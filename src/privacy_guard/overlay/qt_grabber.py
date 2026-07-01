"""Qt screen-capture adapter for the freeze-frame masking path (M-FP2).

Uses ``QScreen.grabWindow(0)`` — already available through PySide6, so screen
capture adds **no new dependency** (and nothing new for the privacy AST guard
to quarantine). This is a display adapter: excluded from coverage like
``qt_overlay.py`` and exercised manually; all capture *logic* (fallbacks,
blank detection, lifecycle) lives in pure, fully-tested modules.

Privacy (P2/P3): the captured frame goes straight into a numpy array in RAM —
never written to disk, never shown to the user, and the Qt-side pixmap/image
temporaries go out of scope before this returns. Failure of ANY screen fails
the whole capture (returns ``[]``) so the caller veils every screen (P4).
"""

from __future__ import annotations

import logging

import numpy as np

from privacy_guard.overlay.grabber import ScreenGrabber, ScreenShot

try:  # pragma: no cover - import guard
    from PySide6.QtGui import QGuiApplication, QImage

    _QT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _QT_AVAILABLE = False

logger = logging.getLogger(__name__)


class QtScreenGrabber(ScreenGrabber):  # pragma: no cover - requires a display
    """Captures every screen of the virtual desktop via ``QScreen.grabWindow``."""

    def __init__(self) -> None:
        """Create the grabber.

        Raises:
            RuntimeError: If PySide6 is unavailable.
        """
        if not _QT_AVAILABLE:
            msg = "PySide6 unavailable; install the 'ui' extra to capture screens."
            raise RuntimeError(msg)

    def grab_all(self) -> list[ScreenShot]:
        """One shot per screen, or ``[]`` on any failure (never raises — P4)."""
        app = QGuiApplication.instance()
        if app is None:
            logger.warning("Screen capture failed: no QGuiApplication is running.")
            return []
        shots: list[ScreenShot] = []
        for screen in app.screens():
            try:
                pixmap = screen.grabWindow(0)
            except Exception:  # OS/driver refusal must not crash masking (P4)
                logger.warning("Screen capture failed on %r.", screen.name(), exc_info=True)
                return []
            if pixmap.isNull() or pixmap.width() == 0 or pixmap.height() == 0:
                logger.warning("Screen capture returned an empty frame on %r.", screen.name())
                return []
            qimage = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
            array = self._to_array(qimage)
            if array is None:
                return []
            geometry = screen.geometry()
            shots.append(
                ScreenShot(
                    image=array,
                    x=geometry.x(),
                    y=geometry.y(),
                    width=geometry.width(),
                    height=geometry.height(),
                )
            )
        if not shots:
            logger.warning("Screen capture found no screens.")
        return shots

    @staticmethod
    def _to_array(qimage: QImage) -> np.ndarray | None:
        """Copy a ``Format_RGB888`` QImage into an owned (H, W, 3) uint8 array.

        The copy is deliberate: the result must not alias Qt-owned memory, so
        its lifetime (and release on unmask — P2) is fully ours.
        """
        h, w = qimage.height(), qimage.width()
        stride = qimage.bytesPerLine()
        buffer = qimage.constBits()
        if buffer is None or h <= 0 or w <= 0:
            logger.warning("Screen capture produced an unreadable image.")
            return None
        rows = np.frombuffer(buffer, dtype=np.uint8, count=stride * h).reshape(h, stride)
        return rows[:, : w * 3].reshape(h, w, 3).copy()
