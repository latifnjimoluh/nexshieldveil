"""Pure geometry: gaze vectors, screen targeting, primary-user selection."""

from __future__ import annotations

from privacy_guard.geometry.calibration import (
    ScreenSize,
    is_plausible_screen_mm,
    resolve_screen_size,
)
from privacy_guard.geometry.gaze import (
    angle_between,
    gaze_points_at_screen,
    gaze_vector,
    nearest_point_in_rect,
    primary_user_scores,
    ray_plane_z_intersection,
    select_primary_user,
    unit_vector,
)
from privacy_guard.geometry.types import FaceCandidate, ScreenModel

__all__ = [
    "FaceCandidate",
    "ScreenModel",
    "ScreenSize",
    "angle_between",
    "gaze_points_at_screen",
    "gaze_vector",
    "is_plausible_screen_mm",
    "nearest_point_in_rect",
    "primary_user_scores",
    "ray_plane_z_intersection",
    "resolve_screen_size",
    "select_primary_user",
    "unit_vector",
]
