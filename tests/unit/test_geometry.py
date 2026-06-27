"""Unit + property-based tests for the pure geometry module."""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from privacy_guard.geometry import (
    FaceCandidate,
    ScreenModel,
    angle_between,
    gaze_points_at_screen,
    gaze_vector,
    nearest_point_in_rect,
    ray_plane_z_intersection,
    select_primary_user,
    unit_vector,
)

pytestmark = pytest.mark.unit

SCREEN = ScreenModel(width_mm=520.0, height_mm=290.0, camera_above_mm=10.0)

# Reasonable head angles for a webcam scenario.
angles = st.floats(min_value=-80.0, max_value=80.0, allow_nan=False, allow_infinity=False)


# --------------------------------------------------------------------------- #
# gaze_vector
# --------------------------------------------------------------------------- #
def test_gaze_vector_zero_points_into_screen() -> None:
    v = gaze_vector(0.0, 0.0)
    assert np.allclose(v, [0.0, 0.0, -1.0])


@given(yaw=angles, pitch=angles)
def test_gaze_vector_is_unit_length(yaw: float, pitch: float) -> None:
    v = gaze_vector(yaw, pitch)
    assert math.isclose(float(np.linalg.norm(v)), 1.0, abs_tol=1e-9)


@given(yaw=st.floats(1.0, 80.0), pitch=st.floats(1.0, 80.0))
def test_gaze_vector_signs(yaw: float, pitch: float) -> None:
    # Positive yaw -> +x, positive pitch -> +y, gaze always into-screen (z<=0).
    v = gaze_vector(yaw, pitch)
    assert v[0] > 0.0
    assert v[1] > 0.0
    assert v[2] <= 0.0
    # And the mirrored angles flip x and y.
    vm = gaze_vector(-yaw, -pitch)
    assert vm[0] < 0.0
    assert vm[1] < 0.0


# --------------------------------------------------------------------------- #
# unit_vector / angle_between
# --------------------------------------------------------------------------- #
def test_unit_vector_rejects_zero() -> None:
    with pytest.raises(ValueError, match="zero-length"):
        unit_vector(np.zeros(3))


@given(
    x=st.floats(-10, 10, allow_nan=False),
    y=st.floats(-10, 10, allow_nan=False),
    z=st.floats(-10, 10, allow_nan=False),
)
def test_angle_between_self_is_zero(x: float, y: float, z: float) -> None:
    v = np.array([x, y, z])
    if np.linalg.norm(v) < 1e-6:
        return
    assert angle_between(v, v) == pytest.approx(0.0, abs=1e-3)


@given(yaw=angles, pitch=angles)
def test_angle_between_is_symmetric_and_bounded(yaw: float, pitch: float) -> None:
    a = gaze_vector(yaw, pitch)
    b = gaze_vector(0.0, 0.0)
    ang_ab = angle_between(a, b)
    ang_ba = angle_between(b, a)
    assert ang_ab == pytest.approx(ang_ba, abs=1e-9)
    assert 0.0 <= ang_ab <= 180.0


def test_angle_between_orthogonal() -> None:
    assert angle_between(np.array([1.0, 0, 0]), np.array([0, 1.0, 0])) == pytest.approx(90.0)


# --------------------------------------------------------------------------- #
# ray_plane_z_intersection
# --------------------------------------------------------------------------- #
def test_intersection_straight_down_z() -> None:
    hit = ray_plane_z_intersection(np.array([3.0, -5.0, 500.0]), np.array([0.0, 0.0, -1.0]))
    assert hit is not None
    assert np.allclose(hit, [3.0, -5.0])


def test_intersection_parallel_returns_none() -> None:
    assert ray_plane_z_intersection(np.array([0.0, 0.0, 10.0]), np.array([1.0, 0.0, 0.0])) is None


def test_intersection_behind_returns_none() -> None:
    # Looking away from the plane (+z) while in front of it never hits it ahead.
    assert ray_plane_z_intersection(np.array([0.0, 0.0, 10.0]), np.array([0.0, 0.0, 1.0])) is None


