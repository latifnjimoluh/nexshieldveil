"""PySide6 masking overlay: opaque veil + frozen transformed frames, multi-screen.

This is a display adapter. PySide6 is optional: if it is missing, constructing
the overlay raises a clear, catchable error so the app can fall back to a
headless renderer. The module is excluded from coverage because CI has no real
display, but its behaviour (per-screen windows, frame swap, release on hide) is
exercised offscreen by ``tests/ui/test_qt_presenter.py``.

Two layers live here (M-FP4):
- ``_OverlayWidget`` — one frameless, always-on-top, click-through window per
  screen. It paints the opaque veil, optionally a frozen transformed frame
  (blur/pixelate of the captured screen) fading in over it, and always the
  centered lock panel on top so the user understands WHY the screen is hidden.
- ``QtMaskPresenter`` — implements the compositor's ``MaskPresenter`` protocol:
  veil every screen instantly, swap in per-screen frames, release everything on
  hide (P2: no frame outlives the lift).

The veil reduces shoulder-surfing risk; it cannot change how light leaves the
screen (see docs/LIMITATIONS.md).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from privacy_guard.overlay.grabber import ScreenShot
from privacy_guard.overlay.renderer import Renderer

if TYPE_CHECKING:
    from privacy_guard.config import MaskingConfig

try:  # pragma: no cover - import guard
    from PySide6.QtCore import QRectF, Qt, QVariantAnimation
    from PySide6.QtGui import (
        QBrush,
        QColor,
        QFont,
        QImage,
        QPainter,
        QPainterPath,
        QPen,
    )
    from PySide6.QtWidgets import QApplication, QWidget

    _QT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _QT_AVAILABLE = False

logger = logging.getLogger(__name__)


def qt_available() -> bool:
    """Return whether PySide6 is importable."""
    return _QT_AVAILABLE


_DEFAULT_TITLE = "Contenu masqué"
_DEFAULT_SUBTITLE = "Un observateur regarde votre écran"
# Short veil->frame crossfade. Callers pass 0 under the user's reduced-motion
# setting (ThemeController.reduced_motion) — masking itself is never animated,
# only the cosmetic swap that happens after protection is already up.
_DEFAULT_FADE_MS = 120


if _QT_AVAILABLE:  # pragma: no cover - requires a display (tested offscreen)

    def _shot_to_qimage(shot: ScreenShot) -> QImage:
        """Copy a shot's (H, W, 3) RGB array into a self-owned QImage.

        ``.copy()`` is deliberate: the QImage must not alias the numpy buffer,
        so the captured array is collectable as soon as the caller drops it.
        """
        image = np.ascontiguousarray(shot.image)
        h, w = image.shape[:2]
        return QImage(image.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()

    class _OverlayWidget(QWidget):
        """Frameless, translucent, click-through full-screen veil for ONE screen.

        Paint stack, bottom to top: opaque veil colour -> (optional) frozen
        transformed frame fading in -> lock panel with title/subtitle.
        """

        def __init__(
            self,
            opacity: float,
            color: tuple[int, int, int],
            title: str,
            subtitle: str,
            fade_ms: int = _DEFAULT_FADE_MS,
        ) -> None:
            super().__init__()
            self._opacity = opacity
            self._color = color
            self._title = title
            self._subtitle = subtitle
            self._fade_ms = fade_ms
            self._frame: QImage | None = None
            self._frame_opacity = 0.0
            self._fade: QVariantAnimation | None = None
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
                | Qt.WindowType.WindowTransparentForInput
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        # ---- frame lifecycle (driven by QtMaskPresenter) ------------------ #
        @property
        def has_frame(self) -> bool:
            """Whether a transformed frame is currently attached."""
            return self._frame is not None

        @property
        def frame_opacity(self) -> float:
            """Current opacity of the frame layer (1.0 = fully swapped in)."""
            return self._frame_opacity

        def show_veil_mode(self) -> None:
            """Drop any frame and paint the plain opaque veil."""
            self._cancel_fade()
            self._frame = None
            self._frame_opacity = 0.0
            self.update()

        def set_frame(self, frame: QImage) -> None:
            """Attach a transformed frame, crossfading it over the veil."""
            self._cancel_fade()
            self._frame = frame
            if self._fade_ms <= 0:
                self._frame_opacity = 1.0
                self.update()
                return
            fade = QVariantAnimation(self)
            fade.setStartValue(0.0)
            fade.setEndValue(1.0)
            fade.setDuration(self._fade_ms)
            fade.valueChanged.connect(self._on_fade_tick)
            self._fade = fade
            fade.start()

        def clear_frame(self) -> None:
            """Release the frame reference (P2) without repainting."""
            self._cancel_fade()
            self._frame = None
            self._frame_opacity = 0.0

        def _on_fade_tick(self, value: object) -> None:
            self._frame_opacity = float(value)  # type: ignore[arg-type]
            self.update()

        def _cancel_fade(self) -> None:
            if self._fade is not None:
                self._fade.stop()
                self._fade = None

        # ---- painting ------------------------------------------------------ #
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
            # Full-screen dark veil (always: it is the fallback under the frame).
            painter.fillRect(self.rect(), QColor(r, g, b, int(self._opacity * 255)))

            # Frozen transformed frame, stretched onto the logical rect (Qt maps
            # physical capture pixels onto the DPI-scaled geometry).
            if self._frame is not None and self._frame_opacity > 0.0:
                painter.setOpacity(self._frame_opacity)
                painter.drawImage(self.rect(), self._frame)
                painter.setOpacity(1.0)

            # Centered panel, always on top: the user must see WHY the screen
            # is hidden, whatever the masking style underneath.
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


class QtMaskPresenter:  # pragma: no cover - Qt adapter (tested offscreen)
    """One overlay window per screen; satisfies the ``MaskPresenter`` protocol.

    Frames are matched to screens by their logical (x, y) origin (carried by
    :class:`ScreenShot` from the grabber). Screens without a matching frame
    simply keep the opaque veil — that is the P4 degradation, not an error.
    """

    def __init__(
        self,
        opacity: float = 0.92,
        color: tuple[int, int, int] = (16, 16, 16),
        title: str = _DEFAULT_TITLE,
        subtitle: str = _DEFAULT_SUBTITLE,
        fade_ms: int = _DEFAULT_FADE_MS,
    ) -> None:
        """Create the presenter (requires PySide6; creates the app if needed).

        Raises:
            RuntimeError: If PySide6 is unavailable.
        """
        if not _QT_AVAILABLE:
            msg = "PySide6 unavailable; install the 'ui' extra to use the Qt overlay."
            raise RuntimeError(msg)
        self._app = QApplication.instance() or QApplication([])
        self._style = (opacity, color, title, subtitle, fade_ms)
        self._widgets: dict[tuple[int, int], _OverlayWidget] = {}

    @property
    def widgets(self) -> tuple[object, ...]:
        """Current per-screen overlay widgets (diagnostics/tests)."""
        return tuple(self._widgets.values())

    def _sync_widgets_to_screens(self) -> None:
        """(Re)build one widget per current screen; screens can change anytime."""
        opacity, color, title, subtitle, fade_ms = self._style
        seen: set[tuple[int, int]] = set()
        for screen in self._app.screens():
            geometry = screen.geometry()
            key = (geometry.x(), geometry.y())
            seen.add(key)
            widget = self._widgets.get(key)
            if widget is None:
                widget = _OverlayWidget(opacity, color, title, subtitle, fade_ms)
                self._widgets[key] = widget
            widget.setGeometry(geometry)
        for key in list(self._widgets):
            if key not in seen:  # screen was unplugged
                self._widgets.pop(key).deleteLater()

    # ---- MaskPresenter protocol ------------------------------------------- #
    def show_veil(self) -> None:
        """Veil every screen instantly (P1)."""
        self._sync_widgets_to_screens()
        for widget in self._widgets.values():
            widget.show_veil_mode()
            widget.show()
            widget.raise_()
        self._app.processEvents()

    def show_frames(self, frames: list[ScreenShot]) -> None:
        """Swap the veil for each screen's transformed frame (crossfaded)."""
        for frame in frames:
            widget = self._widgets.get((frame.x, frame.y))
            if widget is None:
                logger.warning(
                    "No overlay window at (%d, %d); that screen keeps the veil.",
                    frame.x,
                    frame.y,
                )
                continue
            widget.set_frame(_shot_to_qimage(frame))
        self._app.processEvents()

    def hide(self) -> None:
        """Hide every overlay and release every frame reference (P2)."""
        for widget in self._widgets.values():
            widget.clear_frame()
            widget.hide()
        self._app.processEvents()

    def close(self) -> None:
        """Destroy all overlay windows."""
        for widget in self._widgets.values():
            widget.clear_frame()
            widget.hide()
            widget.deleteLater()
        self._widgets.clear()
        self._app.processEvents()


