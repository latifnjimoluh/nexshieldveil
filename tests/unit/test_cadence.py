"""Frame pacing and idle back-off (AM-13). Pure: the clock is passed in.

Two things are under test: the sleep must *absorb* the processing time rather
than add to it, and the rate must drop only when genuinely nothing is happening.
"""

from __future__ import annotations

import pytest

from privacy_guard.capture import AdaptiveCadence

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# construction
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "kwargs",
    [
        {"target_fps": 0},
        {"target_fps": -1},
        {"target_fps": 15, "idle_fps": 0},
        {"target_fps": 15, "idle_after_ms": -1},
    ],
)
def test_invalid_parameters_are_rejected(kwargs) -> None:
    with pytest.raises(ValueError):
        AdaptiveCadence(**kwargs)


def test_the_idle_rate_never_exceeds_the_full_rate() -> None:
    # "Backing off" to something faster would be nonsense.
    cadence = AdaptiveCadence(target_fps=4, idle_fps=30)
    assert cadence.idle_fps == 4


def test_it_starts_at_the_full_rate() -> None:
    cadence = AdaptiveCadence(target_fps=15)
    assert cadence.is_idle is False
    assert cadence.current_fps == 15
    assert cadence.period_ms == pytest.approx(1000 / 15)


# --------------------------------------------------------------------------- #
# deadline pacing: the sleep absorbs the work
# --------------------------------------------------------------------------- #
def test_the_sleep_absorbs_the_processing_time() -> None:
    # The old code slept a fixed 1000/fps on top of the work, so 15 fps
    # requested with 25 ms of inference actually ran at ~11 fps.
    cadence = AdaptiveCadence(target_fps=15)  # 66.7 ms per frame
    assert cadence.sleep_ms(25.0) == pytest.approx(41.7, abs=0.1)
    assert cadence.sleep_ms(0.0) == pytest.approx(66.7, abs=0.1)


def test_a_frame_over_budget_sleeps_zero_rather_than_going_negative() -> None:
    cadence = AdaptiveCadence(target_fps=15)
    assert cadence.sleep_ms(200.0) == 0.0
    assert cadence.is_late(200.0) is True
    assert cadence.is_late(10.0) is False


def test_negative_work_is_treated_as_zero() -> None:
    # A non-monotonic clock must not produce a longer-than-period sleep.
    cadence = AdaptiveCadence(target_fps=10)
    assert cadence.sleep_ms(-50.0) == pytest.approx(100.0)


# --------------------------------------------------------------------------- #
# idle back-off
# --------------------------------------------------------------------------- #
def test_an_empty_room_backs_off_after_the_configured_delay() -> None:
    cadence = AdaptiveCadence(target_fps=15, idle_fps=5, idle_after_ms=30_000)
    cadence.observe(now_ms=0.0, faces_count=1, masked=False)
    cadence.observe(now_ms=20_000.0, faces_count=0, masked=False)
    assert cadence.is_idle is False  # 20 s: not yet
    cadence.observe(now_ms=30_000.0, faces_count=0, masked=False)
    assert cadence.is_idle is True
    assert cadence.current_fps == 5
    assert cadence.sleep_ms(0.0) == pytest.approx(200.0)


def test_a_face_appearing_restores_the_full_rate_at_once() -> None:
    # The whole point: backing off must never delay the *reaction*, only the
    # polling while there is demonstrably nothing to react to.
    cadence = AdaptiveCadence(target_fps=15, idle_fps=5, idle_after_ms=1_000)
    cadence.observe(now_ms=0.0, faces_count=0, masked=False)
    cadence.observe(now_ms=1_000.0, faces_count=0, masked=False)
    assert cadence.is_idle is True
    cadence.observe(now_ms=1_200.0, faces_count=1, masked=False)
    assert cadence.is_idle is False
    assert cadence.current_fps == 15


def test_an_engaged_mask_counts_as_activity() -> None:
    # The walk-away lock masks an EMPTY frame. Idling then would slow down
    # noticing the user's return, which is precisely when it must be quick.
    cadence = AdaptiveCadence(target_fps=15, idle_fps=5, idle_after_ms=1_000)
    for t in range(0, 10_000, 100):
        cadence.observe(now_ms=float(t), faces_count=0, masked=True)
    assert cadence.is_idle is False


def test_the_idle_timer_restarts_on_every_face() -> None:
    cadence = AdaptiveCadence(target_fps=15, idle_fps=5, idle_after_ms=1_000)
    cadence.observe(now_ms=0.0, faces_count=0, masked=False)
    cadence.observe(now_ms=900.0, faces_count=1, masked=False)
    cadence.observe(now_ms=1_800.0, faces_count=0, masked=False)
    assert cadence.is_idle is False  # only 900 ms of new emptiness


def test_the_adaptive_part_can_be_disabled() -> None:
    cadence = AdaptiveCadence(target_fps=15, idle_fps=5, idle_after_ms=0)
    for t in range(0, 120_000, 1_000):
        cadence.observe(now_ms=float(t), faces_count=0, masked=False)
    assert cadence.is_idle is False
    assert cadence.current_fps == 15


def test_the_first_empty_frame_starts_the_clock_rather_than_idling() -> None:
    # Starting up in an empty room must not jump straight to the idle rate.
    cadence = AdaptiveCadence(target_fps=15, idle_fps=5, idle_after_ms=1_000)
    cadence.observe(now_ms=50_000.0, faces_count=0, masked=False)
    assert cadence.is_idle is False


def test_reset_returns_to_the_full_rate() -> None:
    cadence = AdaptiveCadence(target_fps=15, idle_fps=5, idle_after_ms=1_000)
    cadence.observe(now_ms=0.0, faces_count=0, masked=False)
    cadence.observe(now_ms=1_000.0, faces_count=0, masked=False)
    assert cadence.is_idle is True
    cadence.reset()
    assert cadence.is_idle is False


def test_a_realistic_session_spends_most_frames_idle() -> None:
    # A laptop left alone for an hour: the loop must actually save work, not
    # just claim to. 15 fps for an hour is 54_000 frames; at 5 fps it is 18_000.
    cadence = AdaptiveCadence(target_fps=15, idle_fps=5, idle_after_ms=30_000)
    elapsed_ms, frames = 0.0, 0
    while elapsed_ms < 3_600_000:
        cadence.observe(now_ms=elapsed_ms, faces_count=0, masked=False)
        elapsed_ms += cadence.sleep_ms(5.0) + 5.0
        frames += 1
    assert frames < 20_000, f"expected the idle rate to dominate, got {frames} frames"
