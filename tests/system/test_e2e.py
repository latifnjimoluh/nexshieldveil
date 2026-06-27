"""System / end-to-end test: drive the assembled app headless and assert via hooks.

This treats the pipeline as a black box, observing only the public Renderer hook,
exactly as a real overlay would be driven — no real camera or display involved.
"""

from __future__ import annotations

import pytest

from privacy_guard.app import PrivacyGuardPipeline
from privacy_guard.capture import SyntheticFrameSource
from privacy_guard.config import AppConfig
from privacy_guard.overlay import RecordingRenderer
from privacy_guard.vision import ScriptedFaceDetector
from tests.conftest import FPS, session_script

pytestmark = pytest.mark.system


def test_full_session_engages_then_lifts_masking() -> None:
    script = session_script(intro_clear=10, observer_frames=16, outro_clear=30)
    source = SyntheticFrameSource(n_frames=len(script), fps=FPS)
    detector = ScriptedFaceDetector(script)
    renderer = RecordingRenderer()

    pipeline = PrivacyGuardPipeline(AppConfig(), source, detector, renderer)
    transitions_seen: list[tuple[int, bool]] = []
    pipeline._on_result = lambda r: transitions_seen.append((r.index, r.is_masked))
    pipeline.run()
    pipeline.close()

    # Exactly one engage + one lift over the session.
    assert renderer.transitions == [True, False]
    assert renderer.is_masked is False

    # Masking only happened during/after the observer window, never during the intro.
    masked_indices = [i for i, masked in transitions_seen if masked]
    assert min(masked_indices) >= 10  # not during the 10-frame solo intro
    assert max(masked_indices) < len(script)


def test_app_run_is_idempotent_after_exhaustion() -> None:
    script = session_script(intro_clear=2, observer_frames=2, outro_clear=2)
    source = SyntheticFrameSource(n_frames=len(script), fps=FPS)
    detector = ScriptedFaceDetector(script)
    pipeline = PrivacyGuardPipeline(AppConfig(), source, detector, RecordingRenderer())
    first = pipeline.run()
    second = pipeline.run()  # source exhausted -> no more frames
    assert len(first) == len(script)
    assert second == []


def test_degraded_empty_source_runs_without_error() -> None:
    # Simulates the no-camera degraded mode: zero frames, no crash, stays clear.
    pipeline = PrivacyGuardPipeline(
        AppConfig(),
        SyntheticFrameSource(n_frames=0),
        ScriptedFaceDetector([]),
        RecordingRenderer(),
    )
    assert pipeline.run() == []
    assert pipeline.last_result is None
