"""On-screen masking overlay (Qt adapters + headless test doubles)."""

from __future__ import annotations

from privacy_guard.overlay.grabber import (
    FakeScreenGrabber,
    ScreenGrabber,
    ScreenShot,
    looks_blank,
)
from privacy_guard.overlay.qt_grabber import QtScreenGrabber
from privacy_guard.overlay.qt_overlay import QtOverlayRenderer, qt_available
from privacy_guard.overlay.renderer import RecordingRenderer, Renderer

__all__ = [
    "FakeScreenGrabber",
    "QtOverlayRenderer",
    "QtScreenGrabber",
    "RecordingRenderer",
    "Renderer",
    "ScreenGrabber",
    "ScreenShot",
    "looks_blank",
    "qt_available",
]
