"""Locate bundled resources, whether running from source or a frozen .exe.

When packaged with PyInstaller, data files (including the MediaPipe model) live under
``sys._MEIPASS``. From source, paths resolve relative to the current directory so the
existing developer workflow (``models/face_landmarker.task``) keeps working.
"""

from __future__ import annotations

import sys
from pathlib import Path

_MODEL_RELATIVE = Path("models") / "face_landmarker.task"


def is_frozen() -> bool:
    """Whether we are running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Root directory for bundled resources (the bundle when frozen, else cwd)."""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) if base else Path.cwd()


def default_model_path() -> str:
    """Default Face Landmarker model path: bundled when frozen, else cwd-relative."""
    return str(resource_root() / _MODEL_RELATIVE)
