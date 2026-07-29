"""Hardware-free tests for the live CoreController's result/config mapping."""

from __future__ import annotations

import pytest

from privacy_guard.app import FrameResult
from privacy_guard.config import AppConfig
from privacy_guard.policy import MaskReason, PolicyState
from privacy_guard.ui.core_controller import (
    CoreController,
    app_config_from_snapshot,
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


def test_app_config_from_snapshot_reflects_runtime_settings() -> None:
    # The worker is built from the snapshot-merged config, so persisted or
    # edited detection settings actually reach the pipeline (M-R2).
    cfg = AppConfig()
    snap = UiSnapshot(
        masking_strategy="pixelate",
        opacity=0.6,
        sensitivity_deg=24.0,
        trigger_ms=600,
        release_ms=900,
        camera_index=1,
    )
    merged = app_config_from_snapshot(cfg, snap)
    assert merged.camera.device_index == 1
    assert merged.geometry.gaze_tolerance_deg == 24.0
    assert merged.policy.trigger_ms == 600
    assert merged.policy.release_ms == 900
    assert merged.masking == masking_config_from_snapshot(snap)
    # Non-UI parts pass through untouched.
    assert merged.detection == cfg.detection
    assert merged.tracking == cfg.tracking
    assert merged.geometry.screen_width_mm == cfg.geometry.screen_width_mm


def test_app_config_from_snapshot_roundtrips_the_defaults() -> None:
    cfg = AppConfig()
    assert app_config_from_snapshot(cfg, snapshot_from_config(cfg)) == cfg


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


# --------------------------------------------------------------------------- #
# overlay copy: supplied by the shell's translator, re-read on every rebuild
# so a language switch reaches the full-screen mask too (AM-2)
# --------------------------------------------------------------------------- #
def test_overlay_labels_come_from_the_injected_provider() -> None:
    lang = {"code": "fr"}
    controller = CoreController(
        AppConfig(),
        "model.task",
        overlay_labels=lambda: (
            ("Contenu masqué", "Un observateur regarde ton écran")
            if lang["code"] == "fr"
            else ("Content hidden", "Someone else is looking at your screen")
        ),
    )
    assert controller.overlay_labels() == ("Contenu masqué", "Un observateur regarde ton écran")
    # Switching language must be reflected on the NEXT read, not frozen at build.
    lang["code"] = "en"
    assert controller.overlay_labels() == (
        "Content hidden",
        "Someone else is looking at your screen",
    )


def test_overlay_labels_are_none_without_a_provider() -> None:
    # The headless/CLI path has no translator; the Qt adapter's own fallback applies.
    assert CoreController(AppConfig(), "model.task").overlay_labels() is None


def test_overlay_labels_survive_a_failing_provider() -> None:
    # A caption is never worth losing the mask over.
    def boom() -> tuple[str, str]:
        raise RuntimeError("translator gone")

    controller = CoreController(AppConfig(), "model.task", overlay_labels=boom)
    assert controller.overlay_labels() is None


# --------------------------------------------------------------------------- #
# walk-away lock (AM-7): the setting must reach the pipeline, and the reason
# must reach the interface
# --------------------------------------------------------------------------- #
def test_absence_lock_reaches_the_worker_config() -> None:
    snap = UiSnapshot(trigger_ms=400, release_ms=800, absence_lock_ms=12_000)
    assert app_config_from_snapshot(AppConfig(), snap).policy.absence_ms == 12_000


def test_absence_lock_off_reaches_the_worker_config_as_zero() -> None:
    snap = UiSnapshot(absence_lock_ms=0)
    assert app_config_from_snapshot(AppConfig(), snap).policy.absence_ms == 0


def test_snapshot_from_config_mirrors_the_absence_lock() -> None:
    cfg = AppConfig()
    cfg = cfg.model_copy(update={"policy": cfg.policy.model_copy(update={"absence_ms": 9_000})})
    assert snapshot_from_config(cfg).absence_lock_ms == 9_000


@pytest.mark.parametrize(
    ("reason", "expected"),
    [(MaskReason.OBSERVER, "observer"), (MaskReason.ABSENCE, "absence"), (None, None)],
)
def test_mask_reason_is_mapped_onto_the_snapshot(qapp, reason, expected) -> None:
    controller = CoreController(AppConfig(), "model.task")
    result = FrameResult(
        index=0,
        timestamp_ms=0.0,
        n_faces=0,
        primary_index=None,
        observer_present=False,
        smoothed_confidence=0.0,
        state=PolicyState.MASKED,
        is_masked=True,
        mask_reason=reason,
    )
    controller.apply_frame_result(result)
    assert controller.snapshot.mask_reason == expected
