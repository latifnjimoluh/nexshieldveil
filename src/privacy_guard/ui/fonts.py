"""Load bundled OFL fonts at startup, if present (no network, no failure if absent).

The ``.ttf`` files are not vendored in the repo (see ``assets/fonts/README.md``); when
they exist they are registered so QML can use the families named in ``tokens.FONTS``.
Missing fonts simply fall back to system faces — the app never blocks on this.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("privacy_guard.ui")

_FONTS_DIR = Path(__file__).parent / "assets" / "fonts"


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
