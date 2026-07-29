"""Qt glue for the self-updater: background threads, the tray icon, the preference.

The actual network lives in :mod:`privacy_guard.update.checker` (quarantined). This
module only wraps it in QThreads so the UI never blocks. Everything the user sees
is in the QML update surface (:mod:`privacy_guard.ui.viewmodels.updates`); this is
a display adapter, so it needs PySide6 and is excluded from coverage.
"""

from __future__ import annotations

try:  # pragma: no cover - import guard
    from PySide6.QtCore import QPointF, QSettings, Qt, QThread, Signal
    from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygonF

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


def set_auto_check_enabled(enabled: bool) -> None:
    """Persist the 'check on startup' preference."""
    if not _QT_AVAILABLE:  # pragma: no cover
        return
    QSettings(_ORG, _APP).setValue(_AUTO_CHECK_KEY, bool(enabled))


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
        """Downloads *and verifies* the installer off the UI thread (AM-4)."""

        progressed = Signal(float)
        downloaded = Signal(str)
        failed = Signal(str)

        def __init__(self, url: str, dest: str, expected_sha256: str) -> None:
            """Store the asset URL, destination path, and the published digest."""
            super().__init__()
            self._url = url
            self._dest = dest
            self._expected_sha256 = expected_sha256

        def run(self) -> None:
            """Download the installer and emit the local path (or an error).

            A checksum mismatch or an untrusted host surfaces here as a failure:
            the path is only emitted for a file that matched its published digest.
            """
            try:
                from privacy_guard.update import download_installer

                path = download_installer(
                    self._url,
                    self._dest,
                    self._expected_sha256,
                    progress=self.progressed.emit,
                )
                self.downloaded.emit(path)
            except Exception as exc:  # report, never crash the app
                self.failed.emit(str(exc))
