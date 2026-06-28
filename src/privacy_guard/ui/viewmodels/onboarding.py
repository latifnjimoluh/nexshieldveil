"""Onboarding view-model: honest intro, explicit camera consent, first settings.

Privacy by design: the camera is *not* opened during onboarding. ``allow_camera``
only records consent; the shell opens the camera after ``finish`` if consent was
given. The limits are shown on the first step, before any access is requested.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from privacy_guard.ui.controller import AppController
from privacy_guard.ui.translator import Translator

_STEP_COUNT = 3


class OnboardingViewModel(QObject):
    """Drives the three first-run panels and records camera consent."""

    changed = Signal()

    def __init__(
        self, controller: AppController, translator: Translator, parent: QObject | None = None
    ) -> None:
        """Bind to controller + translator; start on the first step, no consent yet."""
        super().__init__(parent)
        self._c = controller
        self._tr = translator
        self._index = 0
        self._camera_granted = False
        translator.language_changed.connect(self.changed)

    def _step_no(self) -> int:
        return self._index + 1

    def _get_index(self) -> int:
        return self._index

    def _get_count(self) -> int:
        return _STEP_COUNT

    def _get_is_first(self) -> bool:
        return self._index == 0

    def _get_is_last(self) -> bool:
        return self._index == _STEP_COUNT - 1

    def _get_title(self) -> str:
        return self._tr.tr_key(f"onboarding.step{self._step_no()}.title")

    def _get_body(self) -> str:
        return self._tr.tr_key(f"onboarding.step{self._step_no()}.body")

    def _get_show_limits(self) -> bool:
        return self._index == 0

    def _get_limits_title(self) -> str:
        return self._tr.tr_key("onboarding.limits.title")

    def _get_limits_body(self) -> str:
        return self._tr.tr_key("onboarding.limits.body")

    def _get_show_camera_consent(self) -> bool:
        return self._index == 1

    def _get_camera_granted(self) -> bool:
        return self._camera_granted

    index = Property(int, _get_index, notify=changed)
    count = Property(int, _get_count, notify=changed)
    is_first = Property(bool, _get_is_first, notify=changed)
    is_last = Property(bool, _get_is_last, notify=changed)
    title = Property(str, _get_title, notify=changed)
    body = Property(str, _get_body, notify=changed)
    show_limits = Property(bool, _get_show_limits, notify=changed)
    limits_title = Property(str, _get_limits_title, notify=changed)
    limits_body = Property(str, _get_limits_body, notify=changed)
    show_camera_consent = Property(bool, _get_show_camera_consent, notify=changed)
    camera_granted = Property(bool, _get_camera_granted, notify=changed)

    @Slot()
    def next(self) -> None:
        """Advance to the next step (clamped at the last)."""
        if self._index < _STEP_COUNT - 1:
            self._index += 1
            self.changed.emit()

    @Slot()
    def back(self) -> None:
        """Return to the previous step (clamped at the first)."""
        if self._index > 0:
            self._index -= 1
            self.changed.emit()

    @Slot()
    def allow_camera(self) -> None:
        """Record explicit camera consent and advance (does NOT open the camera)."""
        self._camera_granted = True
        self.next()

    @Slot()
    def skip_camera(self) -> None:
        """Decline camera access for now and advance."""
        self._camera_granted = False
        self.next()

    @Slot()
    def finish(self) -> None:
        """Complete onboarding; start watching only if consent was given."""
        self._c.finish_onboarding()
        if self._camera_granted:
            self._c.enable()
