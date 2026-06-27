"""Face observation value object produced by detectors.

We never identify *who* a face is. An observation only carries geometry: where the
face is in the frame, a coarse 3D position, and an estimated head/gaze direction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from privacy_guard.geometry.types import FaceCandidate


@dataclass(frozen=True)
class FaceObservation:
    """A single detected face, in geometry terms only (no identity).

    Attributes:
        center_x: Normalized horizontal centre in ``[0, 1]`` (0 = left).
        center_y: Normalized vertical centre in ``[0, 1]`` (0 = top).
        size: Relative face size in ``[0, 1]`` (box area fraction); proxy for closeness.
        position_mm: Coarse 3D face position in the camera frame (mm), ``z > 0``.
        yaw_deg: Estimated head yaw in degrees (+ toward the viewer's right).
        pitch_deg: Estimated head pitch in degrees (+ upward).
        gaze_estimable: Whether the gaze estimate is reliable enough to use.
    """

    center_x: float
    center_y: float
    size: float
    position_mm: NDArray[np.float64] = field(
        default_factory=lambda: np.array([0.0, 0.0, 600.0], dtype=np.float64)
    )
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    gaze_estimable: bool = True

    def to_candidate(self) -> FaceCandidate:
        """Project to a :class:`FaceCandidate` for primary-user selection."""
        return FaceCandidate(center_x=self.center_x, center_y=self.center_y, size=self.size)
