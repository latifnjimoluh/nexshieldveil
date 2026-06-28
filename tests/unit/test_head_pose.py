"""Unit tests for the pure head-pose helpers (no OpenCV/MediaPipe needed).

These lock the pitch normalization that makes real solvePnP output line up with the
gaze convention: without it, a user facing the camera reads pitch ~+-170 deg and is
wrongly classified as "not looking at the screen".
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from privacy_guard.geometry import gaze_vector
from privacy_guard.vision.mediapipe_detector import _wrap_pitch_deg

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0.0, 0.0),
        (10.0, 10.0),
        (-10.0, -10.0),
        (170.0, -10.0),  # facing camera: solvePnP reads ~+170 -> wrapped to ~-10
        (-170.0, 10.0),
        (180.0, 0.0),  # a full half-turn folds back to 0
        (89.0, 89.0),
    ],
)
def test_wrap_pitch_brings_forward_facing_near_zero(raw: float, expected: float) -> None:
    assert _wrap_pitch_deg(raw) == pytest.approx(expected, abs=1e-9)


def test_wrap_pitch_is_idempotent_in_range() -> None:
    for p in (-89.9, -45.0, 0.0, 45.0, 89.9):
        assert _wrap_pitch_deg(p) == pytest.approx(p, abs=1e-9)


def test_wrap_always_in_half_open_range() -> None:
    for raw in range(-360, 361, 7):
        assert -90.0 <= _wrap_pitch_deg(float(raw)) < 90.0


def test_wrapped_pitch_makes_forward_gaze_point_into_screen() -> None:
    # The actual bug: raw pitch ~+170 made gaze z positive (away from screen). After
    # wrapping, gaze must point toward the screen plane (z < 0) for a forward face.
    raw_pitch, yaw = 170.8, 3.5  # medians observed on real hardware
    bad = gaze_vector(yaw, raw_pitch)
    good = gaze_vector(yaw, _wrap_pitch_deg(raw_pitch))
    assert bad[2] > 0.0  # demonstrates the original defect (points away)
    assert good[2] < 0.0  # fixed: points into the screen
    assert math.isclose(float(np.linalg.norm(good)), 1.0, abs_tol=1e-9)
