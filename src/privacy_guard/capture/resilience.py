"""Automatic camera-loss recovery: a resilient wrapper around any frame source.

Windows invalidates webcam handles on suspend/resume, and cables get unplugged.
Without recovery, the first failed read kills the surveillance loop and the app
keeps running while protecting nothing — the worst failure mode (see M-R1).

:class:`ResilientFrameSource` keeps the pipeline alive instead: a few
consecutive failed reads are retried in place (transient glitches), then the
dead source is closed and reopened with a capped backoff, indefinitely, until a
frame flows again or the caller aborts. Health transitions are reported through
a callback so the loss is *visible* to the user, never silent.

Two invariants the callers rely on:

* **Timestamps stay strictly increasing across reconnects.** MediaPipe's video
  mode rejects non-monotonic timestamps and the policy's hysteresis compares
  them, but a reopened camera restarts its clock at zero — so the wrapper
  renumbers frames (index and timestamp) with its own clock.
* **``read()`` returning ``None`` means "closed or aborted", never "transient
  glitch"** — a pipeline loop may treat ``None`` as final.

Pure logic: clock and sleep are injectable, so every rule is unit-tested with
no camera and no real waiting. Frames are never stored beyond the one being
returned (privacy: RAM only, nothing accumulated).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from privacy_guard.capture.frame_source import Frame, FrameSource

logger = logging.getLogger(__name__)


class SourceHealth(Enum):
    """Camera health as reported to the UI (a lost camera must be visible)."""

    OK = "ok"
    RECONNECTING = "reconnecting"


@dataclass(frozen=True)
class ReconnectPolicy:
    """When to declare the camera lost, and how patiently to retry opening it.

    Attributes:
        failure_tolerance: Consecutive failed reads before the source is
            declared lost and reopening starts.
        retry_delay_s: Pause between two in-place read retries, so the
            tolerance spans real glitches (a camera busy for ~200 ms) instead
            of being burned in microseconds on a dead handle.
        backoff_s: Wait before each reopen attempt; the last entry repeats
            forever (capped backoff — reopening never gives up on its own).
    """

    failure_tolerance: int = 3
    retry_delay_s: float = 0.1
    backoff_s: tuple[float, ...] = (1.0, 2.0, 5.0)

    def __post_init__(self) -> None:
        """Validate the bounds (a zero/negative wait would spin the CPU)."""
        if self.failure_tolerance < 1:
            msg = f"failure_tolerance must be >= 1, got {self.failure_tolerance}"
            raise ValueError(msg)
        if self.retry_delay_s < 0:
            msg = f"retry_delay_s must be >= 0, got {self.retry_delay_s}"
            raise ValueError(msg)
        if not self.backoff_s or any(delay <= 0 for delay in self.backoff_s):
            msg = f"backoff_s must be non-empty with positive delays, got {self.backoff_s}"
            raise ValueError(msg)

    def delay_for(self, attempt: int) -> float:
        """Backoff before reopen ``attempt`` (0-based); clamps to the last entry."""
        return self.backoff_s[min(attempt, len(self.backoff_s) - 1)]


def _never_abort() -> bool:
    return False


@dataclass
class ResilientFrameSource(FrameSource):
    """Wrap a source so reads survive suspend/resume and unplugged cameras.

    Args:
        source: The already-open source to protect (first connection is the
            caller's responsibility, so a missing camera at startup still gets
            an immediate, actionable error instead of a silent retry loop).
        reopen: Factory building a fresh source for each reconnect attempt.
        policy: Failure tolerance and backoff schedule.
        should_abort: Polled between waits; return ``True`` to make ``read()``
            give up (returning ``None``) so a stopping worker never blocks.
        on_health: Called with ``RECONNECTING`` when the source is declared
            lost and ``OK`` once frames flow again. Called from the reading
            thread.
        sleep: Injectable for tests (defaults to :func:`time.sleep`).
        clock: Injectable monotonic clock in seconds, used to renumber frames.
        poll_interval_s: Granularity at which waits check ``should_abort``.
    """

    source: FrameSource | None
    reopen: Callable[[], FrameSource]
    policy: ReconnectPolicy = field(default_factory=ReconnectPolicy)
    should_abort: Callable[[], bool] = _never_abort
    on_health: Callable[[SourceHealth], None] | None = None
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    poll_interval_s: float = 0.1

    def __post_init__(self) -> None:
        """Start the wrapper's own frame numbering (continuous across reconnects)."""
        self._start_s = self.clock()
        self._closed = False
        self._next_index = 0
        self._last_timestamp_ms = -1.0

    @property
    def is_available(self) -> bool:
        """Available until closed: while reconnecting, frames are still coming."""
        return not self._closed

    def read(self) -> Frame | None:
        """Return the next frame, reconnecting as needed; ``None`` = closed/aborted."""
        failures = 0
        attempt = 0
        while not (self._closed or self.should_abort()):
            if self.source is None:
                # Reconnect phase: wait (interruptibly), then try a fresh source.
                if not self._wait(self.policy.delay_for(attempt)):
                    break
                attempt += 1
                frame = self._probe_new_source()
                if frame is not None:
                    logger.info("Camera reconnected after %d attempt(s).", attempt)
                    self._notify(SourceHealth.OK)
                    return self._renumbered(frame)
                continue
            frame = self._read_current(self.source)
            if frame is not None:
                return self._renumbered(frame)
            failures += 1
            if failures < self.policy.failure_tolerance:
                # Possible transient glitch (camera briefly busy): retry in place.
                if not self._wait(self.policy.retry_delay_s):
                    break
                continue
            logger.warning(
                "Camera read failed %d times in a row; reopening (suspend/unplug?).", failures
            )
            self._notify(SourceHealth.RECONNECTING)
            self._close_quietly(self.source)
            self.source = None
        return None

    def close(self) -> None:
        """Release the current source and make all further reads return ``None``."""
        self._closed = True
        if self.source is not None:
            self._close_quietly(self.source)
            self.source = None

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    def _read_current(self, source: FrameSource) -> Frame | None:
        """Read from the live source; any exception counts as a failed read (P4)."""
        try:
            return source.read()
        except Exception as exc:  # cv2 can raise on handles invalidated by suspend
            logger.warning("Camera read raised %s; treating as a failed read.", exc)
            return None

    def _probe_new_source(self) -> Frame | None:
        """Open a candidate source and prove it with one frame, else discard it."""
        try:
            candidate = self.reopen()
        except Exception as exc:  # device still absent/busy: just try again later
            logger.debug("Reopen attempt failed: %s", exc)
            return None
        try:
            frame = candidate.read() if candidate.is_available else None
        except Exception as exc:  # a source that opens but cannot read is not back
            logger.debug("Reopened camera failed its probe read: %s", exc)
            frame = None
        if frame is None:
            self._close_quietly(candidate)
            return None
        self.source = candidate
        return frame

    def _renumbered(self, frame: Frame) -> Frame:
        """Restamp with the wrapper's own continuous index and monotonic clock.

        The +1 ms floor keeps timestamps *strictly* increasing even if two reads
        land in the same clock millisecond (MediaPipe's video mode requires it).
        """
        elapsed_ms = (self.clock() - self._start_s) * 1000.0
        timestamp_ms = max(elapsed_ms, self._last_timestamp_ms + 1.0)
        self._last_timestamp_ms = timestamp_ms
        renumbered = Frame(image=frame.image, timestamp_ms=timestamp_ms, index=self._next_index)
        self._next_index += 1
        return renumbered

    def _wait(self, seconds: float) -> bool:
        """Sleep in small slices so aborts stay responsive; ``False`` = aborted."""
        remaining = seconds
        while remaining > 0:
            if self._closed or self.should_abort():
                return False
            step = min(self.poll_interval_s, remaining)
            self.sleep(step)
            remaining -= step
        return not (self._closed or self.should_abort())

    def _notify(self, health: SourceHealth) -> None:
        if self.on_health is not None:
            self.on_health(health)

    @staticmethod
    def _close_quietly(source: FrameSource) -> None:
        """Close a (possibly already dead) source without letting it crash us."""
        try:
            source.close()
        except Exception as exc:  # a dead handle may refuse even to close
            logger.debug("Ignoring error while closing a dead source: %s", exc)