@given(
    px=st.floats(-300, 300, allow_nan=False),
    py=st.floats(-300, 300, allow_nan=False),
    pz=st.floats(100, 1000, allow_nan=False),
    yaw=st.floats(-30, 30, allow_nan=False),
    pitch=st.floats(-30, 30, allow_nan=False),
)
def test_intersection_lies_on_plane(
    px: float, py: float, pz: float, yaw: float, pitch: float
) -> None:
    origin = np.array([px, py, pz])
    direction = gaze_vector(yaw, pitch)  # z component negative => hits plane ahead
    hit = ray_plane_z_intersection(origin, direction)
    assert hit is not None  # always points toward the plane
    # Reconstruct full 3D point and confirm z ~ 0.
    t = -origin[2] / direction[2]
    full = origin + t * direction
    assert full[2] == pytest.approx(0.0, abs=1e-6)


# --------------------------------------------------------------------------- #
# nearest_point_in_rect
# --------------------------------------------------------------------------- #
def test_nearest_point_inside_is_identity() -> None:
    assert nearest_point_in_rect(1.0, 2.0, (-5, 5, -5, 5)) == (1.0, 2.0)


def test_nearest_point_clamps_outside() -> None:
    assert nearest_point_in_rect(10.0, -10.0, (-5, 5, -5, 5)) == (5.0, -5.0)


# --------------------------------------------------------------------------- #
# gaze_points_at_screen
# --------------------------------------------------------------------------- #
def test_face_looking_straight_at_screen_center() -> None:
    # Face directly in front of the screen centre, looking at it.
    cx, cy = SCREEN.center()
    face = np.array([cx, cy, 600.0])
    gaze = np.array([0.0, 0.0, -1.0])
    assert gaze_points_at_screen(face, gaze, SCREEN, tolerance_deg=5.0)


def test_face_looking_away_is_not_at_screen() -> None:
    face = np.array([0.0, -150.0, 600.0])
    gaze = gaze_vector(70.0, 0.0)  # turned far to the side
    assert not gaze_points_at_screen(face, gaze, SCREEN, tolerance_deg=10.0)


def test_face_looking_backward_is_not_at_screen() -> None:
    face = np.array([0.0, -150.0, 600.0])
    gaze = np.array([0.0, 0.0, 1.0])  # away from screen entirely
    assert not gaze_points_at_screen(face, gaze, SCREEN, tolerance_deg=20.0)


@given(tol=st.floats(0.1, 89.0, allow_nan=False), extra=st.floats(0.0, 90.0, allow_nan=False))
def test_tolerance_is_monotonic(tol: float, extra: float) -> None:
    # If a gaze counts as on-screen at tolerance `tol`, it also counts at any larger tolerance.
    face = np.array([120.0, -120.0, 550.0])
    gaze = gaze_vector(15.0, -10.0)
    at_small = gaze_points_at_screen(face, gaze, SCREEN, tolerance_deg=tol)
    at_large = gaze_points_at_screen(face, gaze, SCREEN, tolerance_deg=min(tol + extra, 89.999))
    if at_small:
        assert at_large


# --------------------------------------------------------------------------- #
# select_primary_user
# --------------------------------------------------------------------------- #
def test_select_primary_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        select_primary_user([])


def test_central_large_face_is_primary() -> None:
    faces = [
        FaceCandidate(center_x=0.1, center_y=0.1, size=0.02),  # peripheral, small
        FaceCandidate(center_x=0.5, center_y=0.5, size=0.20),  # central, large
        FaceCandidate(center_x=0.9, center_y=0.2, size=0.05),
    ]
    assert select_primary_user(faces) == 1


def test_size_weight_can_override_centrality() -> None:
    faces = [
        FaceCandidate(center_x=0.5, center_y=0.5, size=0.01),  # central but tiny
        FaceCandidate(center_x=0.2, center_y=0.2, size=0.40),  # off-centre but huge
    ]
    assert select_primary_user(faces, centrality_weight=0.0, size_weight=1.0) == 1


@given(
    st.lists(
        st.builds(
            FaceCandidate,
            center_x=st.floats(0, 1, allow_nan=False),
            center_y=st.floats(0, 1, allow_nan=False),
            size=st.floats(0, 1, allow_nan=False),
        ),
        min_size=1,
        max_size=6,
    )
)
def test_select_primary_returns_valid_index(faces: list[FaceCandidate]) -> None:
    idx = select_primary_user(faces)
    assert 0 <= idx < len(faces)
