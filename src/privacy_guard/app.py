"""Pipeline orchestration: capture -> vision -> geometry -> tracking -> policy -> overlay.

The :class:`PrivacyGuardPipeline` is hardware-agnostic: it depends only on the
injectable :class:`FrameSource`, :class:`FaceDetector`, and :class:`Renderer`
interfaces, so the entire decision flow is testable headless. Per-frame results are
exposed via :class:`FrameResult` and an ``on_result`` callback (the observable hook
used by integration/system tests).

Honest scope: this detects an observer with the camera and masks content. It cannot
change how light leaves the screen, so it reduces risk rather than guaranteeing
privacy. See ``docs/LIMITATIONS.md``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass

from privacy_guard.capture import FrameSource, SyntheticFrameSource
from privacy_guard.config import AppConfig, load_config
from privacy_guard.geometry import (
    ScreenModel,
    gaze_points_at_screen,
    gaze_vector,
    select_primary_user,
)
from privacy_guard.overlay import RecordingRenderer, Renderer
from privacy_guard.policy import DecisionStateMachine, PolicyState
from privacy_guard.tracking import ExponentialSmoother
from privacy_guard.vision import FaceDetector, FaceObservation

logger = logging.getLogger("privacy_guard")


@dataclass(frozen=True)
class FrameResult:
    """Observable outcome of processing a single frame."""

    index: int
    timestamp_ms: float
    n_faces: int
    primary_index: int | None
    observer_present: bool
    smoothed_confidence: float
    state: PolicyState
    is_masked: bool


@dataclass(frozen=True)
class StepDetail:
    """Transient per-frame detail for an *optional* diagnostic/preview consumer.

    Carries the raw frame image plus the decision context the core already computed
    (so a preview can draw boxes/tags without re-implementing any logic). It is passed
    to the ``on_step_detail`` callback and **never retained** by the pipeline — the
    image lives only for the duration of the call, preserving the no-frame-accumulation
    guarantee.
    """

    image: object  # the BGR frame (numpy array); typed loosely to avoid a hard dep here
    observations: list[FaceObservation]
    looking: list[bool]  # per-face: does this face's gaze hit the screen?
    primary_index: int | None
    result: FrameResult


class PrivacyGuardPipeline:
    """Wires the pure decision modules to injectable hardware adapters."""

    def __init__(
        self,
        config: AppConfig,
        source: FrameSource,
        detector: FaceDetector,
        renderer: Renderer,
        on_result: Callable[[FrameResult], None] | None = None,
        on_step_detail: Callable[[StepDetail], None] | None = None,
    ) -> None:
        """Build the pipeline from config and injected adapters.

        ``on_step_detail`` is an optional diagnostic hook (e.g. a live preview). When
        ``None`` (the default) there is zero extra work and nothing extra is retained.
        """
        self.config = config
        self.source = source
        self.detector = detector
        self.renderer = renderer
        self._on_result = on_result
        self._on_step_detail = on_step_detail

        self._screen = ScreenModel(
            width_mm=config.geometry.screen_width_mm,
            height_mm=config.geometry.screen_height_mm,
            camera_above_mm=config.geometry.camera_above_screen_mm,
        )
        self._tolerance = config.geometry.gaze_tolerance_deg
        self._smoother = ExponentialSmoother(config.tracking.smoothing_alpha)
        self._policy = DecisionStateMachine.from_config(config.policy)
        self.last_result: FrameResult | None = None

    @property
    def state(self) -> PolicyState:
        """Current decision state."""
        return self._policy.state

    def _observer_is_looking(self, obs: FaceObservation) -> bool:
        """Whether a (non-primary) face's gaze points at the screen."""
        if not obs.gaze_estimable:
            return False
        gaze = gaze_vector(obs.yaw_deg, obs.pitch_deg)
        return gaze_points_at_screen(obs.position_mm, gaze, self._screen, self._tolerance)

    def _detect_observer(
        self, observations: list[FaceObservation]
    ) -> tuple[bool, int | None, list[bool]]:
        """Return ``(observer_present, primary_index, looking)`` for one frame.

        ``looking[i]`` is whether face ``i``'s gaze hits the screen (independent of who
        is the primary user); the preview uses it to tag faces.
        """
        if not observations:
            return False, None, []
        looking = [self._observer_is_looking(obs) for obs in observations]
        candidates = [o.to_candidate() for o in observations]
        primary_index = select_primary_user(
            candidates,
            centrality_weight=self.config.primary_user.centrality_weight,
            size_weight=self.config.primary_user.size_weight,
        )
        observer_present = any(hit for i, hit in enumerate(looking) if i != primary_index)
        return observer_present, primary_index, looking

    def step(self) -> FrameResult | None:
        """Process the next frame; return its :class:`FrameResult` or ``None`` if exhausted."""
        frame = self.source.read()
        if frame is None:
            return None

        observations = self.detector.detect(frame)
        observer_raw, primary_index, looking = self._detect_observer(observations)

        # Tracking smooths single-frame jitter; policy adds the time hysteresis.
        # Note: this EMA adds a short warm-up before `observer_present` flips true,
        # so the effective masking latency is `trigger_ms` PLUS ~1-2 frames (see
        # docs/LIMITATIONS.md). Set tracking.smoothing_alpha = 1.0 to disable it.
        confidence = float(self._smoother.update(1.0 if observer_raw else 0.0))
        observer_present = confidence >= 0.5

        state = self._policy.update(observer_present, frame.timestamp_ms)
        self.renderer.set_masked(self._policy.is_masked)

        result = FrameResult(
            index=frame.index,
            timestamp_ms=frame.timestamp_ms,
            n_faces=len(observations),
            primary_index=primary_index,
            observer_present=observer_present,
            smoothed_confidence=confidence,
            state=state,
            is_masked=self._policy.is_masked,
        )
        self.last_result = result
        if self._on_result is not None:
            self._on_result(result)
        if self._on_step_detail is not None:
            # Transient: the image is borrowed for this call only, never retained.
            self._on_step_detail(
                StepDetail(
                    image=frame.image,
                    observations=observations,
                    looking=looking,
                    primary_index=primary_index,
                    result=result,
                )
            )
        return result

    def run(self, max_frames: int | None = None) -> list[FrameResult]:
        """Run until the source is exhausted (or ``max_frames`` processed)."""
        results: list[FrameResult] = []
        while max_frames is None or len(results) < max_frames:
            result = self.step()
            if result is None:
                break
            results.append(result)
        return results

    def close(self) -> None:
        """Release all adapter resources."""
        self.source.close()
        self.detector.close()
        self.renderer.close()