def build_qt_masking_renderer(
    masking: MaskingConfig, fade_ms: int = _DEFAULT_FADE_MS
) -> Renderer:  # pragma: no cover - Qt adapter (assembled pieces tested separately)
    """Build the full masking renderer for a ``MaskingConfig`` (M-FP5).

    ``veil`` -> compositor in veil-only mode (no capture, ever). ``blur``/
    ``pixelate`` -> freeze-frame stack: Qt screen grabber + off-thread transform
    + per-screen presenter. Must be called on the UI thread (the transform
    executor delivers its results back to the constructing thread).

    Raises:
        RuntimeError: If PySide6 is unavailable.
    """
    from privacy_guard.masking import make_mask_strategy
    from privacy_guard.overlay.compositor import CompositorRenderer, FreezeFrameCompositor
    from privacy_guard.overlay.qt_executor import QtTransformExecutor
    from privacy_guard.overlay.qt_grabber import QtScreenGrabber

    presenter = QtMaskPresenter(opacity=masking.opacity, fade_ms=fade_ms)
    strategy = None if masking.strategy == "veil" else make_mask_strategy(masking)
    compositor = FreezeFrameCompositor(
        grabber=QtScreenGrabber(),
        strategy=strategy,
        presenter=presenter,
        executor=QtTransformExecutor(),
    )
    return CompositorRenderer(compositor, on_close=presenter.close)


class QtOverlayRenderer(Renderer):  # pragma: no cover - Qt adapter (tested offscreen)
    """Veil-only :class:`Renderer` backed by :class:`QtMaskPresenter`.

    Kept for the classic pipeline path (masking strategy ``veil``). Since
    M-FP4 it veils EVERY screen, not just the primary one.
    """

    def __init__(
        self,
        opacity: float = 0.92,
        color: tuple[int, int, int] = (16, 16, 16),
        title: str = _DEFAULT_TITLE,
        subtitle: str = _DEFAULT_SUBTITLE,
    ) -> None:
        """Create the overlay windows.

        Raises:
            RuntimeError: If PySide6 is unavailable.
        """
        self._presenter = QtMaskPresenter(opacity, color, title, subtitle, fade_ms=0)
        self._masked = False

    def set_masked(self, masked: bool) -> None:
        """Show or hide the veil on every screen."""
        if masked == self._masked:
            return
        self._masked = masked
        if masked:
            self._presenter.show_veil()
        else:
            self._presenter.hide()

    @property
    def is_masked(self) -> bool:
        """Whether the overlay is currently shown."""
        return self._masked

    def close(self) -> None:
        """Hide and destroy the overlay windows."""
        self._presenter.close()
