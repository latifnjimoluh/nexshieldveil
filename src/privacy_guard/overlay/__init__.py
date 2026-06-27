"""On-screen masking overlay (Qt adapter + headless recording renderer)."""

from __future__ import annotations

from privacy_guard.overlay.qt_overlay import QtOverlayRenderer, qt_available
from privacy_guard.overlay.renderer import RecordingRenderer, Renderer

__all__ = [
    "QtOverlayRenderer",
    "RecordingRenderer",
    "Renderer",
    "qt_available",
]
