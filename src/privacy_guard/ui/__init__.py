"""PySide6 desktop UI for NexShieldVeil (optional, degradable).

This package holds the interactive control window and its small pure helpers. The
heavy Qt window code requires a display and is excluded from coverage; the pure
helpers (e.g. status badges) are unit-tested headlessly.
"""

from __future__ import annotations

from privacy_guard.ui.status import (
    FaceTag,
    StatusBadge,
    face_tag,
    sensitivity_descriptor,
    status_badge,
)

__all__ = [
    "FaceTag",
    "StatusBadge",
    "face_tag",
    "sensitivity_descriptor",
    "status_badge",
]
