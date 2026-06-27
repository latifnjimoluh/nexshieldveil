"""PySide6 transparent, always-on-top, click-through overlay (optional, degradable).

This is a display adapter. PySide6 is optional: if it is missing, constructing the
overlay raises a clear, catchable error so the app can fall back to a headless
renderer. The whole module is excluded from coverage because CI has no display.
"""

from __future__ import annotations

from privacy_guard.overlay.renderer import Renderer

try:  # pragma: no cover - import guard
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPainter
    from PySide6.QtWidgets import QApplication, QWidget

    _QT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _QT_AVAILABLE = False


def qt_available() -> bool:
    """Return whether PySide6 is importable."""
    return _QT_AVAILABLE


if _QT_AVAILABLE:  # pragma: no cover - requires a display

    class _OverlayWidget(QWidget):
        """Frameless, translucent, click-through full-screen widget."""

        def __init__(self, opacity: float, color: tuple[int, int, int]) -> None:
            super().__init__()
            self._opacity = opacity
            self._color = color
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
                | Qt.WindowType.WindowTransparentForInput
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        def paintEvent(self, _event: object) -> None:
            painter = QPainter(self)
            r, g, b = self._color
            painter.fillRect(self.rect(), QColor(r, g, b, int(self._opacity * 255)))


class QtOverlayRenderer(Renderer):  # pragma: no cover - requires a display
    """Renderer backed by a PySide6 overlay window."""

    def __init__(self, opacity: float = 0.92, color: tuple[int, int, int] = (16, 16, 16)) -> None:
        """Create the overlay window.

        Raises:
            RuntimeError: If PySide6 is unavailable.
        """
        if not _QT_AVAILABLE:
            msg = "PySide6 unavailable; install the 'ui' extra to use the Qt overlay."
            raise RuntimeError(msg)
        self._app = QApplication.instance() or QApplication([])
        self._widget = _OverlayWidget(opacity, color)
        screen = self._app.primaryScreen()
        if screen is not None:
            self._widget.setGeometry(screen.geometry())
        self._masked = False

    def set_masked(self, masked: bool) -> None:
        """Show or hide the overlay window."""
        if masked == self._masked:
            return
        self._masked = masked
        if masked:
            self._widget.show()
            self._widget.raise_()
        else:
            self._widget.hide()
        self._app.processEvents()

    @property
    def is_masked(self) -> bool:
        """Whether the overlay is currently shown."""
        return self._masked

    def close(self) -> None:
        """Hide and destroy the overlay window."""
        self._widget.hide()
        self._widget.deleteLater()
        self._app.processEvents()
