"""Unit tests for the resilient frame source (M-R1: survive sleep/unplug).

Everything is exercised headlessly: the camera is a scripted fake, the clock and
sleep are injected, so backoff schedules and abort behaviour are asserted without
real waiting. The tester-reported bug ("after sleep, detection never comes back")
is reproduced as: reads fail -> the wrapper reopens by itself -> frames flow again.
"""

from __future__ import annotations

import numpy as np
import pytest

from privacy_guard.capture import (
    Frame,
    FrameSource,
    ReconnectPolicy,
    ResilientFrameSource,
    SourceHealth,
)

pytestmark = pytest.mark.unit


def _frame(value: int = 0) -> Frame:
    """A tiny frame with deliberately non-monotonic metadata.

    Every inner source stamps ``timestamp_ms=0.0, index=0`` — like a real camera
    that was just reopened — so the tests prove the *wrapper* renumbers them.
    """
    image = np.full((4, 4, 3), value % 256, dtype=np.uint8)
    return Frame(image=image, timestamp_ms=0.0, index=0)


class ScriptedSource(FrameSource):
    """Plays a script of reads: a Frame is returned, None is a failed read."""

    def __init__(self, script: list[Frame | None]) -> None:
        self._script = list(script)
        self.closed = False
        self.reads = 0

    @property
    def is_available(self) -> bool:
        return not self.closed

    def read(self) -> Frame | None:
        self.reads += 1
        if not self._script:
            return None
        return self._script.pop(0)

    def close(self) -> None:
        self.closed = True


class RaisingSource(ScriptedSource):
    """A source whose reads explode (cv2 can raise on suspend-invalidated handles)."""

    def read(self) -> Frame | None:
        self.reads += 1
        raise OSError("handle invalidated by suspend")

    def close(self) -> None:
        if self.closed:
            raise OSError("already dead")
        self.closed = True


class UnavailableSource(ScriptedSource):
    """Opens, but immediately reports unavailable (device busy)."""

    @property
    def is_available(self) -> bool:
        return False


class Harness:
    """Wires a ResilientFrameSource with recording fakes for sleep/health/reopen."""

    def __init__(
        self,
        first: FrameSource,
        reopened: list[FrameSource | Exception] | None = None,
        policy: ReconnectPolicy | None = None,
        abort_after_sleeps: int | None = None,
    ) -> None:
        self.sleeps: list[float] = []
        self.health: list[SourceHealth] = []
        self.reopen_calls = 0
        self._reopened = list(reopened or [])
        self._abort_after_sleeps = abort_after_sleeps
        self._now = 0.0
        self.source = ResilientFrameSource(
            first,
            reopen=self._reopen,
            policy=policy or ReconnectPolicy(retry_delay_s=0.1),
            should_abort=self._should_abort,
            on_health=self.health.append,
            sleep=self.sleeps.append,
            clock=self._clock,
        )

    def _clock(self) -> float:
        # Advance 10 ms per look at the clock: deterministic, monotonic.
        self._now += 0.010
        return self._now

    def _should_abort(self) -> bool:
        return self._abort_after_sleeps is not None and len(self.sleeps) >= self._abort_after_sleeps

    def _reopen(self) -> FrameSource:
        self.reopen_calls += 1
        if not self._reopened:
            raise RuntimeError("camera still absent")
        item = self._reopened.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


# --------------------------------------------------------------------------- #
# ReconnectPolicy — validation and backoff shape
# --------------------------------------------------------------------------- #
def test_policy_rejects_zero_tolerance() -> None:
    with pytest.raises(ValueError):
        ReconnectPolicy(failure_tolerance=0)


def test_policy_rejects_negative_retry_delay() -> None:
    with pytest.raises(ValueError):
        ReconnectPolicy(retry_delay_s=-0.1)


def test_policy_rejects_empty_or_nonpositive_backoff() -> None:
    with pytest.raises(ValueError):
        ReconnectPolicy(backoff_s=())
    with pytest.raises(ValueError):
        ReconnectPolicy(backoff_s=(1.0, 0.0))