def build_runtime_components(
    config: AppConfig,
) -> tuple[FrameSource, FaceDetector, Renderer]:  # pragma: no cover - requires hardware/libs
    """Build real adapters, degrading gracefully when hardware/libraries are absent.

    Returns a synthetic source + null detector + recording renderer in degraded mode
    so the application never crashes; it simply cannot detect observers until the
    camera and model are available.
    """
    from privacy_guard.capture import WebcamFrameSource, opencv_available
    from privacy_guard.overlay import build_qt_masking_renderer, qt_available
    from privacy_guard.vision import (
        MediaPipeFaceDetector,
        ScriptedFaceDetector,
        mediapipe_available,
    )

    source: FrameSource
    if config.camera.enabled and opencv_available():
        try:
            source = WebcamFrameSource(config.camera.device_index)
        except RuntimeError:
            logger.warning("Webcam unavailable; running without live capture.")
            source = SyntheticFrameSource(n_frames=0)
    else:
        logger.warning("Camera disabled or OpenCV missing; no live capture.")
        source = SyntheticFrameSource(n_frames=0)

    detector: FaceDetector
    if mediapipe_available() and config.detection.model_path:
        detector = MediaPipeFaceDetector(
            model_path=config.detection.model_path,
            max_faces=config.detection.max_faces,
            min_confidence=config.detection.min_detection_confidence,
        )
    else:
        logger.warning("MediaPipe/model unavailable; detector cannot see faces (degraded mode).")
        detector = ScriptedFaceDetector([])

    renderer: Renderer
    if qt_available():
        # veil -> opaque multi-screen veil; blur/pixelate -> freeze-frame stack
        # (one local capture at masking time, transformed off-thread). M-FP5.
        renderer = build_qt_masking_renderer(config.masking)
    else:
        logger.warning("PySide6 unavailable; using a headless recording renderer.")
        renderer = RecordingRenderer()

    return source, detector, renderer


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = argparse.ArgumentParser(description="Privacy Guard — anti shoulder-surfing overlay.")
    parser.add_argument("-c", "--config", help="Path to a TOML config file.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config(args.config) if args.config else AppConfig()

    try:  # pragma: no cover - requires hardware/libs
        source, detector, renderer = build_runtime_components(config)
    except RuntimeError as exc:  # pragma: no cover
        logger.error("Could not start: %s", exc)
        return 1

    pipeline = PrivacyGuardPipeline(config, source, detector, renderer)
    logger.info("Privacy Guard running. This reduces shoulder-surfing risk; it does not")
    logger.info("guarantee privacy (see docs/LIMITATIONS.md). Press Ctrl+C to stop.")
    try:  # pragma: no cover - long-running loop
        pipeline.run()
    except KeyboardInterrupt:  # pragma: no cover
        logger.info("Stopping.")
    finally:  # pragma: no cover
        pipeline.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
