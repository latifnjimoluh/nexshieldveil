"""Deterministic integration tests of the full pipeline (no hardware).

These exercise the real geometry/tracking/policy/masking code paths via a
SyntheticFrameSource and a ScriptedFaceDetector, proving the masking trigger and
hysteresis without a camera or MediaPipe.
"""

from __future__ import annotations

import numpy as np
import pytest

from privacy_guard.app import PrivacyGuardPipeline
from privacy_guard.capture import SyntheticFrameSource
from privacy_guard.config import AppConfig
from privacy_guard.overlay import RecordingRenderer
from privacy_guard.policy import PolicyState
from privacy_guard.vision import FaceObservation, ScriptedFaceDetector

pytestmark = pytest.mark.integration

FPS = 20.0  # 50 ms per frame


def primary_user() -> FaceObservation:
    """Central, large face = primary user (its gaze is ignored)."""
    return FaceObservation(
        center_x=0.5,
        center_y=0.5,
        size=0.30,
        position_mm=np.array([0.0, -150.0, 500.0]),
        yaw_deg=0.0,
        pitch_deg=0.0,
    )


def observer_looking() -> FaceObservation:
    """Off-centre face positioned so a straight gaze lands on the screen."""
    return FaceObservation(
        center_x=0.85,
        center_y=0.45,
        size=0.08,
        position_mm=np.array([200.0, -150.0, 600.0]),
        yaw_deg=0.0,  # gaze (0,0,-1) hits the screen plane within bounds
        pitch_deg=0.0,
    )


def observer_looking_away() -> FaceObservation:
    """Off-centre face turned far to the side: not looking at the screen."""
    return FaceObservation(
        center_x=0.85,
        center_y=0.45,
        size=0.08,
        position_mm=np.array([200.0, -150.0, 600.0]),
        yaw_deg=70.0,
        pitch_deg=0.0,
    )


def run_script(script: list[list[FaceObservation]], config: AppConfig | None = None):
    cfg = config or AppConfig()
    source = SyntheticFrameSource(n_frames=len(script), fps=FPS)
    detector = ScriptedFaceDetector(script)
    renderer = RecordingRenderer()
    pipeline = PrivacyGuardPipeline(cfg, source, detector, renderer)
    results = pipeline.run()
    return results, renderer


def test_sustained_observer_triggers_mask_then_clears_after_absence() -> None:
    # 16 frames with an observer looking (16*50 = 800 ms), then 30 frames clear.
    script = [[primary_user(), observer_looking()] for _ in range(16)]
    script += [[primary_user()] for _ in range(30)]
    results, renderer = run_script(script)

    masked_flags = [r.is_masked for r in results]
    assert any(masked_flags), "observer looking should engage masking"

    # Masking engages within ~9 frames of the observer appearing (trigger 400 ms).
    first_masked = next(i for i, m in enumerate(masked_flags) if m)
    assert first_masked <= 9

    # By the end (well past the 800 ms release window) it has cleared again.
    assert results[-1].state is PolicyState.CLEAR
    assert results[-1].is_masked is False
    assert renderer.is_masked is False
    assert renderer.mask_engaged_count == 1


def test_only_primary_user_never_masks() -> None:
    script = [[primary_user()] for _ in range(40)]
    results, renderer = run_script(script)
    assert all(r.state is PolicyState.CLEAR for r in results)
    assert not any(r.is_masked for r in results)
    assert renderer.transitions == []


def test_observer_not_looking_does_not_mask() -> None:
    script = [[primary_user(), observer_looking_away()] for _ in range(40)]
    results, _ = run_script(script)
    assert not any(r.is_masked for r in results)


def test_no_faces_stays_clear() -> None:
    script: list[list[FaceObservation]] = [[] for _ in range(20)]
    results, _ = run_script(script)
    assert all(r.state is PolicyState.CLEAR for r in results)
    assert all(r.primary_index is None for r in results)


def test_hysteresis_does_not_clear_before_release_delay() -> None:
    # Observer looks long enough to mask, then leaves; check it stays masked across
    # the first few absent frames (release delay not yet elapsed).
    config = AppConfig()  # trigger 400 ms, release 800 ms
    script = [[primary_user(), observer_looking()] for _ in range(16)]
    script += [[primary_user()] for _ in range(4)]  # only 200 ms of absence
    results, _ = run_script(script, config)
    # The last frame is within the release window -> still masked.
    assert results[-1].is_masked is True
    assert results[-1].state is PolicyState.MASKED


def test_brief_glance_below_trigger_never_masks() -> None:
    # Observer present for only 5 frames (250 ms < 400 ms trigger).
    script = [[primary_user(), observer_looking()] for _ in range(5)]
    script += [[primary_user()] for _ in range(10)]
    results, _ = run_script(script)
    assert not any(r.is_masked for r in results)


def test_on_result_hook_is_called_per_frame() -> None:
    seen: list[int] = []
    cfg = AppConfig()
    source = SyntheticFrameSource(n_frames=5, fps=FPS)
    detector = ScriptedFaceDetector([[primary_user()] for _ in range(5)])
    renderer = RecordingRenderer()
    pipeline = PrivacyGuardPipeline(
        cfg, source, detector, renderer, on_result=lambda r: seen.append(r.index)
    )
    pipeline.run()
    assert seen == [0, 1, 2, 3, 4]
    assert pipeline.last_result is not None
