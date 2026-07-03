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
# masking parameters are clamped to the config bounds (M-FP5)
# --------------------------------------------------------------------------- #
def test_set_blur_radius_is_clamped_to_config_bounds(ctrl: FakeController) -> None:
    ctrl.set_blur_radius(50)
    assert ctrl.property("blur_radius") == 50
    ctrl.set_blur_radius(0)
    assert ctrl.property("blur_radius") == 1
    ctrl.set_blur_radius(10_000)
    assert ctrl.property("blur_radius") == 199


def test_set_pixelate_blocks_is_clamped_to_config_bounds(ctrl: FakeController) -> None:
    ctrl.set_pixelate_blocks(32)
    assert ctrl.property("pixelate_blocks") == 32
    ctrl.set_pixelate_blocks(1)
    assert ctrl.property("pixelate_blocks") == 2
    ctrl.set_pixelate_blocks(10_000)
    assert ctrl.property("pixelate_blocks") == 256


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


def test_blur_and_pixelate_changes_emit_config_changed(ctrl: FakeController, record) -> None:
    # Regression (M-R2): these two were missing from the change detection, so
    # QML captions never refreshed and autosave would have missed them.
    cfg = record(ctrl.config_changed)
    ctrl.set_blur_radius(31)
    ctrl.set_pixelate_blocks(48)
    assert len(cfg) == 2


def test_sensitivity_is_clamped_inside_the_config_bounds(ctrl: FakeController) -> None:
    # GeometryConfig requires 0 < deg < 90 (exclusive); a restored/junk value
    # must never be able to build an invalid worker config.
    ctrl.set_sensitivity_deg(500.0)
    assert ctrl.property("sensitivity_deg") == 89.0
    ctrl.set_sensitivity_deg(-3.0)
    assert ctrl.property("sensitivity_deg") == 1.0


def test_setting_same_value_emits_no_signal(ctrl: FakeController, record) -> None:
    ctrl.enable()
    runs = record(ctrl.running_changed)
    ctrl.enable()  # already running
    assert runs == []


# --------------------------------------------------------------------------- #
# timed pause / snooze (M-R3): pauses now, resumes by itself
# --------------------------------------------------------------------------- #
def test_snooze_pauses_and_arms_the_resume_timer(ctrl: FakeController) -> None:
    ctrl.enable()
    ctrl.snooze(5)
    assert ctrl.property("running") is False
    assert ctrl.property("camera_active") is False  # camera released, like a pause
    assert ctrl.snapshot.snoozed_until_ms is not None
    assert ctrl._snooze_timer.isActive()
    assert ctrl._snooze_timer.interval() == 5 * 60_000


def test_snooze_minutes_are_clamped(ctrl: FakeController) -> None:
    ctrl.snooze(0)
    assert ctrl._snooze_timer.interval() == 1 * 60_000
    ctrl.snooze(10_000)
    assert ctrl._snooze_timer.interval() == 480 * 60_000


def test_snooze_elapsed_resumes_watching(ctrl: FakeController) -> None:
    ctrl.snooze(5)
    ctrl._on_snooze_elapsed()  # what the timer calls when time is up
    assert ctrl.property("running") is True
    assert ctrl.snapshot.snoozed_until_ms is None


def test_manual_resume_cancels_the_snooze(ctrl: FakeController) -> None:
    ctrl.snooze(5)
    ctrl.enable()
    assert ctrl.snapshot.snoozed_until_ms is None
    assert not ctrl._snooze_timer.isActive()


def test_manual_pause_cancels_the_snooze(ctrl: FakeController) -> None:
    # 'Pause' means 'until I say so': the auto-resume must not fire later.
    ctrl.snooze(5)
    ctrl.pause()
    assert ctrl.snapshot.snoozed_until_ms is None
    assert not ctrl._snooze_timer.isActive()
    ctrl._on_snooze_elapsed()  # a stale timer callback must be a no-op
    assert ctrl.property("running") is False


def test_snoozing_again_rearms_with_the_new_duration(ctrl: FakeController) -> None:
    ctrl.snooze(5)
    first_until = ctrl.snapshot.snoozed_until_ms
    ctrl.snooze(15)
    assert ctrl._snooze_timer.interval() == 15 * 60_000
    assert ctrl.snapshot.snoozed_until_ms is not None
    assert ctrl.snapshot.snoozed_until_ms > first_until


def test_snooze_emits_snooze_changed(ctrl: FakeController, record) -> None:
    events = record(ctrl.snooze_changed)
    ctrl.snooze(5)
    assert len(events) == 1
    ctrl.enable()
    assert len(events) == 2  # cleared


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
def test_preview_enable_also_starts_watching(ctrl: FakeController) -> None:
    assert ctrl.property("preview_enabled") is False
    ctrl.set_preview_enabled(True)
    assert ctrl.property("preview_enabled") is True
    assert ctrl.property("running") is True  # turning on the camera view resumes watching


def test_preview_toggle(ctrl: FakeController) -> None:
    ctrl.toggle_preview()
    assert ctrl.property("preview_enabled") is True
    ctrl.toggle_preview()
    assert ctrl.property("preview_enabled") is False


def test_pause_disables_preview(ctrl: FakeController) -> None:
    ctrl.set_preview_enabled(True)
    ctrl.pause()
    assert ctrl.property("preview_enabled") is False
    assert ctrl.property("running") is False


def test_preview_change_emits_signal(ctrl: FakeController, record) -> None:
    events = record(ctrl.preview_changed)
    ctrl.set_preview_enabled(True)
    assert len(events) == 1


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
