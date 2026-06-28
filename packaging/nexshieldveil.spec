# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the standalone NexShieldVeil Windows build.

Bundles the desktop app + the heavy runtime libs (MediaPipe, OpenCV, PySide6) and
*embeds the MediaPipe model* so the .exe works with zero setup.

Build:  pyinstaller --noconfirm --clean packaging/nexshieldveil.spec
Output: dist/NexShieldVeil/NexShieldVeil.exe   (onedir; wrapped by the Inno installer)

Set NSV_CONSOLE=1 before building to keep a console window (handy for debugging).
"""

import os

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# MediaPipe and OpenCV ship native libs + data files (.tflite/.binarypb graphs) that
# are loaded dynamically; collect_all grabs modules, data and dynamic libraries.
for pkg in ("mediapipe", "cv2"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

# Embed the Face Landmarker model under models/ inside the bundle.
_model = os.path.join(SPECPATH, "..", "models", "face_landmarker.task")
datas += [(_model, "models")]

hiddenimports += [
    "privacy_guard.ui.control_window",
    "privacy_guard.vision.mediapipe_detector",
    "privacy_guard.capture.opencv_sources",
    "privacy_guard.overlay.qt_overlay",
]

# MediaPipe's collect_all drags in its optional GenAI/LLM stack (torch ~250 MB,
# pyarrow, HuggingFace tokenizers, etc.) that the FaceLandmarker path never uses.
# Excluding them cuts the bundle by ~350 MB with no effect on detection.
_EXCLUDES = [
    # test tooling
    "pytest",
    "hypothesis",
    "_pytest",
    # MediaPipe GenAI / LLM stack (unused by vision tasks)
    "torch",
    "torchvision",
    "torchaudio",
    "functorch",
    "torchgen",
    "jax",
    "jaxlib",
    "ml_dtypes",
    "transformers",
    "tokenizers",
    "sentencepiece",
    "safetensors",
    "accelerate",
    "huggingface_hub",
    "hf_xet",
    # heavy data libs not on our path
    "pyarrow",
    "pandas",
    "cryptography",
    "tkinter",
]

a = Analysis(
    [os.path.join(SPECPATH, "app_entry.py")],
    pathex=[os.path.join(SPECPATH, "..", "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=_EXCLUDES,
    noarchive=False,
)

pyz = PYZ(a.pure)

_console = os.environ.get("NSV_CONSOLE", "0") == "1"

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NexShieldVeil",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=_console,
    disable_windowed_traceback=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="NexShieldVeil",
)
