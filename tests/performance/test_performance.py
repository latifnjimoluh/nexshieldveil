"""Performance tests: pipeline throughput (FPS) and detection->masking latency.

Marked ``performance``/``slow`` so they can be excluded from fast runs. Thresholds
are deliberately conservative to stay reliable in CI; the pure pipeline (scripted
detector) is far faster than these bounds.
"""

from __future__ import annotations

import time

import pytest

from privacy_guard.app import PrivacyGuardPipeline
from privacy_guard.capture import SyntheticFrameSource
from privacy_guard.config import AppConfig
from privacy_guard.overlay import RecordingRenderer
from privacy_guard.vision import ScriptedFaceDetector
from tests.conftest import observer_looking, primary_user

pytestmark = [pytest.mark.performance, pytest.mark.slow]

LATENCY_BUDGET_MS = 200.0
MIN_FPS = 30.0


def _build(n: int) -> PrivacyGuardPipeline:
    script = [[primary_user(), observer_looking()] for _ in range(n)]
    source = SyntheticFrameSource(width=640, height=480, n_frames=n, fps=30.0)
    return PrivacyGuardPipeline(
        AppConfig(), source, ScriptedFaceDetector(script), RecordingRenderer()
    )


def test_pipeline_throughput_meets_min_fps() -> None:
    n = 300
    pipeline = _build(n)
    start = time.perf_counter()
    results = pipeline.run()
    elapsed = time.perf_counter() - start
    assert len(results) == n
    fps = n / elapsed
    assert fps >= MIN_FPS, f"throughput {fps:.1f} fps below {MIN_FPS} fps"


def test_per_frame_processing_latency_under_budget() -> None:
    pipeline = _build(200)
    worst = 0.0
    while True:
        start = time.perf_counter()
        result = pipeline.step()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if result is None:
            break
        worst = max(worst, elapsed_ms)
    assert worst < LATENCY_BUDGET_MS, f"worst per-frame latency {worst:.2f} ms exceeds budget"


def test_detection_to_mask_compute_latency() -> None:
    # Compute latency from an observer-present frame to the renderer being told to
    # mask. With a zero trigger this collapses to pure per-step compute time.
    cfg = AppConfig(policy={"trigger_ms": 0, "release_ms": 0})
    source = SyntheticFrameSource(n_frames=1, fps=30.0)
    detector = ScriptedFaceDetector([[primary_user(), observer_looking()]])
    renderer = RecordingRenderer()
    pipeline = PrivacyGuardPipeline(cfg, source, detector, renderer)

    start = time.perf_counter()
    result = pipeline.step()
    latency_ms = (time.perf_counter() - start) * 1000.0
    assert result is not None
    assert result.is_masked is True
    assert latency_ms < LATENCY_BUDGET_MS
