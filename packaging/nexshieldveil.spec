# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the standalone NexShieldVeil Windows build.

Bundles the desktop app + the heavy runtime libs (MediaPipe, OpenCV, PySide6) and
*embeds the MediaPipe model* so the .exe works with zero setup.

Build:  pyinstaller --noconfirm --clean packaging/nexshieldveil.spec
Output: dist/NexShieldVeil/NexShieldVeil.exe   (onedir; wrapped by the Inno installer)

Set NSV_CONSOLE=1 before building to keep a console window (handy for debugging).
"""

import glob
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

# Bundle the QML views + i18n catalogs (+ any vendored OFL fonts) at the exact paths
# the frozen resolvers expect (privacy_guard/ui/{views,i18n,assets/fonts}).
_ui = os.path.join(SPECPATH, "..", "src", "privacy_guard", "ui")
for src in glob.glob(os.path.join(_ui, "views", "*.qml")):
    datas.append((src, "privacy_guard/ui/views"))
for src in glob.glob(os.path.join(_ui, "i18n", "*.json")):
    datas.append((src, "privacy_guard/ui/i18n"))
for pattern in ("*.ttf", "*.otf"):
    for src in glob.glob(os.path.join(_ui, "assets", "fonts", pattern)):
        datas.append((src, "privacy_guard/ui/assets/fonts"))

hiddenimports += [
    # New QML (MVVM) UI — much of it is imported lazily inside shell.main().
    "privacy_guard.ui.shell",
    "privacy_guard.ui.core_controller",
    "privacy_guard.ui.controller",
    "privacy_guard.ui.fake_controller",
    "privacy_guard.ui.state",
    "privacy_guard.ui.translator",
    "privacy_guard.ui.qml_app",
    "privacy_guard.ui.fonts",
    "privacy_guard.ui.theme.theme_controller",
    "privacy_guard.ui.viewmodels",
    "privacy_guard.ui.viewmodels.status",
    "privacy_guard.ui.viewmodels.tray",
    "privacy_guard.ui.viewmodels.settings",
    "privacy_guard.ui.viewmodels.onboarding",
    "privacy_guard.ui.viewmodels.about",
    "privacy_guard.ui.updater_ui",
    "privacy_guard.ui.control_window",  # kept for `nexshieldveil-classic`
    # Qt Quick runtime (the views use QtQuick + Controls.Basic).
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickControls2",
    # Core adapters.
    "privacy_guard.vision.mediapipe_detector",
    "privacy_guard.capture.opencv_sources",
    "privacy_guard.overlay.qt_overlay",
    # Freeze-frame masking stack (v0.3.0): capture + compositor + off-thread
    # transform. Imported lazily inside CoreController/_rebuild_overlay.
    "privacy_guard.overlay.grabber",
    "privacy_guard.overlay.qt_grabber",
    "privacy_guard.overlay.compositor",
    "privacy_guard.overlay.qt_executor",
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
