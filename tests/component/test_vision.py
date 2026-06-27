"""Component tests for the vision module (scripted detector, MP degradation)."""

from __future__ import annotations

import numpy as np
import pytest

from privacy_guard.capture import SyntheticFrameSource
from privacy_guard.vision import (
    FaceObservation,
    MediaPipeFaceDetector,
    ScriptedFaceDetector,
    mediapipe_available,
)

pytestmark = pytest.mark.component


def _frame() -> object:
    return next(iter(SyntheticFrameSource(n_frames=1)))


def test_observation_to_candidate() -> None:
    obs = FaceObservation(center_x=0.4, center_y=0.6, size=0.1)
    cand = obs.to_candidate()
    assert (cand.center_x, cand.center_y, cand.size) == (0.4, 0.6, 0.1)


def test_observation_has_sane_defaults() -> None:
    obs = FaceObservation(center_x=0.5, center_y=0.5, size=0.1)
    assert obs.position_mm.shape == (3,)
    assert obs.position_mm[2] > 0  # in front of the camera
    assert obs.gaze_estimable is True


def test_scripted_detector_replays_script() -> None:
    frame = _frame()
    o1 = FaceObservation(center_x=0.5, center_y=0.5, size=0.2)
    o2 = FaceObservation(center_x=0.1, center_y=0.1, size=0.05)
    det = ScriptedFaceDetector([[o1], [o1, o2]])
    assert det.is_available
    assert det.detect(frame) == [o1]
    assert det.detect(frame) == [o1, o2]
    # Past the script: empty.
    assert det.detect(frame) == []


def test_scripted_detector_returns_independent_lists() -> None:
    frame = _frame()
    obs = FaceObservation(center_x=0.5, center_y=0.5, size=0.2)
    det = ScriptedFaceDetector([[obs]])
    result = det.detect(frame)
    result.append(obs)  # mutating the returned list must not corrupt the script
    assert det._script[0] == [obs]


@pytest.mark.skipif(
    mediapipe_available(), reason="MediaPipe present; degradation path not applicable"
)
def test_mediapipe_detector_degrades_without_deps() -> None:
    with pytest.raises(RuntimeError, match="MediaPipe"):
        MediaPipeFaceDetector(model_path="nonexistent.task")


def test_mediapipe_available_is_bool() -> None:
    assert isinstance(mediapipe_available(), bool)


def test_frame_image_is_uint8() -> None:
    frame = next(iter(SyntheticFrameSource(n_frames=1)))
    assert frame.image.dtype == np.uint8
    assert frame.image.ndim == 3
