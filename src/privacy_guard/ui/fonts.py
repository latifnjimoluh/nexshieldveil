"""Load bundled OFL fonts at startup, if present (no network, no failure if absent).

The ``.ttf`` files are not vendored in the repo (see ``assets/fonts/README.md``); when
they exist they are registered so QML can use the families named in ``tokens.FONTS``.
Missing fonts simply fall back to system faces — the app never blocks on this.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger("privacy_guard.ui")


def _fonts_dir() -> Path:
    """The bundled fonts directory, for source *and* frozen builds."""
    if getattr(sys, "frozen", False):  # pragma: no cover - frozen bundle only
        return Path(sys._MEIPASS) / "privacy_guard" / "ui" / "assets" / "fonts"  # type: ignore[attr-defined]
    return Path(__file__).parent / "assets" / "fonts"


_FONTS_DIR = _fonts_dir()


def load_bundled_fonts() -> list[str]:
    """Register any bundled font files; return the families actually loaded."""
    try:
        from PySide6.QtGui import QFontDatabase
    except ImportError:  # pragma: no cover - UI extra absent
        return []

    families: list[str] = []
    for path in sorted(_FONTS_DIR.glob("*.ttf")) + sorted(_FONTS_DIR.glob("*.otf")):
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id == -1:
            logger.warning("Could not load bundled font %s", path.name)
            continue
        families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return families
