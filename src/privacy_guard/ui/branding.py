"""Bundled brand assets: the app icon and the wordmark lockup.

Mirrors :mod:`privacy_guard.ui.fonts`: assets live under
``privacy_guard/ui/assets/branding/`` and are resolved for both source runs and
frozen (PyInstaller) builds. Everything degrades gracefully — a missing asset
falls back to the drawn shield icon, and QML bindings receive an empty string
rather than a broken image.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl
from PySide6.QtGui import QIcon


def _branding_dir() -> Path:
    """The bundled branding directory, for source *and* frozen builds."""
    if getattr(sys, "frozen", False):  # pragma: no cover - frozen bundle only
        base = Path(sys._MEIPASS) / "privacy_guard" / "ui" / "assets" / "branding"  # type: ignore[attr-defined]
        return base
    return Path(__file__).parent / "assets" / "branding"


_DIR = _branding_dir()
_ICON_ICO = _DIR / "icon.ico"
_ICON_PNG = _DIR / "icon.png"
_WORDMARK_PNG = _DIR / "wordmark.png"


def icon_path() -> Path | None:
    """The best available app-icon file (``.ico`` preferred on Windows), or None."""
    for candidate in (_ICON_ICO, _ICON_PNG):
        if candidate.exists():
            return candidate
    return None


def wordmark_path() -> Path | None:
    """The horizontal lockup image, or None if it is not bundled."""
    return _WORDMARK_PNG if _WORDMARK_PNG.exists() else None


def app_icon() -> QIcon:
    """The application icon from the bundled asset.

    Falls back to the hand-drawn shield (``updater_ui.shield_icon``) if the asset
    is missing or unreadable, so the app always has *an* icon.
    """
    path = icon_path()
    if path is not None:
        icon = QIcon(str(path))
        if not icon.isNull():
            return icon
    from privacy_guard.ui.updater_ui import shield_icon

    return shield_icon()


def _file_url(path: Path | None) -> str:
    return QUrl.fromLocalFile(str(path)).toString() if path else ""


class Branding(QObject):
    """Exposes brand asset URLs to QML (context property ``Brand``).

    Both properties are empty strings when the asset is absent; views bind
    ``visible`` to a non-empty check so a missing file leaves no broken image.
    """

    @Property(str, constant=True)
    def wordmark(self) -> str:  # noqa: D102 - QML property
        return _file_url(wordmark_path())

    @Property(str, constant=True)
    def icon(self) -> str:  # noqa: D102 - QML property
        return _file_url(_ICON_PNG if _ICON_PNG.exists() else None)
