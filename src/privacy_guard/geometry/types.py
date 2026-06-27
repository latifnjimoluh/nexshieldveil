"""Geometry value objects.

Coordinate convention (right-handed, camera frame):

* Origin at the camera.
* ``+x`` points to the viewer's right, ``+y`` points up, ``+z`` points *out of the
  screen toward the people in front of it*.
* The screen lies in the plane ``z = 0``. Faces are at ``z > 0`` (in front).
* ``gaze_vector(0, 0)`` is ``(0, 0, -1)``: looking straight into the screen.

All distances are in millimetres. These objects are pure data; no hardware deps.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScreenModel:
    """Rectangular screen in the ``z = 0`` plane, positioned below the camera.

    Attributes:
        width_mm: Physical screen width.
        height_mm: Physical screen height.
        camera_above_mm: Vertical gap between the camera and the screen's top edge.
    """

    width_mm: float
    height_mm: float
    camera_above_mm: float = 10.0

    def bounds(self) -> tuple[float, float, float, float]:
        """Return ``(x_min, x_max, y_min, y_max)`` of the screen in the z=0 plane."""
        half_w = self.width_mm / 2.0
        y_top = -self.camera_above_mm
        y_bottom = y_top - self.height_mm
        return (-half_w, half_w, y_bottom, y_top)

    def center(self) -> tuple[float, float]:
        """Return the ``(x, y)`` centre of the screen in the z=0 plane."""
        x_min, x_max, y_min, y_max = self.bounds()
        return ((x_min + x_max) / 2.0, (y_min + y_max) / 2.0)


@dataclass(frozen=True)
class FaceCandidate:
    """A detected face in normalized image space, for primary-user selection.

    Attributes:
        center_x: Horizontal centre of the face box, in ``[0, 1]`` (0 = left).
        center_y: Vertical centre of the face box, in ``[0, 1]`` (0 = top).
        size: Relative face size (e.g. box area as a fraction of the frame), ``[0, 1]``.
    """

    center_x: float
    center_y: float
    size: float
