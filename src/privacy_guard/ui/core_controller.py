"""The live AppController: drives the snapshot from the real pipeline.

Heavy work (capture + inference + decision) runs in a :class:`_PipelineWorker`
``QThread`` so the Qt UI thread never blocks — it only receives per-frame results
and paints the overlay. This keeps the contract identical to the FakeController, so
the same view-models work unchanged.

The worker construction needs a camera/model and a display, so those paths are
excluded from coverage; the pure result->snapshot mapping (:meth:`apply_frame_result`)
is hardware-free and unit-tested.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from privacy_guard.app import FrameResult
from privacy_guard.config import (
    AppConfig,
    CameraConfig,
    GeometryConfig,
    MaskingConfig,
    PolicyConfig,
)
from privacy_guard.ui.controller import AppController
from privacy_guard.ui.state import CameraError, UiSnapshot

logger = logging.getLogger("privacy_guard.ui")


def snapshot_from_config(config: AppConfig) -> UiSnapshot:
    """Build the initial (paused) snapshot mirroring the app config."""
    return UiSnapshot(
        running=False,
        masking_strategy=config.masking.strategy,
        opacity=config.masking.opacity,
        blur_radius=config.masking.blur_radius,
        pixelate_blocks=config.masking.pixelate_blocks,
        sensitivity_deg=config.geometry.gaze_tolerance_deg,
        trigger_ms=config.policy.trigger_ms,
        release_ms=config.policy.release_ms,
        camera_index=config.camera.device_index,
    )


def masking_config_from_snapshot(snapshot: UiSnapshot) -> MaskingConfig:
    """Masking config reflecting the user's CURRENT (runtime) settings.

    The overlay renderer is built from the snapshot — not the startup config —
    so strategy/parameter edits in the settings window take effect live.
    """
    return MaskingConfig(
        strategy=snapshot.masking_strategy,  # type: ignore[arg-type]
        opacity=snapshot.opacity,
        blur_radius=snapshot.blur_radius,
        pixelate_blocks=snapshot.pixelate_blocks,
    )


def app_config_from_snapshot(config: AppConfig, snapshot: UiSnapshot) -> AppConfig:
    """Full config reflecting the user's CURRENT settings, for the pipeline worker.

    Same principle as :func:`masking_config_from_snapshot`, extended to detection:
    the worker must see what the user set (restored at startup, or edited since),
    not the startup TOML. Every override goes through a *validated* pydantic
    construction, so the controller's clamps and the config bounds stay aligned.
    """
    return config.model_copy(
        update={
            "camera": CameraConfig(
                **{**config.camera.model_dump(), "device_index": snapshot.camera_index}
            ),
            "geometry": GeometryConfig(
                **{**config.geometry.model_dump(), "gaze_tolerance_deg": snapshot.sensitivity_deg}
            ),
            "policy": PolicyConfig(trigger_ms=snapshot.trigger_ms, release_ms=snapshot.release_ms),
            "masking": masking_config_from_snapshot(snapshot),
        }
    )


class _PipelineWorker(QThread):  # pragma: no cover - requires camera/model
    """Runs the capture->decision loop off the UI thread, emitting results."""

    produced = Signal(object)  # FrameResult
    frame_produced = Signal(object)  # QImage (annotated preview frame)
    failed = Signal(str)  # CameraError value

    def __init__(self, config: AppConfig, model_path: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._model_path = model_path
        self._stop = False
        self._preview = False

    def stop(self) -> None:
        self._stop = True

    def set_preview(self, enabled: bool) -> None:
        self._preview = bool(enabled)

    def _emit_detail(self, detail: object) -> None:
        # Only paint a frame when the preview is on (CPU + privacy: opt-in display).
        if not self._preview:
            return
        from privacy_guard.ui.preview import annotate_frame

        qimg = annotate_frame(
            detail.image, detail.observations, detail.looking, detail.primary_index
        )
        self.frame_produced.emit(qimg)

    def _on_source_health(self, health: object) -> None:
        # Called from this worker thread by the resilient source. Only the loss is
        # reported: the next successful frame clears the banner by itself
        # (apply_frame_result resets error_kind on every produced result).
        from privacy_guard.capture import SourceHealth

        if health is SourceHealth.RECONNECTING:
            self.failed.emit(CameraError.RECONNECTING.value)

    def run(self) -> None:
        from pathlib import Path

        from privacy_guard.app import PrivacyGuardPipeline
        from privacy_guard.capture import ResilientFrameSource, WebcamFrameSource
        from privacy_guard.overlay import RecordingRenderer
        from privacy_guard.vision import MediaPipeFaceDetector, mediapipe_available

        if not mediapipe_available() or not Path(self._model_path).is_file():
            self.failed.emit(CameraError.MODEL_UNAVAILABLE.value)
            return
        try:
            webcam = WebcamFrameSource(self._config.camera.device_index)
            if not webcam.is_available:
                self.failed.emit(CameraError.NO_CAMERA.value)
                return
            detector = MediaPipeFaceDetector(
                model_path=self._model_path,
                max_faces=self._config.detection.max_faces,
                min_confidence=self._config.detection.min_detection_confidence,
            )
        except RuntimeError as exc:
            logger.warning("Capture/detector init failed: %s", exc)
            self.failed.emit(CameraError.NO_CAMERA.value)
            return

        # Survive suspend/resume and unplugs: failed reads trigger an automatic
        # close/reopen with backoff instead of killing this loop (M-R1). The
        # wrapper polls our stop flag, so pausing/quitting stays responsive.
        source = ResilientFrameSource(
            webcam,
            reopen=lambda: WebcamFrameSource(self._config.camera.device_index),
            should_abort=lambda: self._stop,
            on_health=self._on_source_health,
        )

        # The worker decides; the UI thread paints the overlay from the emitted result.
        # The optional detail hook builds the preview frame only when preview is on.
        pipeline = PrivacyGuardPipeline(
            self._config,
            source,
            detector,
            RecordingRenderer(),
            on_result=self.produced.emit,
            on_step_detail=self._emit_detail,
        )
        try:
            while not self._stop:
                if pipeline.step() is None:
                    # With the resilient source this only happens on stop/close;
                    # the guard keeps a real exhaustion visible rather than silent.
                    if not self._stop:
                        self.failed.emit(CameraError.DISCONNECTED.value)
                    break
                self.msleep(int(1000 / max(1, self._config.camera.target_fps)))
        finally:
            pipeline.close()


class CoreController(AppController):
    """Live controller: starts/stops the worker and maps results to the snapshot."""

    # Annotated preview frame (QImage), forwarded to the camera view-model on the UI
    # thread. Emitted only while the preview is enabled.
    frame_ready = Signal(object)

    def __init__(
        self,
        config: AppConfig,
        model_path: str,
        parent: QObject | None = None,
        fade_ms: int = 120,
    ) -> None:
        """Initialise paused, mirroring ``config``; no hardware touched yet.

        ``fade_ms`` is the veil->frame crossfade for the overlay; the shell
        passes 0 when the user prefers reduced motion.
        """
        super().__init__(snapshot_from_config(config), parent)
        self._config = config
        self._model_path = model_path
        self._fade_ms = fade_ms
        self._worker: _PipelineWorker | None = None
        self._overlay: object | None = None
        # Detection-threshold edits restart the worker (the pipeline reads them at
        # construction). Debounced so dragging a slider triggers ONE restart, not
        # one per tick — reopening the camera + MediaPipe is expensive.
        self._restart_timer = QTimer(self)
        self._restart_timer.setSingleShot(True)
        self._restart_timer.setInterval(800)
        self._restart_timer.timeout.connect(self._apply_detection_settings)

    # ---- result -> snapshot (hardware-free, unit-tested) ----------------- #
    def apply_frame_result(self, result: FrameResult) -> None:
        """Map one pipeline :class:`FrameResult` onto the UI snapshot + overlay."""
        if self._overlay is not None:
            self._overlay.set_masked(result.is_masked)  # type: ignore[attr-defined]
        self._update(
            running=True,
            error_kind=None,
            camera_active=True,
            faces_count=result.n_faces,
            is_masked=result.is_masked,
            policy_state=result.state,
        )

    def report_worker_error(self, error_value: str) -> None:
        """Map a worker error code to the snapshot's error state."""
        self._update(error_kind=CameraError(error_value), camera_active=False)

    # ---- lifecycle (hardware; excluded from coverage) ------------------- #
    def enable(self) -> None:  # pragma: no cover - requires camera/model/display
        """Resume watching and start the capture/decision worker."""
        super().enable()
        self._start_worker()

    def pause(self) -> None:  # pragma: no cover - requires display
        """Pause watching, stop the worker, and lift the overlay."""
        super().pause()
        self._stop_worker()

    def set_preview_enabled(self, enabled: bool) -> None:  # pragma: no cover - hardware
        """Toggle the live preview, starting the worker if needed."""
        super().set_preview_enabled(enabled)  # updates snapshot (may set running=True)
        if self._snap.running and self._worker is None:
            self._start_worker()
        if self._worker is not None:
            self._worker.set_preview(self._snap.preview_enabled)

    def _start_worker(self) -> None:  # pragma: no cover - hardware
        from privacy_guard.overlay import qt_available

        self._stop_worker()
        if qt_available() and self._overlay is None:
            self._rebuild_overlay()
        # The worker gets the snapshot-merged config, so persisted/edited settings
        # actually reach the pipeline (the startup TOML is only the base).
        worker_config = app_config_from_snapshot(self._config, self._snap)
        self._worker = _PipelineWorker(worker_config, self._model_path, self)
        self._worker.set_preview(self._snap.preview_enabled)
        self._worker.produced.connect(self.apply_frame_result)
        self._worker.frame_produced.connect(self.frame_ready)
        self._worker.failed.connect(self.report_worker_error)
        self._worker.start()

    def _rebuild_overlay(self) -> None:  # pragma: no cover - display
        """(Re)build the overlay renderer from the CURRENT snapshot settings."""
        from privacy_guard.overlay import build_qt_masking_renderer, qt_available

        if not qt_available():
            return
        was_masked = False
        if self._overlay is not None:
            was_masked = bool(self._overlay.is_masked)  # type: ignore[attr-defined]
            self._overlay.close()  # type: ignore[attr-defined]
        self._overlay = build_qt_masking_renderer(
            masking_config_from_snapshot(self._snap), fade_ms=self._fade_ms
        )
        if was_masked:
            self._overlay.set_masked(True)  # type: ignore[attr-defined]

    # ---- detection edits reach the pipeline via a debounced worker restart -- #
    def _apply_detection_settings(self) -> None:  # pragma: no cover - hardware
        """Restart the worker so new detection thresholds reach the pipeline.

        The masking stays engaged/level through the restart only via the policy
        re-deciding; the brief detection gap is acceptable because this only
        happens while the user is at the controls, adjusting sliders.
        """
        if self._worker is not None and self._snap.running:
            self._start_worker()

    def _schedule_worker_restart(self) -> None:  # pragma: no cover - hardware
        if self._worker is not None:
            self._restart_timer.start()

    def set_sensitivity_deg(self, deg: float) -> None:  # pragma: no cover - hardware
        """Change the gaze tolerance and (debounced) apply it to the live pipeline."""
        super().set_sensitivity_deg(deg)
        self._schedule_worker_restart()

    def set_trigger_ms(self, ms: int) -> None:  # pragma: no cover - hardware
        """Change the trigger delay and (debounced) apply it to the live pipeline."""
        super().set_trigger_ms(ms)
        self._schedule_worker_restart()

    def set_release_ms(self, ms: int) -> None:  # pragma: no cover - hardware
        """Change the release delay and (debounced) apply it to the live pipeline."""
        super().set_release_ms(ms)
        self._schedule_worker_restart()

    # ---- masking edits take effect live on the overlay ------------------- #
    def set_masking_strategy(self, strategy: str) -> None:  # pragma: no cover - display
        """Change the masking style and rebuild the live overlay accordingly."""
        super().set_masking_strategy(strategy)
        if self._overlay is not None:
            self._rebuild_overlay()

    def set_opacity(self, opacity: float) -> None:  # pragma: no cover - display
        """Change the veil opacity and rebuild the live overlay accordingly."""
        super().set_opacity(opacity)
        if self._overlay is not None:
            self._rebuild_overlay()

    def set_blur_radius(self, radius: int) -> None:  # pragma: no cover - display
        """Change the blur radius and rebuild the live overlay accordingly."""
        super().set_blur_radius(radius)
        if self._overlay is not None:
            self._rebuild_overlay()

    def set_pixelate_blocks(self, blocks: int) -> None:  # pragma: no cover - display
        """Change the pixelation block count and rebuild the live overlay accordingly."""
        super().set_pixelate_blocks(blocks)
        if self._overlay is not None:
            self._rebuild_overlay()

    def _stop_worker(self) -> None:  # pragma: no cover - hardware
        self._restart_timer.stop()
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait(2000)
            self._worker = None
        if self._overlay is not None:
            self._overlay.set_masked(False)  # type: ignore[attr-defined]

    def shutdown(self) -> None:  # pragma: no cover - hardware
        """Stop the worker and release the overlay (called on app quit)."""
        self._stop_worker()
        if self._overlay is not None:
            self._overlay.close()  # type: ignore[attr-defined]
            self._overlay = None
