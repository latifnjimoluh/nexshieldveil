"""Pure-math gaze geometry: gaze vectors, ray/plane intersection, screen targeting.

These functions are deliberately free of any hardware or heavy library dependency
(numpy only) so they are fully unit-testable, including with property-based tests.

Honesty note: webcam gaze estimation typically carries 1.5-3 degrees of error, so
the screen-targeting test is intended to be used with a *generous*, configurable
angular tolerance. We do not claim sub-degree accuracy.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from privacy_guard.geometry.types import FaceCandidate, ScreenModel

_EPS = 1e-9


def unit_vector(vec: NDArray[np.float64]) -> NDArray[np.float64]:
    """Return ``vec`` normalized to unit length.

    Raises:
        ValueError: If ``vec`` has (near) zero length.
    """
    norm = float(np.linalg.norm(vec))
    if norm < _EPS:
        msg = "Cannot normalize a zero-length vector"
        raise ValueError(msg)
    return (vec / norm).astype(np.float64)


def gaze_vector(yaw_deg: float, pitch_deg: float) -> NDArray[np.float64]:
    """Convert head yaw/pitch angles into a unit gaze direction.

    ``yaw_deg = pitch_deg = 0`` yields ``(0, 0, -1)`` (looking straight into the
    screen). Positive yaw turns toward ``+x``; positive pitch tilts toward ``+y``.

    Args:
        yaw_deg: Horizontal rotation in degrees.
        pitch_deg: Vertical rotation in degrees.

    Returns:
        A unit 3D vector ``[x, y, z]``.
    """
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)
    x = math.sin(yaw) * math.cos(pitch)
    y = math.sin(pitch)
    z = -math.cos(yaw) * math.cos(pitch)
    return np.array([x, y, z], dtype=np.float64)


def angle_between(v1: NDArray[np.float64], v2: NDArray[np.float64]) -> float:
    """Return the angle between two vectors in degrees, in ``[0, 180]``."""
    a = unit_vector(np.asarray(v1, dtype=np.float64))
    b = unit_vector(np.asarray(v2, dtype=np.float64))
    cos_theta = float(np.clip(np.dot(a, b), -1.0, 1.0))
    return math.degrees(math.acos(cos_theta))


def ray_plane_z_intersection(
    origin: NDArray[np.float64], direction: NDArray[np.float64]
) -> NDArray[np.float64] | None:
    """Intersect the ray ``origin + t*direction`` (t>0) with the plane ``z = 0``.

    Args:
        origin: Ray origin (3D).
        direction: Ray direction (3D), not necessarily unit length.

    Returns:
        The ``[x, y]`` coordinates of the intersection, or ``None`` if the ray is
        parallel to the plane or only meets it behind the origin (``t <= 0``).
    """
    origin = np.asarray(origin, dtype=np.float64)
    direction = np.asarray(direction, dtype=np.float64)
    dz = float(direction[2])
    if abs(dz) < _EPS:
        return None
    t = -float(origin[2]) / dz
    if t <= 0.0:
        return None
    point = origin + t * direction
    return np.array([point[0], point[1]], dtype=np.float64)


def nearest_point_in_rect(
    x: float, y: float, bounds: tuple[float, float, float, float]
) -> tuple[float, float]:
    """Clamp ``(x, y)`` to the closest point inside/on the rectangle ``bounds``."""
    x_min, x_max, y_min, y_max = bounds
    cx = min(max(x, x_min), x_max)
    cy = min(max(y, y_min), y_max)
    return (cx, cy)


def gaze_points_at_screen(
    face_pos: NDArray[np.float64],
    gaze_dir: NDArray[np.float64],
    screen: ScreenModel,
    tolerance_deg: float,
) -> bool:
    """Decide whether a gaze ray points at the screen, within an angular tolerance.

    The gaze ray is intersected with the screen plane; the intersection is clamped
    to the nearest point on the screen rectangle, and the angle between the gaze and
    the direction from the face to that point is compared against ``tolerance_deg``.
    A direct hit yields ~0 degrees; a near miss yields a small angle.

    Args:
        face_pos: 3D position of the observer's face (``z > 0``).
        gaze_dir: Gaze direction (3D, any length).
        screen: The screen geometry.
        tolerance_deg: Angular tolerance in degrees (``> 0``).

    Returns:
        ``True`` if the gaze is judged to point at the screen.
    """
    face_pos = np.asarray(face_pos, dtype=np.float64)
    gaze_dir = np.asarray(gaze_dir, dtype=np.float64)
    bounds = screen.bounds()

    hit = ray_plane_z_intersection(face_pos, gaze_dir)
    if hit is not None:
        tx, ty = nearest_point_in_rect(float(hit[0]), float(hit[1]), bounds)
    else:
        tx, ty = screen.center()

    target = np.array([tx, ty, 0.0], dtype=np.float64)
    to_target = target - face_pos
    if float(np.linalg.norm(to_target)) < _EPS:
        # Face sitting exactly on the target point: treat as looking at screen.
        return True
    return angle_between(gaze_dir, to_target) <= tolerance_deg


def select_primary_user(
    faces: list[FaceCandidate],
    centrality_weight: float = 1.0,
    size_weight: float = 1.0,
) -> int:
    """Pick the index of the primary user among detected faces.

    The primary user is the face that best combines being central in the frame and
    being large (i.e. close to the camera). This never identifies *who* a face is.

    Args:
        faces: Non-empty list of face candidates in normalized image space.
        centrality_weight: Weight for centrality (proximity to the frame centre).
        size_weight: Weight for relative face size.

    Returns:
        The index of the primary-user face.

    Raises:
        ValueError: If ``faces`` is empty.
    """
    if not faces:
        msg = "Cannot select a primary user from an empty face list"
        raise ValueError(msg)

    best_idx = 0
    best_score = -math.inf
    # Max possible distance from centre in normalized space is the half-diagonal.
    max_dist = math.hypot(0.5, 0.5)
    for idx, face in enumerate(faces):
        dist = math.hypot(face.center_x - 0.5, face.center_y - 0.5)
        centrality = 1.0 - (dist / max_dist)
        score = centrality_weight * centrality + size_weight * face.size
        if score > best_score:
            best_score = score
            best_idx = idx
    return best_idx