def test_backoff_is_capped_at_last_entry_forever() -> None:
    policy = ReconnectPolicy(backoff_s=(1.0, 2.0, 5.0))
    assert [policy.delay_for(i) for i in (0, 1, 2, 3, 50)] == [1.0, 2.0, 5.0, 5.0, 5.0]


# --------------------------------------------------------------------------- #
# Healthy path — pass-through with renumbering
# --------------------------------------------------------------------------- #
def test_healthy_reads_pass_frames_through() -> None:
    frames = [_frame(1), _frame(2)]
    h = Harness(ScriptedSource(list(frames)))
    out = [h.source.read(), h.source.read()]
    # Same pixel data (the very same array object: no copy, RAM-only invariant).
    assert out[0] is not None and out[0].image is frames[0].image
    assert out[1] is not None and out[1].image is frames[1].image
    assert h.reopen_calls == 0
    assert h.health == []


def test_wrapper_renumbers_indices_and_timestamps() -> None:
    h = Harness(ScriptedSource([_frame(), _frame(), _frame()]))
    out = [h.source.read() for _ in range(3)]
    assert [f.index for f in out if f is not None] == [0, 1, 2]
    stamps = [f.timestamp_ms for f in out if f is not None]
    assert stamps == sorted(stamps)
    assert len(set(stamps)) == 3  # strictly increasing


def test_timestamps_strictly_increase_even_with_frozen_clock() -> None:
    # MediaPipe's video mode rejects equal timestamps; the +1 ms floor prevents it.
    h = Harness(ScriptedSource([_frame(), _frame(), _frame()]))
    h.source.clock = lambda: 0.0  # freeze time entirely
    out = [h.source.read() for _ in range(3)]
    stamps = [f.timestamp_ms for f in out if f is not None]
    assert stamps[0] < stamps[1] < stamps[2]


# --------------------------------------------------------------------------- #
# Transient glitches — retried in place, no reopen
# --------------------------------------------------------------------------- #
def test_failures_below_tolerance_recover_without_reopen() -> None:
    h = Harness(ScriptedSource([None, None, _frame(7)]))  # tolerance is 3
    frame = h.source.read()
    assert frame is not None
    assert h.reopen_calls == 0
    assert h.health == []  # the user never saw a thing
    # One retry pause per failed read.
    assert h.sleeps == pytest.approx([0.1, 0.1])


def test_success_resets_the_failure_counter() -> None:
    script: list[Frame | None] = [None, None, _frame(1), None, None, _frame(2)]
    h = Harness(ScriptedSource(script))
    assert h.source.read() is not None
    assert h.source.read() is not None
    assert h.reopen_calls == 0  # 2+2 failures, but never 3 in a row


# --------------------------------------------------------------------------- #
# Camera lost — automatic reopen with backoff (the sleep/resume bug)
# --------------------------------------------------------------------------- #
def test_lost_camera_is_reopened_and_frames_flow_again() -> None:
    dead = ScriptedSource([None, None, None])
    revived = ScriptedSource([_frame(9), _frame(10)])
    h = Harness(dead, reopened=[revived])
    frame = h.source.read()
    assert frame is not None and frame.image is not None
    assert dead.closed  # the dead handle was released
    assert h.health == [SourceHealth.RECONNECTING, SourceHealth.OK]
    # Next reads keep flowing from the new source, index continuity preserved.
    nxt = h.source.read()
    assert nxt is not None and nxt.index == frame.index + 1


def test_reopen_failures_follow_the_capped_backoff_schedule() -> None:
    revived = ScriptedSource([_frame(1)])
    h = Harness(
        RaisingSource([]),  # reads raise -> counted as failures (P4: never crash)
        reopened=[RuntimeError("no device"), RuntimeError("busy"), RuntimeError("busy"), revived],
        policy=ReconnectPolicy(failure_tolerance=2, retry_delay_s=0.0, backoff_s=(1.0, 2.0, 5.0)),
    )
    frame = h.source.read()
    assert frame is not None
    assert h.reopen_calls == 4
    # Waited 1 s, 2 s, 5 s, then 5 s again (cap), sliced into <=0.1 s abort checks.
    assert sum(h.sleeps) == pytest.approx(1.0 + 2.0 + 5.0 + 5.0)
    assert max(h.sleeps) <= h.source.poll_interval_s


