"""Frame downscaling before inference: making ``camera.downscale_width`` real (AM-12).

The setting was declared in the config schema and advertised in
``config.example.toml`` ("frames downscaled to this width before vision (speed)"),
but nothing ever applied it: MediaPipe ran on the camera's native resolution —
often 1280x720 or more — for a task that needs roughly 640 px of width. On an app
meant to run all day in the background, that is the dominant CPU cost.

:class:`DownscaledFrameSource` wraps any :class:`FrameSource` and shrinks each
frame on the way out. All the decision logic (whether to resize, to what size)
is pure and unit-tested; the pixel resampling itself is an injectable callable so
the fast OpenCV path is used when OpenCV is there, without making this module
depend on it.

**Why downscaling does not shift the head pose.**
:meth:`~privacy_guard.vision.mediapipe_detector.MediaPipeFaceDetector._solve_head_pose`
derives its focal length from the frame width (``focal = w``) and its principal
point from ``(w/2, h/2)``, while the landmarks it feeds to ``solvePnP`` are
normalised coordinates multiplied by ``w`` and ``h``. Scaling the image by a factor
``k`` therefore scales the image points, the focal length and the principal point by
the same ``k`` — which is exactly a change of pixel units, and leaves the recovered
rotation and translation unchanged. ``tests/component/test_downscale_pose.py``
checks that empirically when OpenCV is installed.

Privacy: frames stay in RAM. Nothing is written, nothing is accumulated — the
wrapper holds no reference to a frame once it has returned it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import cast

import numpy as np
from numpy.typing import NDArray

from privacy_guard.capture.frame_source import Frame, FrameSource

logger = logging.getLogger(__name__)

Image = NDArray[np.uint8]
# (image, target_width, target_height) -> resized image
Resizer = Callable[[Image, int, int], Image]


def target_size(width: int, height: int, target_width: int) -> tuple[int, int] | None:
    """Size to resize a ``width x height`` frame to, or ``None`` to leave it alone.

    Upscaling is never done: a camera already below ``target_width`` is returned
    untouched (there is no detail to gain, only CPU to burn). The aspect ratio is
    preserved, and the height never collapses below one pixel.

    Args:
        width: Source frame width in pixels.
        height: Source frame height in pixels.
        target_width: Desired width in pixels.

    Returns:
        ``(new_width, new_height)``, or ``None`` if no resize is needed.

    Raises:
        ValueError: If any dimension is not positive.
    """
    if width <= 0 or height <= 0:
        msg = f"frame dimensions must be positive, got {width}x{height}"
        raise ValueError(msg)
    if target_width <= 0:
        msg = f"target_width must be positive, got {target_width}"
        raise ValueError(msg)
    if target_width >= width:
        return None
    new_height = max(1, round(height * target_width / width))
    return (target_width, new_height)


def resize_nearest(image: Image, width: int, height: int) -> Image:
    """Nearest-neighbour resize, pure numpy — the fallback when OpenCV is absent.

    Nearest sampling aliases, which is why it is only the fallback: whenever
    OpenCV is installed (i.e. whenever a real webcam is in play, since both come
    from the ``vision`` extra) :func:`default_resizer` picks ``INTER_AREA``, which
    averages the discarded pixels instead of dropping them.
    """
    src_h, src_w = image.shape[:2]
    rows = (np.arange(height) * (src_h / height)).astype(np.int64).clip(0, src_h - 1)
    cols = (np.arange(width) * (src_w / width)).astype(np.int64).clip(0, src_w - 1)
    resized: Image = image[rows[:, None], cols[None, :]]
    return resized


def default_resizer() -> Resizer:
    """Return the best resampler available: OpenCV ``INTER_AREA``, else numpy nearest."""
    try:  # pragma: no cover - depends on the optional 'vision' extra
        import cv2
    except ImportError:  # pragma: no cover - exercised by the pure fallback tests
        return resize_nearest

    def _cv2_area(image: Image, width: int, height: int) -> Image:  # pragma: no cover - needs cv2
        # cv2.resize preserves the input dtype (uint8 in, uint8 out); its stubs
        # only promise a generic ndarray, hence the cast.
        return cast("Image", cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA))

    return _cv2_area


class DownscaledFrameSource(FrameSource):
    """Wrap a source so every frame is shrunk to ``target_width`` before inference.

    Index and timestamp are passed through untouched — unlike
    :class:`~privacy_guard.capture.resilience.ResilientFrameSource`, this wrapper
    changes pixels only, so MediaPipe's strictly-increasing timestamp requirement
    stays the inner source's business.

    Composition order matters: put this **outside** the resilient wrapper
    (``Downscaled(Resilient(Webcam))``) so frames from a camera that reconnected
    mid-session are downscaled too.
    """

    def __init__(
        self,
        source: FrameSource,
        target_width: int,
        resizer: Resizer | None = None,
    ) -> None:
        """Wrap ``source``, resizing frames wider than ``target_width``.

        Args:
            source: The source to wrap.
            target_width: Width to shrink frames to (frames already narrower are
                passed through unchanged).
            resizer: Resampling callable; defaults to :func:`default_resizer`.

        Raises:
            ValueError: If ``target_width`` is not positive.
        """
        if target_width <= 0:
            msg = f"target_width must be positive, got {target_width}"
            raise ValueError(msg)
        self._source = source
        self._target_width = target_width
        self._resize = resizer if resizer is not None else default_resizer()
        self._logged_size: tuple[int, int] | None = None

    @property
    def is_available(self) -> bool:
        """Whether the wrapped source can currently yield frames."""
        return self._source.is_available

    def read(self) -> Frame | None:
        """Return the next frame, downscaled; ``None`` propagates unchanged."""
        frame = self._source.read()
        if frame is None:
            return None
        size = target_size(frame.width, frame.height, self._target_width)
        if size is None:
            return frame
        width, height = size
        if self._logged_size != size:
            logger.info(
                "Downscaling capture %dx%d -> %dx%d before inference.",
                frame.width,
                frame.height,
                width,
                height,
            )
            self._logged_size = size
        return Frame(
            image=np.ascontiguousarray(self._resize(frame.image, width, height)),
            timestamp_ms=frame.timestamp_ms,
            index=frame.index,
        )

    def close(self) -> None:
        """Release the wrapped source."""
        self._source.close()
