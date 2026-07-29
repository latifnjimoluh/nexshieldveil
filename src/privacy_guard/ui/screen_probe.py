"""Qt probe for the primary screen's physical size (AM-10).

A thin display adapter: it reads ``QScreen.physicalSize()`` and hands the numbers
to :mod:`privacy_guard.geometry.calibration`, which decides whether to believe
them. Excluded from coverage like the other Qt adapters — the judgement it feeds
is pure and fully tested.

Only the *primary* screen is probed. The decision geometry models one screen
plane (the one the camera sits above); the masking, since M-FP4, covers every
screen. That asymmetry is documented in ``docs/LIMITATIONS.md`` rather than
papered over.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def primary_screen_mm() -> tuple[float, float] | None:  # pragma: no cover - needs a display
    """Physical size of the primary screen in millimetres, or ``None``.

    Never raises: a missing display, a headless session or a Qt build without a
    screen must degrade to "we do not know", not crash the startup path.
    """
    try:
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication.instance()
        if app is None:
            return None
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return None
        size = screen.physicalSize()
        return (float(size.width()), float(size.height()))
    except Exception as exc:
        logger.debug("Could not read the primary screen's physical size: %s", exc)
        return None