def test_reopened_source_must_prove_itself_with_a_frame() -> None:
    blind = ScriptedSource([None])  # opens but cannot read
    busy = UnavailableSource([])  # opens but reports unavailable
    good = ScriptedSource([_frame(3)])
    h = Harness(ScriptedSource([None, None, None]), reopened=[blind, busy, good])
    frame = h.source.read()
    assert frame is not None
    assert blind.closed and busy.closed  # failed candidates are not leaked
    assert h.health == [SourceHealth.RECONNECTING, SourceHealth.OK]


def test_reopened_source_whose_read_raises_is_discarded() -> None:
    exploding = RaisingSource([])  # opens fine, then its probe read raises
    good = ScriptedSource([_frame(5)])
    h = Harness(ScriptedSource([None, None, None]), reopened=[exploding, good])
    frame = h.source.read()
    assert frame is not None
    assert exploding.closed  # the failed candidate was released, not leaked
    assert h.reopen_calls == 2


def test_indices_and_timestamps_stay_monotonic_across_reconnect() -> None:
    # Both inner sources restart their own numbering at 0; the wrapper must not.
    h = Harness(
        ScriptedSource([_frame(1), None, None, None]),
        reopened=[ScriptedSource([_frame(2)])],
    )
    first = h.source.read()
    second = h.source.read()
    assert first is not None and second is not None
    assert second.index == first.index + 1
    assert second.timestamp_ms > first.timestamp_ms


# --------------------------------------------------------------------------- #
# Abort and close — None means final, and the worker never blocks
# --------------------------------------------------------------------------- #
def test_abort_during_backoff_returns_none_quickly() -> None:
    h = Harness(ScriptedSource([None, None, None]), abort_after_sleeps=3)
    assert h.source.read() is None
    # It stopped mid-backoff instead of waiting the full schedule out.
    assert len(h.sleeps) == 3


def test_abort_requested_upfront_reads_nothing() -> None:
    inner = ScriptedSource([_frame(1)])
    h = Harness(inner, abort_after_sleeps=0)
    assert h.source.read() is None
    assert inner.reads == 0


def test_abort_during_a_transient_retry_wait_returns_none() -> None:
    # The stop flag flips while the wrapper pauses between two in-place retries.
    inner = ScriptedSource([None, _frame(1)])
    h = Harness(inner, abort_after_sleeps=1)
    assert h.source.read() is None
    assert inner.reads == 1  # never got to the second read


def test_close_while_reconnecting_is_a_no_op_on_the_gone_source() -> None:
    # Aborting mid-reconnect leaves no live inner source; close() must cope.
    h = Harness(ScriptedSource([None, None, None]), abort_after_sleeps=5)
    assert h.source.read() is None
    h.source.close()
    assert not h.source.is_available


def test_close_releases_inner_source_and_ends_reads() -> None:
    inner = ScriptedSource([_frame(1)])
    h = Harness(inner)
    h.source.close()
    assert inner.closed
    assert not h.source.is_available
    assert h.source.read() is None


def test_close_survives_a_source_that_raises_on_close() -> None:
    dead = RaisingSource([])
    dead.closed = True  # its close() now raises
    h = Harness(dead)
    h.source.close()  # must not propagate
    assert h.source.read() is None


def test_available_while_reconnecting() -> None:
    # 'Reconnecting' is not 'gone': the wrapper still promises future frames.
    h = Harness(ScriptedSource([None, None, None]), abort_after_sleeps=5)
    assert h.source.read() is None  # aborted mid-reconnect
    assert h.source.is_available


def test_health_callback_is_optional() -> None:
    source = ResilientFrameSource(
        ScriptedSource([None, None, None]),
        reopen=lambda: ScriptedSource([_frame(4)]),
        policy=ReconnectPolicy(retry_delay_s=0.0),
        sleep=lambda _s: None,
    )
    assert source.read() is not None  # no on_health, no crash
