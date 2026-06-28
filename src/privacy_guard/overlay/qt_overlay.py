"""PySide6 transparent, always-on-top, click-through overlay (optional, degradable).

This is a display adapter. PySide6 is optional: if it is missing, constructing the
overlay raises a clear, catchable error so the app can fall back to a headless
renderer. The whole module is excluded from coverage because CI has no display.

The veil is an opaque dark layer with a centered panel (drawn lock + message) so the
user understands *why* their screen is hidden. It reduces shoulder-surfing risk; it
cannot change how light leaves the screen (see docs/LIMITATIONS.md).
"""

from __future__ import annotations

from privacy_guard.overlay.renderer import Renderer

try:  # pragma: no cover - import guard
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
    from PySide6.QtWidgets import QApplication, QWidget

    _QT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _QT_AVAILABLE = False


def qt_available() -> bool:
    """Return whether PySide6 is importable."""
    return _QT_AVAILABLE


_DEFAULT_TITLE = "Contenu masqué"
_DEFAULT_SUBTITLE = "Un observateur regarde votre écran"


if _QT_AVAILABLE:  # pragma: no cover - requires a display

    class _OverlayWidget(QWidget):
        """Frameless, translucent, click-through full-screen veil with a message."""

        def __init__(
            self,
            opacity: float,
            color: tuple[int, int, int],
            title: str,
            subtitle: str,
        ) -> None:
            super().__init__()
            self._opacity = opacity
            self._color = color
            self._title = title
            self._subtitle = subtitle
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
                | Qt.WindowType.WindowTransparentForInput
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        def _draw_lock(self, painter: QPainter, cx: float, cy: float, scale: float) -> None:
            """Draw a simple vector padlock centered at (cx, cy)."""
            accent = QColor(240, 240, 240)
            body_w, body_h = 46 * scale, 34 * scale
            body = QRectF(cx - body_w / 2, cy - body_h / 2 + 6 * scale, body_w, body_h)
            # Shackle (arc) above the body.
            pen = QPen(accent, 6 * scale)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            shackle = QRectF(cx - 15 * scale, cy - 30 * scale, 30 * scale, 34 * scale)
            painter.drawArc(shackle, 0 * 16, 180 * 16)
            # Body.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(accent))
            path = QPainterPath()
            path.addRoundedRect(body, 7 * scale, 7 * scale)
            painter.drawPath(path)
            # Keyhole.
            painter.setBrush(QBrush(QColor(30, 30, 30)))
            painter.drawEllipse(QRectF(cx - 4 * scale, cy - 1 * scale, 8 * scale, 8 * scale))

        def paintEvent(self, _event: object) -> None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            r, g, b = self._color
            # Full-screen dark veil.
            painter.fillRect(self.rect(), QColor(r, g, b, int(self._opacity * 255)))

            # Centered panel.
            w, h = self.width(), self.height()
            pw, ph = 560.0, 200.0
            panel = QRectF((w - pw) / 2, (h - ph) / 2, pw, ph)
            painter.setPen(QPen(QColor(255, 255, 255, 40), 1.5))
            painter.setBrush(QBrush(QColor(28, 28, 32, 235)))
            painter.drawRoundedRect(panel, 22, 22)

            self._draw_lock(painter, panel.center().x(), panel.top() + 56, 1.15)

            painter.setPen(QPen(QColor(245, 245, 245)))
            title_font = QFont()
            title_font.setPointSize(20)
            title_font.setBold(True)
            painter.setFont(title_font)
            title_rect = QRectF(panel.left(), panel.top() + 92, pw, 36)
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignHCenter, self._title)

            painter.setPen(QPen(QColor(190, 190, 195)))
            sub_font = QFont()
            sub_font.setPointSize(11)
            painter.setFont(sub_font)
            sub_rect = QRectF(panel.left(), panel.top() + 134, pw, 28)
            painter.drawText(sub_rect, Qt.AlignmentFlag.AlignHCenter, self._subtitle)


class QtOverlayRenderer(Renderer):  # pragma: no cover - requires a display
    """Renderer backed by a PySide6 overlay window."""

    def __init__(
        self,
        opacity: float = 0.92,
        color: tuple[int, int, int] = (16, 16, 16),
        title: str = _DEFAULT_TITLE,
        subtitle: str = _DEFAULT_SUBTITLE,
    ) -> None:
        """Create the overlay window.

        Raises:
            RuntimeError: If PySide6 is unavailable.
        """
        if not _QT_AVAILABLE:
            msg = "PySide6 unavailable; install the 'ui' extra to use the Qt overlay."
            raise RuntimeError(msg)
        self._app = QApplication.instance() or QApplication([])
        self._widget = _OverlayWidget(opacity, color, title, subtitle)
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
