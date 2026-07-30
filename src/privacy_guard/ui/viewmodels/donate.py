"""Donate view-model: an optional way to support the project.

Like the other view-models it performs **no network I/O**: it holds the copy and
the hosted payment-link URL, and emits intents the shell fulfils —
``window_requested`` (show the donate panel) and ``donate_requested`` (open the
payment link in the user's browser). KPay's "pay link" is a hosted checkout page,
so the whole integration is opening a URL: no API, no key, and nothing leaves the
app until the user clicks through.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from privacy_guard.ui.translator import Translator

# The hosted KPay payment link for this project. Opening it in the browser is the
# entire integration (KPay handles the checkout; we never touch payment details).
DONATION_URL = "https://kpay.site/pay/link/nexshieldveil-a86914"


class DonateViewModel(QObject):
    """Drives the donate panel: translated copy + the user's intents."""

    changed = Signal()
    # Intents the shell fulfils (it owns the windows and the browser).
    window_requested = Signal()  # open the donate panel
    donate_requested = Signal(str)  # open this payment-link URL in the browser

    def __init__(self, translator: Translator, parent: QObject | None = None) -> None:
        """Bind to the translator (re-translates on language change)."""
        super().__init__(parent)
        self._tr = translator
        translator.language_changed.connect(self.changed)

    def _get_title(self) -> str:
        return self._tr.tr_key("donate.title")

    def _get_body(self) -> str:
        return self._tr.tr_key("donate.body")

    def _get_action_label(self) -> str:
        return self._tr.tr_key("donate.action")

    def _get_note(self) -> str:
        return self._tr.tr_key("donate.note")

    def _get_url(self) -> str:
        return DONATION_URL

    title = Property(str, _get_title, notify=changed)
    body = Property(str, _get_body, notify=changed)
    action_label = Property(str, _get_action_label, notify=changed)
    note = Property(str, _get_note, notify=changed)
    url = Property(str, _get_url, constant=True)

    @Slot()
    def open_window(self) -> None:
        """Ask the shell to surface the donate panel (from the tray / main window)."""
        self.window_requested.emit()

    @Slot()
    def donate(self) -> None:
        """Ask the shell to open the payment link in the user's browser."""
        self.donate_requested.emit(DONATION_URL)
