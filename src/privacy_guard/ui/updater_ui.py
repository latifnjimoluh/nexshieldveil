"""Qt glue for the self-updater: background threads + the Settings dialog.

The actual network lives in :mod:`privacy_guard.update.checker` (quarantined). This
module only wraps it in QThreads (so the UI never blocks) and a small dialog. It is a
display adapter: it needs PySide6 and is excluded from coverage.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from privacy_guard import __version__

try:  # pragma: no cover - import guard
    from PySide6.QtCore import QPointF, QSettings, Qt, QThread, Signal
    from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygonF
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QDialog,
        QHBoxLayout,
        QLabel,
        QProgressBar,
        QPushButton,
        QVBoxLayout,
    )

    _QT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _QT_AVAILABLE = False

_ORG = "NexShieldVeil"
_APP = "NexShieldVeil"
_AUTO_CHECK_KEY = "auto_check_updates"


def auto_check_enabled() -> bool:
    """Read the persisted 'check on startup' preference (defaults to on)."""
    if not _QT_AVAILABLE:  # pragma: no cover
        return False
    settings = QSettings(_ORG, _APP)
    return bool(settings.value(_AUTO_CHECK_KEY, True, type=bool))


if _QT_AVAILABLE:  # pragma: no cover - requires a display

    def shield_icon(size: int = 64) -> QIcon:
        """A simple drawn shield icon (no asset file needed)."""
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        s = size
        poly = QPolygonF(
            [
                QPointF(s * 0.5, s * 0.08),
                QPointF(s * 0.88, s * 0.24),
                QPointF(s * 0.88, s * 0.55),
                QPointF(s * 0.5, s * 0.92),
                QPointF(s * 0.12, s * 0.55),
                QPointF(s * 0.12, s * 0.24),
            ]
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#2563eb"))
        painter.drawPolygon(poly)
        painter.setBrush(QColor("#eaf0ff"))
        painter.drawEllipse(QPointF(s * 0.5, s * 0.45), s * 0.12, s * 0.12)
        painter.end()
        return QIcon(pix)

    class UpdateCheckThread(QThread):
        """Checks GitHub for a newer release off the UI thread."""

        found = Signal(object)  # UpdateInfo | None
        failed = Signal(str)

        def run(self) -> None:
            """Run the (quarantined) network check and emit the result."""
            try:
                from privacy_guard.update import check_for_update

                self.found.emit(check_for_update())
            except Exception as exc:  # report, never crash the app
                self.failed.emit(str(exc))

    class UpdateDownloadThread(QThread):
        """Downloads the installer off the UI thread, reporting progress."""

        progressed = Signal(float)
        downloaded = Signal(str)
        failed = Signal(str)

        def __init__(self, url: str, dest: str) -> None:
            """Store the asset URL and destination path."""
            super().__init__()
            self._url = url
            self._dest = dest

        def run(self) -> None:
            """Download the installer and emit the local path (or an error)."""
            try:
                from privacy_guard.update import download_installer

                path = download_installer(self._url, self._dest, progress=self.progressed.emit)
                self.downloaded.emit(path)
            except Exception as exc:  # report, never crash the app
                self.failed.emit(str(exc))

    class SettingsDialog(QDialog):
        """Settings + update panel: version, auto-check toggle, check/download/install."""

        def __init__(self, parent: object = None) -> None:
            """Build the settings dialog."""
            super().__init__(parent)  # type: ignore[arg-type]
            self.setWindowTitle("Paramètres — NexShieldVeil")
            self.setMinimumWidth(440)
            self._info = None
            self._check_thread: UpdateCheckThread | None = None
            self._dl_thread: UpdateDownloadThread | None = None
            self._build()

        def _build(self) -> None:
            root = QVBoxLayout(self)
            root.setSpacing(12)
            root.setContentsMargins(18, 16, 18, 16)

            root.addWidget(QLabel(f"<b>NexShieldVeil</b> — version {__version__}"))

            self._auto = QCheckBox("Vérifier les mises à jour au démarrage")
            self._auto.setChecked(auto_check_enabled())
            self._auto.toggled.connect(self._save_auto)
            root.addWidget(self._auto)

            row = QHBoxLayout()
            self._check_btn = QPushButton("Vérifier les mises à jour")
            self._check_btn.clicked.connect(self.check_now)
            row.addWidget(self._check_btn)
            row.addStretch(1)
            root.addLayout(row)

            self._status = QLabel("")
            self._status.setWordWrap(True)
            root.addWidget(self._status)

            self._progress = QProgressBar()
            self._progress.setRange(0, 100)
            self._progress.hide()
            root.addWidget(self._progress)

            self._install_btn = QPushButton("Télécharger et installer")
            self._install_btn.clicked.connect(self._download_and_install)
            self._install_btn.hide()
            root.addWidget(self._install_btn)

            close = QPushButton("Fermer")
            close.clicked.connect(self.accept)
            foot = QHBoxLayout()
            foot.addStretch(1)
            foot.addWidget(close)
            root.addLayout(foot)

        def _save_auto(self, value: bool) -> None:
            QSettings(_ORG, _APP).setValue(_AUTO_CHECK_KEY, value)

        def check_now(self) -> None:
            """Start a manual update check."""
            self._status.setText("Vérification en cours…")
            self._check_btn.setEnabled(False)
            self._check_thread = UpdateCheckThread(self)
            self._check_thread.found.connect(self._on_found)
            self._check_thread.failed.connect(self._on_failed)
            self._check_thread.start()

        def present_update(self, info: object) -> None:
            """Display an update already found elsewhere (e.g. the startup check)."""
            self._on_found(info)

        def _on_found(self, info: object) -> None:
            self._check_btn.setEnabled(True)
            if info is None:
                self._status.setText("Vous avez déjà la dernière version. ✅")
                self._install_btn.hide()
                return
            self._info = info
            version = getattr(info, "version", "?")
            self._status.setText(f"Nouvelle version <b>{version}</b> disponible.")
            self._install_btn.setVisible(getattr(info, "installer_url", None) is not None)
            if getattr(info, "installer_url", None) is None:
                self._status.setText(
                    f"Nouvelle version <b>{version}</b> disponible "
                    "(pas d'installeur attaché — voir la page de release)."
                )

        def _on_failed(self, message: str) -> None:
            self._check_btn.setEnabled(True)
            self._status.setText(f"Échec de la vérification : {message}")

        def _download_and_install(self) -> None:
            url = getattr(self._info, "installer_url", None)
            if not url:
                return
            dest = str(Path(tempfile.gettempdir()) / "NexShieldVeil-Setup.exe")
            self._install_btn.setEnabled(False)
            self._progress.setValue(0)
            self._progress.show()
            self._status.setText("Téléchargement…")
            self._dl_thread = UpdateDownloadThread(url, dest)
            self._dl_thread.progressed.connect(lambda f: self._progress.setValue(int(f * 100)))
            self._dl_thread.downloaded.connect(self._on_downloaded)
            self._dl_thread.failed.connect(self._on_failed)
            self._dl_thread.start()

        def _on_downloaded(self, path: str) -> None:
            from privacy_guard.update import launch_installer

            self._status.setText("Lancement de l'installeur…")
            launch_installer(path)
            QApplication.quit()
