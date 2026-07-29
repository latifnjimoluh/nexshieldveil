"""Updates view-model: the update surface of the QML app (AM-3).

Until now the self-updater only existed in the legacy Qt Widgets window, while the
installer ships the QML shell — so nobody who installed NexShieldVeil would ever
be told about a new version, security fix included. This view-model brings the
update surface into the QML app, translated like everything else.

It performs **no network I/O and starts no thread**: it holds the state and the
copy, emits intent signals (``check_requested`` / ``install_requested`` /
``launch_requested``), and receives outcomes through ``report_*`` methods. The
shell connects those to the quarantined
:mod:`~privacy_guard.update.checker` running on a worker thread. That split is
what makes the whole surface testable headlessly, with no network and no clock.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from privacy_guard import __version__
from privacy_guard.ui.state import UpdateState, update_headline_key, update_is_busy
from privacy_guard.ui.translator import Translator


class UpdatesViewModel(QObject):
    """Drives the update window: state, copy, progress, and the user's intents."""

    changed = Signal()
    # Intents the shell fulfils (it owns the threads and the browser).
    check_requested = Signal()
    install_requested = Signal(str, str)  # (url, expected_sha256)
    launch_requested = Signal(str)  # verified installer path
    page_requested = Signal(str)  # release page URL
    # Emitted only when the preference actually flips, so the shell persists it
    # on a real user decision rather than on every repaint.
    auto_check_changed = Signal(bool)

    def __init__(
        self,
        translator: Translator,
        auto_check: bool = True,
        parent: QObject | None = None,
    ) -> None:
        """Bind to the translator; start idle with the persisted auto-check value."""
        super().__init__(parent)
        self._tr = translator
        self._state = UpdateState.IDLE
        self._version = ""
        self._notes = ""
        self._page_url = ""
        self._installer_url = ""
        self._installer_sha256 = ""
        self._progress = 0.0
        self._error = ""
        self._auto_check = bool(auto_check)
        translator.language_changed.connect(self.changed)

    # ---- state (read by QML) -------------------------------------------- #
    def _get_state_key(self) -> str:
        return self._state.value

    def _get_busy(self) -> bool:
        return update_is_busy(self._state)

    def _get_headline(self) -> str:
        return self._tr.tr_key(update_headline_key(self._state), version=self._version)

    def _get_detail(self) -> str:
        if self._state is UpdateState.FAILED:
            return self._tr.tr_key("update.failed.detail", error=self._error)
        if self._state is UpdateState.MANUAL_ONLY:
            # Say WHY the one-click install is missing rather than hiding it:
            # an unexplained missing button reads like a bug, not a safeguard.
            return self._tr.tr_key("update.manual_only.detail")
        if self._state is UpdateState.AVAILABLE:
            return self._tr.tr_key("update.available.detail")
        if self._state is UpdateState.UP_TO_DATE:
            return self._tr.tr_key("update.up_to_date.detail")
        return self._tr.tr_key("update.idle.detail")

    def _get_current_version(self) -> str:
        return self._tr.tr_key("about.version", version=__version__)

    def _get_notes(self) -> str:
        return self._notes

    def _get_progress(self) -> float:
        return self._progress

    def _get_can_install(self) -> bool:
        return self._state is UpdateState.AVAILABLE

    def _get_can_open_page(self) -> bool:
        return bool(self._page_url) and self._state in (
            UpdateState.AVAILABLE,
            UpdateState.MANUAL_ONLY,
        )

    def _get_auto_check(self) -> bool:
        return self._auto_check

    def _get_check_label(self) -> str:
        return self._tr.tr_key("update.action.check")

    def _get_install_label(self) -> str:
        return self._tr.tr_key("update.action.install")

    def _get_page_label(self) -> str:
        return self._tr.tr_key("update.action.page")

    def _get_auto_check_label(self) -> str:
        return self._tr.tr_key("update.auto_check")

    state_key = Property(str, _get_state_key, notify=changed)
    busy = Property(bool, _get_busy, notify=changed)
    headline = Property(str, _get_headline, notify=changed)
    detail = Property(str, _get_detail, notify=changed)
    current_version = Property(str, _get_current_version, notify=changed)
    notes = Property(str, _get_notes, notify=changed)
    progress = Property(float, _get_progress, notify=changed)
    can_install = Property(bool, _get_can_install, notify=changed)
    can_open_page = Property(bool, _get_can_open_page, notify=changed)
    auto_check = Property(bool, _get_auto_check, notify=changed)
    check_label = Property(str, _get_check_label, notify=changed)
    install_label = Property(str, _get_install_label, notify=changed)
    page_label = Property(str, _get_page_label, notify=changed)
    auto_check_label = Property(str, _get_auto_check_label, notify=changed)

    # ---- commands (called by QML / the tray) ----------------------------- #
    @Slot()
    def check(self) -> None:
        """Ask the shell to run a check (ignored while one is already running)."""
        if update_is_busy(self._state):
            return
        self._state = UpdateState.CHECKING
        self._error = ""
        self.changed.emit()
        self.check_requested.emit()

    @Slot()
    def install(self) -> None:
        """Ask the shell to download and verify the installer.

        Only ever emitted for an update carrying a published digest: the shell
        passes it straight to ``download_installer``, which refuses anything else.
        """
        if self._state is not UpdateState.AVAILABLE:
            return
        self._state = UpdateState.DOWNLOADING
        self._progress = 0.0
        self.changed.emit()
        self.install_requested.emit(self._installer_url, self._installer_sha256)

    @Slot()
    def open_release_page(self) -> None:
        """Ask the shell to open the release page in the user's browser."""
        if self._page_url:
            self.page_requested.emit(self._page_url)

    @Slot(bool)
    def set_auto_check(self, enabled: bool) -> None:
        """Enable/disable the startup check (the shell persists it)."""
        enabled = bool(enabled)
        if enabled != self._auto_check:
            self._auto_check = enabled
            self.changed.emit()
            self.auto_check_changed.emit(enabled)

    # ---- outcomes (called by the shell's worker threads) ----------------- #
    def report_result(self, info: object | None) -> None:
        """Record a finished check: ``None`` means already up to date."""
        if info is None:
            self._state = UpdateState.UP_TO_DATE
            self._version = ""
            self._notes = ""
            self._page_url = ""
            self._installer_url = ""
            self._installer_sha256 = ""
            self.changed.emit()
            return
        self._version = str(getattr(info, "version", "") or "")
        self._notes = str(getattr(info, "notes", "") or "")
        self._page_url = str(getattr(info, "html_url", "") or "")
        self._installer_url = str(getattr(info, "installer_url", "") or "")
        self._installer_sha256 = str(getattr(info, "installer_sha256", "") or "")
        # An installer we cannot verify is not an installer we offer to run.
        self._state = (
            UpdateState.AVAILABLE
            if getattr(info, "can_auto_install", False)
            else UpdateState.MANUAL_ONLY
        )
        self.changed.emit()

    def report_progress(self, fraction: float) -> None:
        """Record download progress (clamped to ``[0, 1]``)."""
        self._progress = min(1.0, max(0.0, float(fraction)))
        self.changed.emit()

    def report_downloaded(self, path: str) -> None:
        """A verified installer landed on disk: ask the shell to launch it."""
        self._progress = 1.0
        self.changed.emit()
        self.launch_requested.emit(path)

    def report_failed(self, message: str) -> None:
        """Record a failed check/download, keeping the reason visible."""
        self._state = UpdateState.FAILED
        self._error = str(message)
        self.changed.emit()
