"""On-screen masking overlay (Qt adapters + headless test doubles)."""

from __future__ import annotations

from privacy_guard.overlay.compositor import (
    CompositorRenderer,
    CompositorState,
    FreezeFrameCompositor,
    ManualTransformExecutor,
    MaskPresenter,
    RecordingPresenter,
    SynchronousTransformExecutor,
    TransformExecutor,
    transform_shots,
)
from privacy_guard.overlay.grabber import (
    FakeScreenGrabber,
    ScreenGrabber,
    ScreenShot,
    looks_blank,
)
from privacy_guard.overlay.qt_executor import QtTransformExecutor
from privacy_guard.overlay.qt_grabber import QtScreenGrabber
from privacy_guard.overlay.qt_overlay import (
    QtMaskPresenter,
    QtOverlayRenderer,
    build_qt_masking_renderer,
    qt_available,
)
from privacy_guard.overlay.renderer import RecordingRenderer, Renderer

__all__ = [
    "CompositorRenderer",
    "CompositorState",
    "FakeScreenGrabber",
    "FreezeFrameCompositor",
    "ManualTransformExecutor",
    "MaskPresenter",
    "QtMaskPresenter",
    "QtOverlayRenderer",
    "QtScreenGrabber",
    "QtTransformExecutor",
    "RecordingPresenter",
    "RecordingRenderer",
    "Renderer",
    "ScreenGrabber",
    "ScreenShot",
    "SynchronousTransformExecutor",
    "TransformExecutor",
    "build_qt_masking_renderer",
    "looks_blank",
    "qt_available",
    "transform_shots",
]
