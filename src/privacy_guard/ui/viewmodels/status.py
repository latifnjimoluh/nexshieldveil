"""Status view-model: the live indicator (state, detail, camera, primary action)."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from privacy_guard.ui.controller import AppController
from privacy_guard.ui.state import (
    ProtectionState,
    color_role,
    detail_key,
    headline_key,
    primary_action_id,
    primary_action_label_key,
)
from privacy_guard.ui.translator import Translator


class StatusViewModel(QObject):
    """Maps the controller snapshot to what the status surface shows."""

    changed = Signal()
    # Error actions the shell must handle itself (open OS settings, open docs).
    action_requested = Signal(str)

    def __init__(
        self, controller: AppController, translator: Translator, parent: QObject | None = None
    ) -> None:
        """Bind to the controller + translator and re-emit ``changed`` on any update."""
        super().__init__(parent)
        self._c = controller
        self._tr = translator
        for signal in (
            controller.state_changed,
            controller.error_changed,
            controller.camera_active_changed,
            controller.faces_count_changed,
            controller.engaging_changed,
            controller.running_changed,
            translator.language_changed,
        ):
            signal.connect(self.changed)

    # ---- derived state --------------------------------------------------- #
    def _get_state_key(self) -> str:
        return self._c.snapshot.protection_state.value

    def _get_color_role(self) -> str:
        return color_role(self._c.snapshot.protection_state)

    def _get_headline(self) -> str:
        return self._tr.tr_key(headline_key(self._c.snapshot.protection_state))

    def _get_detail(self) -> str:
        return self._tr.tr_key(detail_key(self._c.snapshot))

    def _get_is_error(self) -> bool:
        return self._c.snapshot.protection_state is ProtectionState.CAMERA_ERROR

    def _get_is_paused(self) -> bool:
        return self._c.snapshot.protection_state is ProtectionState.PAUSED

    # ---- camera transparency -------------------------------------------- #
    def _get_camera_active(self) -> bool:
        return self._c.snapshot.camera_active

    def _get_camera_label(self) -> str:
        key = "camera.active" if self._c.snapshot.camera_active else "camera.inactive"
        return self._tr.tr_key(key)

    # ---- faces (count only, never an image/identity) -------------------- #
    def _get_show_faces(self) -> bool:
        snap = self._c.snapshot
        return snap.running and snap.error_kind is None

    def _get_faces_text(self) -> str:
        return self._tr.tr_key("faces.count", count=self._c.snapshot.faces_count)

    # ---- primary action -------------------------------------------------- #
    def _get_primary_action_id(self) -> str:
        return primary_action_id(self._c.snapshot)

    def _get_primary_action_label(self) -> str:
        return self._tr.tr_key(primary_action_label_key(self._c.snapshot))

    state_key = Property(str, _get_state_key, notify=changed)
    color_role = Property(str, _get_color_role, notify=changed)
    headline = Property(str, _get_headline, notify=changed)
    detail = Property(str, _get_detail, notify=changed)
    is_error = Property(bool, _get_is_error, notify=changed)
    is_paused = Property(bool, _get_is_paused, notify=changed)
    camera_active = Property(bool, _get_camera_active, notify=changed)
    camera_label = Property(str, _get_camera_label, notify=changed)
    show_faces = Property(bool, _get_show_faces, notify=changed)
    faces_text = Property(str, _get_faces_text, notify=changed)
    primary_action_id = Property(str, _get_primary_action_id, notify=changed)
    primary_action_label = Property(str, _get_primary_action_label, notify=changed)

    @Slot()
    def activate_primary(self) -> None:
        """Run the primary action: toggle watching, retry, or defer to the shell."""
        action = primary_action_id(self._c.snapshot)
        if action == "resume" or action == "retry":
            self._c.enable()
        elif action == "pause":
            self._c.pause()
        else:  # open_system_settings / open_docs — the shell knows how
            self.action_requested.emit(action)
