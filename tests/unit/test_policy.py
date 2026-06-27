"""Unit tests for the decision state machine and its hysteresis."""

from __future__ import annotations

import pytest

from privacy_guard.config import PolicyConfig
from privacy_guard.policy import DecisionStateMachine, PolicyState

pytestmark = pytest.mark.unit


def make(trigger: float = 400, release: float = 800) -> DecisionStateMachine:
    return DecisionStateMachine(trigger_ms=trigger, release_ms=release)


def feed(
    sm: DecisionStateMachine, present: bool, start: float, count: int, step: float = 50.0
) -> float:
    """Feed `count` observations spaced by `step` ms; return next timestamp."""
    t = start
    for _ in range(count):
        sm.update(present, t)
        t += step
    return t


# --------------------------------------------------------------------------- #
# construction / validation
# --------------------------------------------------------------------------- #
def test_release_below_trigger_rejected() -> None:
    with pytest.raises(ValueError, match="release_ms"):
        DecisionStateMachine(trigger_ms=500, release_ms=100)


def test_negative_thresholds_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        DecisionStateMachine(trigger_ms=-1, release_ms=100)


def test_from_config() -> None:
    sm = DecisionStateMachine.from_config(PolicyConfig(trigger_ms=300, release_ms=700))
    assert sm.trigger_ms == 300
    assert sm.release_ms == 700
    assert sm.state is PolicyState.CLEAR


# --------------------------------------------------------------------------- #
# no false positives
# --------------------------------------------------------------------------- #
def test_primary_user_only_stays_clear() -> None:
    sm = make()
    feed(sm, present=False, start=0.0, count=100)
    assert sm.state is PolicyState.CLEAR
    assert not sm.is_masked


def test_brief_glance_below_trigger_never_masks() -> None:
    sm = make(trigger=400)
    # Observer present for only 300 ms (< 400 ms trigger), then gone.
    feed(sm, present=True, start=0.0, count=6)  # 6 * 50 = 300 ms
    assert sm.state is PolicyState.OBSERVER_DETECTED
    assert not sm.is_masked
    sm.update(False, 350.0)
    assert sm.state is PolicyState.CLEAR


# --------------------------------------------------------------------------- #
# triggering
# --------------------------------------------------------------------------- #
def test_sustained_observer_triggers_masking() -> None:
    sm = make(trigger=400)
    # First present frame enters OBSERVER_DETECTED at t=0.
    sm.update(True, 0.0)
    assert sm.state is PolicyState.OBSERVER_DETECTED
    # By t=400 the trigger threshold is reached.
    sm.update(True, 400.0)
    assert sm.state is PolicyState.MASKED
    assert sm.is_masked


def test_masks_within_expected_frame_budget() -> None:
    # At 20 fps (50 ms/frame), 400 ms trigger => masked within ~9 frames.
    sm = make(trigger=400)
    t = 0.0
    frames = 0
    while sm.state is not PolicyState.MASKED and frames < 100:
        sm.update(True, t)
        t += 50.0
        frames += 1
    assert sm.is_masked
    assert frames <= 9


def test_zero_trigger_masks_immediately() -> None:
    sm = make(trigger=0, release=0)
    sm.update(True, 0.0)
    assert sm.state is PolicyState.MASKED


# --------------------------------------------------------------------------- #
# hysteresis on release
# --------------------------------------------------------------------------- #
def test_release_respects_hysteresis_delay() -> None:
    sm = make(trigger=400, release=800)
    # Get to MASKED.
    sm.update(True, 0.0)
    sm.update(True, 400.0)
    assert sm.is_masked
    # First absent observation at t=400 starts the release timer.
    sm.update(False, 400.0)
    assert sm.is_masked
    sm.update(False, 800.0)  # 400 ms absent < 800 ms
    assert sm.is_masked
    sm.update(False, 1100.0)  # 700 ms absent < 800 ms
    assert sm.is_masked
    # At 1200 ms (800 ms absent) it finally clears.
    sm.update(False, 1200.0)
    assert sm.state is PolicyState.CLEAR


def test_reappearing_observer_resets_release_timer() -> None:
    sm = make(trigger=200, release=600)
    sm.update(True, 0.0)
    sm.update(True, 200.0)
    assert sm.is_masked
    sm.update(False, 300.0)  # absent starts at 300
    sm.update(False, 700.0)  # 400 ms absent, still masked
    assert sm.is_masked
    sm.update(True, 750.0)  # observer back -> reset absence timer
    sm.update(False, 800.0)  # absence restarts at 800
    sm.update(False, 1300.0)  # 500 ms absent, < 600 -> still masked
    assert sm.is_masked
    sm.update(False, 1450.0)  # 650 ms absent -> clears
    assert sm.state is PolicyState.CLEAR


def test_full_cycle_clear_detected_masked_clear() -> None:
    sm = make(trigger=100, release=200)
    assert sm.state is PolicyState.CLEAR
    sm.update(True, 0.0)
    assert sm.state is PolicyState.OBSERVER_DETECTED
    sm.update(True, 100.0)
    assert sm.state is PolicyState.MASKED
    sm.update(False, 200.0)
    sm.update(False, 400.0)
    assert sm.state is PolicyState.CLEAR


def test_reset_returns_to_clear() -> None:
    sm = make(trigger=0)
    sm.update(True, 0.0)
    assert sm.is_masked
    sm.reset()
    assert sm.state is PolicyState.CLEAR
    assert not sm.is_masked
