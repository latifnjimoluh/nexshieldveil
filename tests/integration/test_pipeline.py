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
from privacy_guard.policy import MaskReason, PolicyState
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


def test_smoothing_alpha_one_removes_ema_warmup() -> None:
    # FUNC-1: the EMA adds ~1 frame of warm-up before observer_present flips, so the
    # effective masking latency exceeds trigger_ms. alpha=1.0 (passthrough) removes it.
    intro = 10
    script = [[primary_user()] for _ in range(intro)]
    script += [[primary_user(), observer_looking()] for _ in range(20)]

    smoothed, _ = run_script(script, AppConfig(tracking={"smoothing_alpha": 0.4}))
    instant, _ = run_script(script, AppConfig(tracking={"smoothing_alpha": 1.0}))

    first_smoothed = next(i for i, r in enumerate(smoothed) if r.is_masked)
    first_instant = next(i for i, r in enumerate(instant) if r.is_masked)

    # trigger_ms=400 at 20fps = 8 frames after the observer appears (frame 10).
    assert first_instant == intro + 8
    # The default EMA delays masking by at least one extra frame.
    assert first_smoothed > first_instant


def test_on_step_detail_hook_exposes_frame_and_looking() -> None:
    from privacy_guard.app import StepDetail

    details: list[StepDetail] = []
    cfg = AppConfig()
    source = SyntheticFrameSource(n_frames=3, fps=FPS)
    detector = ScriptedFaceDetector([[primary_user(), observer_looking()] for _ in range(3)])
    pipeline = PrivacyGuardPipeline(
        cfg, source, detector, RecordingRenderer(), on_step_detail=details.append
    )
    pipeline.run()

    assert len(details) == 3
    d = details[0]
    # The central/large face is the primary; the off-centre observer is looking.
    assert d.primary_index == 0
    assert d.looking[1] is True
    assert len(d.observations) == 2
    assert d.image is not None  # the raw frame is handed over for drawing
    assert d.result is details[0].result  # the FrameResult is attached


def test_on_step_detail_absent_by_default() -> None:
    # No hook -> the optional path is simply never taken (zero overhead).
    cfg = AppConfig()
    source = SyntheticFrameSource(n_frames=2, fps=FPS)
    detector = ScriptedFaceDetector([[primary_user()] for _ in range(2)])
    pipeline = PrivacyGuardPipeline(cfg, source, detector, RecordingRenderer())
    assert pipeline.run()  # runs fine with on_step_detail=None


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


# --------------------------------------------------------------------------- #
# AM-8: two people side by side must not make the decision oscillate
# --------------------------------------------------------------------------- #
def _twin(center_x: float, size: float, yaw_deg: float) -> FaceObservation:
    """One of two people sitting side by side, equidistant from the camera."""
    return FaceObservation(
        center_x=center_x,
        center_y=0.5,
        size=size,
        position_mm=np.array([(center_x - 0.5) * 800.0, -150.0, 600.0]),
        yaw_deg=yaw_deg,
        pitch_deg=0.0,
    )


def test_two_tied_faces_do_not_flip_the_masking_decision() -> None:
    # Both look at the screen and are nearly tied on score, with the tiny size
    # difference changing sign every frame (breathing, leaning). Whoever holds
    # the "primary user" title has their gaze ignored — so a title that flips
    # makes the veil flicker on and off. It must not.
    jitter = [0.002, -0.002, 0.001, -0.001, 0.003, -0.003] * 5
    script = [[_twin(0.45, 0.20 + d, 0.0), _twin(0.55, 0.20 - d, 0.0)] for d in jitter]
    results, _ = run_script(script)

    primaries = {r.primary_index for r in results}
    assert len(primaries) == 1, f"the primary user changed hands: {primaries}"
    # ...and with a stable primary, the other one is consistently an observer.
    assert all(r.observer_present for r in results[1:])


def test_a_real_move_still_transfers_the_primary_title() -> None:
    # Hysteresis must not freeze the election: someone who genuinely takes the
    # front seat (much closer, much more central) does become the primary user.
    script = [[_twin(0.5, 0.30, 0.0), _twin(0.9, 0.05, 70.0)] for _ in range(4)]
    script += [[_twin(0.5, 0.05, 0.0), _twin(0.55, 0.45, 70.0)] for _ in range(8)]
    results, _ = run_script(script)

    assert results[0].primary_index == 0
    assert results[-1].primary_index == 1


# --------------------------------------------------------------------------- #
# AM-7: the walk-away lock, end to end through the real pipeline
# --------------------------------------------------------------------------- #
def _absence_config(absence_ms: int) -> AppConfig:
    cfg = AppConfig()
    return cfg.model_copy(
        update={"policy": cfg.policy.model_copy(update={"absence_ms": absence_ms})}
    )


def test_an_empty_frame_alone_never_masks_by_default() -> None:
    # Nobody in front of the camera, walk-away lock off: the screen stays visible.
    results, renderer = run_script([[] for _ in range(40)])
    assert not any(r.is_masked for r in results)
    assert renderer.transitions == []  # the veil never even moved


def test_walking_away_masks_when_the_lock_is_enabled() -> None:
    # 20 fps: 40 frames = 2 s of absence, past a 1 s lock.
    results, _ = run_script([[] for _ in range(40)], _absence_config(1_000))
    assert results[-1].is_masked is True
    assert results[-1].mask_reason is MaskReason.ABSENCE
    # ...and not before the delay: the first second is still clear.
    assert results[10].is_masked is False


def test_the_lone_stranger_case_the_lock_exists_for() -> None:
    # The scenario the observer path structurally cannot catch: the user leaves,
    # a stranger sits down. With one face in frame that face IS the primary user,
    # so its gaze is ignored — only the absence that preceded it masks the screen.
    script: list[list[FaceObservation]] = [[primary_user()] for _ in range(5)]
    script += [[] for _ in range(40)]  # the user walks away (2 s)
    script += [[observer_looking()] for _ in range(10)]  # a stranger sits down
    results, _ = run_script(script, _absence_config(1_000))

    assert results[4].is_masked is False  # user present: clear
    assert results[44].is_masked is True  # absence: masked
    assert results[44].mask_reason is MaskReason.ABSENCE
    # The stranger's arrival does not instantly reveal the screen: the release
    # hysteresis still has to elapse.
    assert results[45].is_masked is True
