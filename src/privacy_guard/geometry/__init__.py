"""Pure geometry: gaze vectors, screen targeting, primary-user selection."""

from __future__ import annotations

from privacy_guard.geometry.gaze import (
    angle_between,
    gaze_points_at_screen,
    gaze_vector,
    nearest_point_in_rect,
    ray_plane_z_intersection,
    select_primary_user,
    unit_vector,
)
from privacy_guard.geometry.types import FaceCandidate, ScreenModel

__all__ = [
    "FaceCandidate",
    "ScreenModel",
    "angle_between",
    "gaze_points_at_screen",
    "gaze_vector",
    "nearest_point_in_rect",
    "ray_plane_z_intersection",
    "select_primary_user",
    "unit_vector",
]
