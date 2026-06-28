"""QML wiring helpers: where the views live and how context objects are exposed.

Shared by the live shell and the headless view tests so both expose the exact same
context property names (``Theme``, ``Tr``, ``statusVM``, …) to QML.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlContext

VIEWS_DIR = Path(__file__).parent / "views"


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
    }
    for key, qml_name in mapping.items():
        obj = objects.get(key)
        if obj is not None:
            context.setContextProperty(qml_name, obj)
