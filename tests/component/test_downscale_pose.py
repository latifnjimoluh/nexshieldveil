"""Downscaling must not move the head pose (AM-12).

``DownscaledFrameSource`` only exists if shrinking the frame is *free* in terms of
geometry. It is, because ``_solve_head_pose`` derives both the focal length and the
principal point from the frame size, so scaling the image is a pure change of pixel
units. This test proves that claim on the real ``solvePnP`` rather than leaving it
as a comment.

Requires OpenCV (the ``vision`` extra); skipped otherwise, like the other capture
component tests.
"""

from __future__ import annotations

import numpy as np
import pytest

pytestmark = pytest.mark.component

cv2 = pytest.importorskip("cv2", reason="OpenCV not installed")

from privacy_guard.vision.mediapipe_detector import MediaPipeFaceDetector  # noqa: E402

# A plausible set of the six landmarks used for solvePnP, in pixels, for a face
# turned slightly to one side in a 1280x720 frame.
_FULL_W, _FULL_H = 1280, 720
_IMAGE_POINTS = np.array(
    [
        [664.0, 372.0],  # nose tip
        [658.0, 470.0],  # chin
        [590.0, 330.0],  # left eye outer corner
        [726.0, 336.0],  # right eye outer corner
        [614.0, 432.0],  # left mouth corner
        [706.0, 436.0],  # right mouth corner
    ],
    dtype=np.float64,
)


@pytest.mark.parametrize("scale", [0.5, 0.25])
def test_head_pose_is_invariant_under_frame_scaling(scale: float) -> None:
    solve = MediaPipeFaceDetector._solve_head_pose
    yaw_full, pitch_full, position_full = solve(_IMAGE_POINTS, _FULL_W, _FULL_H)
    yaw_small, pitch_small, position_small = solve(
        _IMAGE_POINTS * scale, round(_FULL_W * scale), round(_FULL_H * scale)
    )

    # Not bit-identical, and it never will be: SOLVEPNP_ITERATIVE refines
    # numerically, and rounding the scaled frame to whole pixels perturbs the
    # principal point slightly. The measured drift is ~4e-6 degrees — six orders
    # of magnitude below the 1.5-3 degrees of error a webcam gaze estimate
    # carries anyway (docs/LIMITATIONS.md), so the tolerances below are the
    # honest statement of "unchanged", not a weakened assertion.
    assert yaw_small == pytest.approx(yaw_full, abs=1e-3)
    assert pitch_small == pytest.approx(pitch_full, abs=1e-3)
    # The recovered translation is in millimetres and must not drift either:
    # a shifted distance would move the gaze ray's origin and change the decision.
    assert position_small == pytest.approx(position_full, rel=1e-4)


def test_the_scaling_actually_changed_the_inputs() -> None:
    # Anti-tautology: make sure the "invariance" above is not comparing two
    # identical computations.
    assert not np.allclose(_IMAGE_POINTS, _IMAGE_POINTS * 0.5)
