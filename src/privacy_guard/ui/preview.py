"""Live camera preview: annotate a frame with detection boxes, and serve it to QML.

The preview is **opt-in** and **transient**: a frame is drawn and handed to QML for
display, then dropped. Nothing is written to disk or sent anywhere — this only paints
on screen what the camera already sees, exactly like the classic window did.

Face tags/colours reuse the pure ``ui.status.face_tag`` mapping, so the preview and
the rest of the UI stay consistent.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen
from PySide6.QtQuick import QQuickImageProvider

from privacy_guard.ui.status import face_tag

if TYPE_CHECKING:
    from privacy_guard.vision import FaceObservation


def annotate_frame(
    image: np.ndarray,
    observations: list[FaceObservation],
    looking: list[bool],
    primary_index: int | None,
) -> QImage:
    """Return a QImage of the BGR ``image`` with a labelled box per detected face."""
    # BGR -> RGB, contiguous, so QImage can wrap it; .copy() then owns the pixels.
    rgb = np.ascontiguousarray(image[:, :, ::-1])
    h, w, _ = rgb.shape
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()

    painter = QPainter(qimg)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    label_px = max(14, int(h * 0.033))
    font = QFont()
    font.setPixelSize(label_px)
    font.setBold(True)
    painter.setFont(font)

    for i, obs in enumerate(observations):
        is_looking = looking[i] if i < len(looking) else False
        tag = face_tag(is_primary=(i == primary_index), is_looking=is_looking)
        col = QColor(tag.color)
        side = max(math.sqrt(max(obs.size, 1e-4)), 0.12)
        bw, bh = side * w * 1.1, side * h * 1.4
        cx, cy = obs.center_x * w, obs.center_y * h
        x, y = cx - bw / 2, cy - bh / 2
        painter.setPen(QPen(col, max(2, int(h * 0.006))))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(x, y, bw, bh, 12, 12)
        # Tag badge above the box.
        tw = painter.fontMetrics().horizontalAdvance(tag.label) + 16
        th = label_px + 10
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(col))
        painter.drawRoundedRect(x, max(0.0, y - th - 4), tw, th, 8, 8)
        painter.setPen(QPen(QColor("#ffffff")))
        painter.drawText(int(x + 8), int(max(0.0, y - th - 4) + label_px + 2), tag.label)
    painter.end()
    return qimg


class CameraImageProvider(QQuickImageProvider):
    """Serves the latest annotated frame to a QML ``Image`` (image://nsvcam/<tick>)."""

    PROVIDER_ID = "nsvcam"

    def __init__(self) -> None:
        """Start with a tiny transparent placeholder (no camera frame yet)."""
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._image = QImage(2, 2, QImage.Format.Format_RGB888)
        self._image.fill(QColor("#000000"))

    def set_image(self, image: QImage) -> None:
        """Replace the current frame (called on the UI thread)."""
        self._image = image

    def requestImage(self, image_id: str, size: QSize, requested_size: QSize) -> QImage:
        """Return the latest frame (the ``image_id`` is just a cache-busting counter)."""
        return self._image
