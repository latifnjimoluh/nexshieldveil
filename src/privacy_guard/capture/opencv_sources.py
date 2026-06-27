"""OpenCV-backed frame sources (webcam, video file).

These are hardware/IO adapters. OpenCV is an optional dependency: if it is not
installed, constructing these sources raises a clear, catchable error so the app
can degrade gracefully instead of crashing.

No frame is ever written to disk here, and no network connection is opened.
"""

from __future__ import annotations

import time

import numpy as np

from privacy_guard.capture.frame_source import Frame, FrameSource

try:  # pragma: no cover - import guard exercised indirectly
    import cv2

    _CV2_AVAILABLE = True
except ImportError:  # pragma: no cover
    cv2 = None
    _CV2_AVAILABLE = False


def opencv_available() -> bool:
    """Return whether OpenCV is importable in this environment."""
    return _CV2_AVAILABLE


class _OpenCVCaptureSource(FrameSource):
    """Shared logic for cv2.VideoCapture-based sources."""

    def __init__(self, target: int | str) -> None:
        if not _CV2_AVAILABLE:
            msg = "OpenCV (opencv-python) is not installed; install the 'vision' extra."
            raise RuntimeError(msg)
        self._capture = cv2.VideoCapture(target)
        self._index = 0
        self._start = time.monotonic()

    @property
    def is_available(self) -> bool:
        """Whether the underlying capture opened successfully."""
        return bool(self._capture is not None and self._capture.isOpened())

    def _timestamp_ms(self) -> float:
        return (time.monotonic() - self._start) * 1000.0

    def read(self) -> Frame | None:
        """Grab the next frame, or ``None`` if the capture is closed/exhausted."""
        if not self.is_available:
            return None
        ok, image = self._capture.read()
        if not ok or image is None:
            return None
        frame = Frame(
            image=np.ascontiguousarray(image, dtype=np.uint8),
            timestamp_ms=self._timestamp_ms(),
            index=self._index,
        )
        self._index += 1
        return frame

    def close(self) -> None:
        """Release the underlying capture device/file."""
        if self._capture is not None:
            self._capture.release()


class WebcamFrameSource(_OpenCVCaptureSource):
    """Live webcam capture via OpenCV. Requires a real camera at runtime."""

    def __init__(self, device_index: int = 0) -> None:
        """Open the webcam at ``device_index``.

        Raises:
            RuntimeError: If OpenCV is unavailable.
        """
        super().__init__(device_index)


class VideoFileFrameSource(_OpenCVCaptureSource):
    """Replay a known video clip; used for deterministic system/E2E tests."""

    def __init__(self, path: str) -> None:
        """Open the video file at ``path``.

        Raises:
            RuntimeError: If OpenCV is unavailable.
        """
        super().__init__(path)

    def _timestamp_ms(self) -> float:
        # Prefer the file's own presentation timestamp for determinism.
        pos = self._capture.get(cv2.CAP_PROP_POS_MSEC)
        return float(pos) if pos and pos > 0 else super()._timestamp_ms()
