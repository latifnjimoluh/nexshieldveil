"""Hardware-free tests for the live CoreController's result/config mapping."""

from __future__ import annotations

import pytest

from privacy_guard.app import FrameResult
from privacy_guard.config import AppConfig
from privacy_guard.policy import PolicyState
from privacy_guard.ui.core_controller import (
    CoreController,
    masking_config_from_snapshot,
    snapshot_from_config,
)
from privacy_guard.ui.state import ProtectionState, UiSnapshot

pytestmark = pytest.mark.unit


def _result(*, masked: bool, faces: int, state: PolicyState) -> FrameResult:
    return FrameResult(
        index=0,
        timestamp_ms=0.0,
        n_faces=faces,
        primary_index=0,
        observer_present=masked,
        smoothed_confidence=1.0 if masked else 0.0,
        state=state,
        is_masked=masked,
    )


def test_snapshot_from_config_mirrors_values() -> None:
    cfg = AppConfig()
    snap = snapshot_from_config(cfg)
    assert snap.running is False
    assert snap.sensitivity_deg == cfg.geometry.gaze_tolerance_deg
    assert snap.trigger_ms == cfg.policy.trigger_ms
    assert snap.release_ms == cfg.policy.release_ms
    assert snap.opacity == cfg.masking.opacity
    assert snap.blur_radius == cfg.masking.blur_radius
    assert snap.pixelate_blocks == cfg.masking.pixelate_blocks


def test_masking_config_from_snapshot_reflects_runtime_settings() -> None:
    # The overlay is rebuilt from the snapshot so settings edits apply live.
    snap = UiSnapshot(masking_strategy="blur", opacity=0.5, blur_radius=41, pixelate_blocks=12)
    masking = masking_config_from_snapshot(snap)
    assert masking.strategy == "blur"
    assert masking.opacity == 0.5
    assert masking.blur_radius == 41
    assert masking.pixelate_blocks == 12


def test_masking_config_from_snapshot_roundtrips_the_defaults() -> None:
    cfg = AppConfig()
    snap = snapshot_from_config(cfg)
    assert masking_config_from_snapshot(snap) == cfg.masking


def test_apply_frame_result_sets_protected(qapp) -> None:
    ctrl = CoreController(AppConfig(), model_path="missing.task")
    ctrl.apply_frame_result(_result(masked=True, faces=2, state=PolicyState.MASKED))
    assert ctrl.property("protection_state") == ProtectionState.PROTECTED.value
    assert ctrl.property("faces_count") == 2
    assert ctrl.property("camera_active") is True


def test_apply_frame_result_clear(qapp) -> None:
    ctrl = CoreController(AppConfig(), model_path="missing.task")
    ctrl.apply_frame_result(_result(masked=False, faces=1, state=PolicyState.CLEAR))
    assert ctrl.property("protection_state") == ProtectionState.CLEAR.value


def test_report_worker_error_sets_camera_error(qapp) -> None:
    ctrl = CoreController(AppConfig(), model_path="missing.task")
    # The controller starts paused; an error implies it was trying to run.
    ctrl.apply_frame_result(_result(masked=False, faces=0, state=PolicyState.CLEAR))
    ctrl.report_worker_error("no_camera")
    assert ctrl.property("protection_state") == ProtectionState.CAMERA_ERROR.value
    assert ctrl.property("error_kind") == "no_camera"
    assert ctrl.property("camera_active") is False
