"""Camera-preview view-model: opt-in live view of what the camera sees + detects.

Holds the preview on/off state (mirrored from the controller), a frame counter that
QML binds to (to refresh the ``Image``), the legend, and the toggle command. The
actual frames arrive via :meth:`push_frame` and are handed to the image provider.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Property, QObject, Signal, Slot

from privacy_guard.ui.controller import AppController
from privacy_guard.ui.status import face_tag
from privacy_guard.ui.translator import Translator

if TYPE_CHECKING:
    from PySide6.QtGui import QImage

    from privacy_guard.ui.preview import CameraImageProvider


class CameraViewModel(QObject):
    """Drives the (opt-in) camera preview surface."""

    changed = Signal()
    frame_tick_changed = Signal()

    def __init__(
        self,
        controller: AppController,
        translator: Translator,
        provider: CameraImageProvider | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Bind to the controller/translator; ``provider`` feeds frames to QML."""
        super().__init__(parent)
        self._c = controller
        self._tr = translator
        self._provider = provider
        self._tick = 0
        controller.preview_changed.connect(self.changed)
        controller.camera_active_changed.connect(self.changed)
        controller.running_changed.connect(self.changed)
        translator.language_changed.connect(self.changed)

    # ---- state ----------------------------------------------------------- #
    def _get_preview_enabled(self) -> bool:
        return self._c.snapshot.preview_enabled

    def _get_available(self) -> bool:
        # Something to show only when the preview is on and the camera is delivering.
        snap = self._c.snapshot
        return snap.preview_enabled and snap.camera_active

    def _get_title(self) -> str:
        return self._tr.tr_key("preview.title")

    def _get_hint(self) -> str:
        return self._tr.tr_key("preview.hint")

    def _get_off_text(self) -> str:
        return self._tr.tr_key("preview.off")

    def _get_toggle_label(self) -> str:
        key = "preview.hide" if self._c.snapshot.preview_enabled else "preview.show"
        return self._tr.tr_key(key)

    def _get_legend(self) -> list[dict[str, str]]:
        # Colours reuse the on-frame tag palette so legend and boxes match exactly.
        return [
            {
                "label": self._tr.tr_key("preview.legend.primary"),
                "color": face_tag(is_primary=True, is_looking=False).color,
            },
            {
                "label": self._tr.tr_key("preview.legend.observer"),
                "color": face_tag(is_primary=False, is_looking=True).color,
            },
            {
                "label": self._tr.tr_key("preview.legend.idle"),
                "color": face_tag(is_primary=False, is_looking=False).color,
            },
        ]

    def _get_frame_tick(self) -> int:
        return self._tick

    preview_enabled = Property(bool, _get_preview_enabled, notify=changed)
    available = Property(bool, _get_available, notify=changed)
    title = Property(str, _get_title, notify=changed)
    hint = Property(str, _get_hint, notify=changed)
    off_text = Property(str, _get_off_text, notify=changed)
    toggle_label = Property(str, _get_toggle_label, notify=changed)
    legend = Property("QVariantList", _get_legend, notify=changed)
    frame_tick = Property(int, _get_frame_tick, notify=frame_tick_changed)

    # ---- commands -------------------------------------------------------- #
    @Slot()
    def toggle(self) -> None:
        """Show/hide the camera preview."""
        self._c.toggle_preview()

    @Slot(bool)
    def set_enabled(self, enabled: bool) -> None:
        """Set the preview on/off explicitly."""
        self._c.set_preview_enabled(enabled)

    def push_frame(self, image: QImage) -> None:
        """Receive a new annotated frame (UI thread): store it and bump the counter."""
        if self._provider is not None:
            self._provider.set_image(image)
        self._tick += 1
        self.frame_tick_changed.emit()
