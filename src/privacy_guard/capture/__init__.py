"""Frame capture abstraction (webcam / video file / synthetic)."""

from __future__ import annotations

from privacy_guard.capture.frame_source import Frame, FrameSource, SyntheticFrameSource
from privacy_guard.capture.opencv_sources import (
    VideoFileFrameSource,
    WebcamFrameSource,
    opencv_available,
)

__all__ = [
    "Frame",
    "FrameSource",
    "SyntheticFrameSource",
    "VideoFileFrameSource",
    "WebcamFrameSource",
    "opencv_available",
]
