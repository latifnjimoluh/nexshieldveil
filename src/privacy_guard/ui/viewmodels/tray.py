"""Tray view-model: the system-tray icon state, tooltip, and menu labels."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from privacy_guard.ui.controller import AppController
from privacy_guard.ui.state import (
    SNOOZE_LONG_MINUTES,
    SNOOZE_SHORT_MINUTES,
    color_role,
    headline_key,
)
from privacy_guard.ui.translator import Translator


class TrayViewModel(QObject):
    """Drives the tray icon (the app's primary surface) and its menu."""

    changed = Signal()

    def __init__(
        self, controller: AppController, translator: Translator, parent: QObject | None = None
    ) -> None:
        """Bind to controller + translator."""
        super().__init__(parent)
        self._c = controller
        self._tr = translator
        for signal in (
            controller.state_changed,
            controller.camera_active_changed,
            controller.faces_count_changed,
            controller.running_changed,
            controller.snooze_changed,
            translator.language_changed,
        ):
            signal.connect(self.changed)

    def _get_icon_state(self) -> str:
        # Which of the four tray glyphs to show (clear/protected/paused/error).
        return color_role(self._c.snapshot.protection_state)

    def _get_tooltip(self) -> str:
        name = self._tr.tr_key("app.name")
        headline = self._tr.tr_key(headline_key(self._c.snapshot.protection_state))
        return f"{name} — {headline}"

    def _get_toggle_label(self) -> str:
        key = "action.pause" if self._c.snapshot.running else "action.resume"
        return self._tr.tr_key(key)

    def _get_settings_label(self) -> str:
        return self._tr.tr_key("action.settings")

    def _get_about_label(self) -> str:
        return self._tr.tr_key("action.about")

    def _get_quit_label(self) -> str:
        return self._tr.tr_key("action.quit")

    def _get_camera_label(self) -> str:
        key = "camera.active" if self._c.snapshot.camera_active else "camera.inactive"
        return self._tr.tr_key(key)

    def _get_snooze_short_label(self) -> str:
        return self._tr.tr_key("action.snooze", minutes=SNOOZE_SHORT_MINUTES)

    def _get_snooze_long_label(self) -> str:
        return self._tr.tr_key("action.snooze", minutes=SNOOZE_LONG_MINUTES)

    icon_state = Property(str, _get_icon_state, notify=changed)
    tooltip = Property(str, _get_tooltip, notify=changed)
    toggle_label = Property(str, _get_toggle_label, notify=changed)
    settings_label = Property(str, _get_settings_label, notify=changed)
    about_label = Property(str, _get_about_label, notify=changed)
    quit_label = Property(str, _get_quit_label, notify=changed)
    camera_label = Property(str, _get_camera_label, notify=changed)
    snooze_short_label = Property(str, _get_snooze_short_label, notify=changed)
    snooze_long_label = Property(str, _get_snooze_long_label, notify=changed)

    @Slot()
    def toggle(self) -> None:
        """Pause/resume watching from the tray."""
        self._c.toggle()

    @Slot()
    def snooze_short(self) -> None:
        """Timed pause (short) from the tray; watching resumes by itself."""
        self._c.snooze(SNOOZE_SHORT_MINUTES)

    @Slot()
    def snooze_long(self) -> None:
        """Timed pause (long) from the tray; watching resumes by itself."""
        self._c.snooze(SNOOZE_LONG_MINUTES)

    @Slot()
    def open_settings(self) -> None:
        """Request the settings window."""
        self._c.open_settings()

    @Slot()
    def open_about(self) -> None:
        """Request the about/limits window."""
        self._c.open_about()

    @Slot()
    def quit(self) -> None:
        """Request application quit."""
        self._c.quit()
