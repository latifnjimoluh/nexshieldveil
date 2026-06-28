"""Tests for the AppController contract via the FakeController stub (headless)."""

from __future__ import annotations

import pytest

from privacy_guard.policy import PolicyState
from privacy_guard.ui.fake_controller import FakeController
from privacy_guard.ui.state import CameraError, ProtectionState, UiSnapshot

pytestmark = pytest.mark.unit


@pytest.fixture
def ctrl(qapp) -> FakeController:
    return FakeController()


# --------------------------------------------------------------------------- #
# commands change state and emit the right signals
# --------------------------------------------------------------------------- #
def test_enable_then_pause_toggles_running_and_state(ctrl: FakeController, record) -> None:
    states = record(ctrl.state_changed)
    runs = record(ctrl.running_changed)

    ctrl.enable()
    assert ctrl.property("running") is True
    assert ctrl.property("protection_state") == ProtectionState.CLEAR.value

    ctrl.pause()
    assert ctrl.property("running") is False
    assert ctrl.property("protection_state") == ProtectionState.PAUSED.value
    # Two genuine running transitions and two state transitions occurred.
    assert len(runs) == 2
    assert len(states) == 2


def test_toggle_flips_running(ctrl: FakeController) -> None:
    assert ctrl.property("running") is False
    ctrl.toggle()
    assert ctrl.property("running") is True
    ctrl.toggle()
    assert ctrl.property("running") is False


def test_pause_clears_error_and_camera(ctrl: FakeController) -> None:
    ctrl.emit_error(CameraError.DISCONNECTED)
    ctrl.emit_camera_active(True)
    assert ctrl.property("protection_state") == ProtectionState.CAMERA_ERROR.value

    ctrl.pause()
    assert ctrl.property("error_kind") == ""
    assert ctrl.property("camera_active") is False
    assert ctrl.property("protection_state") == ProtectionState.PAUSED.value


# --------------------------------------------------------------------------- #
# hysteresis invariant is preserved at the UI boundary too
# --------------------------------------------------------------------------- #
def test_set_trigger_above_release_raises_release(ctrl: FakeController) -> None:
    ctrl.set_release_ms(800)
    ctrl.set_trigger_ms(1200)
    assert ctrl.property("trigger_ms") == 1200
    assert ctrl.property("release_ms") == 1200  # raised to keep release >= trigger


def test_set_release_below_trigger_is_clamped(ctrl: FakeController) -> None:
    ctrl.set_trigger_ms(400)
    ctrl.set_release_ms(100)
    assert ctrl.property("release_ms") == 400  # clamped up to the trigger


def test_negative_trigger_is_floored_to_zero(ctrl: FakeController) -> None:
    ctrl.set_trigger_ms(-50)
    assert ctrl.property("trigger_ms") == 0


# --------------------------------------------------------------------------- #
# config setters emit config_changed; no-op writes emit nothing
# --------------------------------------------------------------------------- #
def test_config_setters_emit_config_changed(ctrl: FakeController, record) -> None:
    cfg = record(ctrl.config_changed)
    ctrl.set_masking_strategy("veil")  # default is already 'veil' -> no change
    assert cfg == []
    ctrl.set_masking_strategy("blur")
    ctrl.set_sensitivity_deg(25.0)
    ctrl.select_camera(2)
    ctrl.set_start_at_login(True)
    assert len(cfg) == 4


def test_setting_same_value_emits_no_signal(ctrl: FakeController, record) -> None:
    ctrl.enable()
    runs = record(ctrl.running_changed)
    ctrl.enable()  # already running
    assert runs == []


# --------------------------------------------------------------------------- #
# intent signals reach the shell (recorded by the fake)
# --------------------------------------------------------------------------- #
def test_intents_are_emitted(ctrl: FakeController) -> None:
    ctrl.open_settings()
    ctrl.finish_onboarding()
    ctrl.quit()
    assert (ctrl.settings_opened, ctrl.onboarding_done, ctrl.quit_calls) == (1, 1, 1)


# --------------------------------------------------------------------------- #
# pushed core signals map to the right UI state
# --------------------------------------------------------------------------- #
def test_emit_masked_is_protected(ctrl: FakeController) -> None:
    ctrl.emit_masked(True)
    assert ctrl.property("protection_state") == ProtectionState.PROTECTED.value


def test_emit_observer_detected_sets_engaging_without_changing_state(ctrl: FakeController) -> None:
    ctrl.emit_observer_detected()
    assert ctrl.property("engaging") is True
    # Still 'clear' logically — engaging is only a hint, not a state.
    assert ctrl.property("protection_state") == ProtectionState.CLEAR.value


def test_emit_error_is_camera_error(ctrl: FakeController) -> None:
    ctrl.emit_error(CameraError.NO_CAMERA)
    assert ctrl.property("protection_state") == ProtectionState.CAMERA_ERROR.value
    assert ctrl.property("error_kind") == "no_camera"


def test_starting_snapshot_is_respected(qapp) -> None:
    ctrl = FakeController(UiSnapshot(running=True, is_masked=True))
    assert ctrl.property("protection_state") == ProtectionState.PROTECTED.value


def test_faces_count_never_negative(ctrl: FakeController) -> None:
    ctrl.emit_faces(-5)
    assert ctrl.property("faces_count") == 0


def test_engaging_cleared_when_masked(ctrl: FakeController) -> None:
    ctrl.emit_observer_detected()
    assert ctrl.property("engaging") is True
    ctrl.emit_masked(True, policy_state=PolicyState.MASKED)
    assert ctrl.property("engaging") is False
