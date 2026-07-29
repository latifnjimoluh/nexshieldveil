"""Frame pacing: honour the configured rate, and back off when nothing happens (AM-13).

Two defects lived in one line of the worker loop
(``self.msleep(int(1000 / target_fps))``):

1. **The pause was fixed**, so it added to the processing time instead of
   absorbing it. At 15 fps requested and 25 ms of inference, the loop actually ran
   at ~11 fps — and the real masking latency drifted with it, silently.
2. **The rate never adapted.** The same cadence ran whether someone had been
   sitting there for an hour or the room had been empty since lunch. On a laptop
   that is the difference between an app people keep and an app they uninstall
   because of the battery.

:class:`AdaptiveCadence` fixes both, and stays pure: the clock is passed in, so
every rule is unit-tested with no sleeping and no camera.

The honest cost of backing off is written down in ``docs/LIMITATIONS.md``: while
idling at the reduced rate, a person who appears is noticed up to one idle frame
later. That window is added to the masking delay, so the idle rate is a floor on
how fast the app can *start* reacting — never on how fast it reacts once someone
is there.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class AdaptiveCadence:
    """Decides how long the capture loop should sleep after each frame.

    Full rate applies whenever the situation is live: a face was seen recently,
    or the mask is currently engaged. The reduced rate applies only after
    ``idle_after_ms`` with an empty frame — i.e. nobody in front of the screen.

    Args:
        target_fps: The configured (full) frame rate.
        idle_fps: Reduced rate used when nothing has happened for a while.
            Must not exceed ``target_fps``; it is clamped down if it does.
        idle_after_ms: How long the frame must stay empty before backing off.
            ``0`` disables the adaptive part, leaving only the deadline pacing.

    Raises:
        ValueError: If either rate is not positive, or ``idle_after_ms`` is negative.
    """

    def __init__(self, target_fps: int, idle_fps: int = 5, idle_after_ms: float = 30_000.0) -> None:
        """Start at the full rate, with no face seen yet."""
        if target_fps <= 0:
            msg = f"target_fps must be > 0, got {target_fps}"
            raise ValueError(msg)
        if idle_fps <= 0:
            msg = f"idle_fps must be > 0, got {idle_fps}"
            raise ValueError(msg)
        if idle_after_ms < 0:
            msg = f"idle_after_ms must be >= 0, got {idle_after_ms}"
            raise ValueError(msg)
        self.target_fps = target_fps
        # Never "back off" to something faster than the configured rate.
        self.idle_fps = min(idle_fps, target_fps)
        self.idle_after_ms = float(idle_after_ms)
        self._last_activity_ms: float | None = None
        self._idle = False

    @property
    def is_idle(self) -> bool:
        """Whether the loop is currently running at the reduced rate."""
        return self._idle

    @property
    def current_fps(self) -> float:
        """The rate currently in force."""
        return float(self.idle_fps if self._idle else self.target_fps)

    @property
    def period_ms(self) -> float:
        """The interval between two frames at the current rate."""
        return 1000.0 / self.current_fps

    def observe(self, *, now_ms: float, faces_count: int, masked: bool) -> None:
        """Record what the last frame contained, updating the rate.

        Args:
            now_ms: Monotonic timestamp of the frame just processed.
            faces_count: How many faces it contained.
            masked: Whether the mask is currently engaged.
        """
        # A mask that is up counts as activity even with an empty frame: that is
        # exactly the walk-away lock case, and it must stay responsive to the
        # user coming back.
        if faces_count > 0 or masked:
            self._last_activity_ms = now_ms
            self._set_idle(False)
            return
        if self.idle_after_ms <= 0.0:  # adaptive part disabled
            return
        if self._last_activity_ms is None:
            self._last_activity_ms = now_ms
            return
        if now_ms - self._last_activity_ms >= self.idle_after_ms:
            self._set_idle(True)

    def sleep_ms(self, work_ms: float) -> float:
        """How long to sleep after a frame that took ``work_ms`` to process.

        This is the deadline pacing: the sleep *absorbs* the work instead of
        adding to it, so the loop holds the configured rate as long as the
        machine can keep up. When it cannot, the result is ``0`` — running late
        is reported by :meth:`is_late`, never hidden by an extra pause.
        """
        return max(0.0, self.period_ms - max(0.0, work_ms))

    def is_late(self, work_ms: float) -> bool:
        """Whether processing alone already exceeded the frame budget."""
        return work_ms > self.period_ms

    def reset(self) -> None:
        """Forget the activity history and return to the full rate."""
        self._last_activity_ms = None
        self._set_idle(False)

    def _set_idle(self, idle: bool) -> None:
        if idle != self._idle:
            self._idle = idle
            logger.info(
                "Capture cadence -> %.0f fps (%s).",
                self.current_fps,
                "idle: nobody in front of the camera" if idle else "active",
            )
