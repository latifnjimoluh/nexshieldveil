"""QML wiring helpers: where the views live and how context objects are exposed.

Shared by the live shell and the headless view tests so both expose the exact same
context property names (``Theme``, ``Tr``, ``statusVM``, …) to QML.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlContext


def _ui_dir() -> Path:
    """The ``privacy_guard/ui`` directory, resolved for source *and* frozen builds."""
    if getattr(sys, "frozen", False):  # pragma: no cover - frozen bundle only
        return Path(sys._MEIPASS) / "privacy_guard" / "ui"  # type: ignore[attr-defined]
    return Path(__file__).parent


VIEWS_DIR = _ui_dir() / "views"


def view_url(name: str) -> QUrl:
    """Resolve a view file name (e.g. ``'StatusView.qml'``) to a local file URL."""
    return QUrl.fromLocalFile(str(VIEWS_DIR / name))


def install_context(context: QQmlContext, **objects: QObject | None) -> None:
    """Expose controller/translator/theme/view-models to QML under fixed names.

    Recognised keys: ``theme``, ``translator``, ``status``, ``settings``,
    ``onboarding``, ``about``, ``tray``. ``None`` values are skipped.
    """
    mapping = {
        "theme": "Theme",
        "translator": "Tr",
        "status": "statusVM",
        "settings": "settingsVM",
        "onboarding": "onboardingVM",
        "about": "aboutVM",
        "tray": "trayVM",
        "camera": "cameraVM",
    }
    for key, qml_name in mapping.items():
        obj = objects.get(key)
        if obj is not None:
            context.setContextProperty(qml_name, obj)
