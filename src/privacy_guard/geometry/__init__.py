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
from privacy_guard.geometry.iris import (
    DEFAULT_MAX_OFFSET_DEG,
    compose_gaze,
    iris_offset_deg,
)
from privacy_guard.geometry.types import FaceCandidate, ScreenModel

__all__ = [
    "DEFAULT_MAX_OFFSET_DEG",
    "FaceCandidate",
    "ScreenModel",
    "ScreenSize",
    "angle_between",
    "compose_gaze",
    "gaze_points_at_screen",
    "gaze_vector",
    "iris_offset_deg",
    "is_plausible_screen_mm",
    "nearest_point_in_rect",
    "primary_user_scores",
    "ray_plane_z_intersection",
    "resolve_screen_size",
    "select_primary_user",
    "unit_vector",
]
