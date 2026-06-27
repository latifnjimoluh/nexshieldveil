"""Frame sources: the injectable camera abstraction.

The pipeline only ever talks to :class:`FrameSource`, so tests and CI run fully
**headless** by injecting :class:`SyntheticFrameSource` (deterministic in-RAM
frames) instead of a real camera.

Privacy by design: frames live **only in RAM**. No source writes image data to
disk, and nothing here opens a network connection. Frames are produced on demand
and are not accumulated between iterations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import TracebackType
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True)
class Frame:
    """A single captured frame held in memory.

    Attributes:
        image: ``(H, W, 3)`` uint8 array (BGR, OpenCV convention).
        timestamp_ms: Capture timestamp in milliseconds.
        index: Monotonic frame index from this source.
    """

    image: NDArray[np.uint8]
    timestamp_ms: float
    index: int

    @property
    def width(self) -> int:
        """Frame width in pixels."""
        return int(self.image.shape[1])

    @property
    def height(self) -> int:
        """Frame height in pixels."""
        return int(self.image.shape[0])


class FrameSource(ABC):
    """Abstract, injectable source of frames."""

    @abstractmethod
    def read(self) -> Frame | None:
        """Return the next frame, or ``None`` when the source is exhausted/unavailable."""

    @abstractmethod
    def close(self) -> None:
        """Release any underlying resources."""

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether the source can currently yield frames."""

    def __iter__(self) -> Iterator[Frame]:
        """Iterate frames until the source is exhausted."""
        while True:
            frame = self.read()
            if frame is None:
                return
            yield frame

    def __enter__(self) -> FrameSource:
        """Enter a context that guarantees :meth:`close` on exit."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Release resources on context exit."""
        self.close()


class SyntheticFrameSource(FrameSource):
    """Deterministic in-memory frames for tests and headless runs.

    Each frame's pixels are a simple deterministic function of the frame index, so
    runs are reproducible. No randomness, no disk, no network.
    """

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        n_frames: int = 30,
        fps: float = 20.0,
    ) -> None:
        """Initialise the synthetic source.

        Args:
            width: Frame width in pixels.
            height: Frame height in pixels.
            n_frames: Number of frames to emit before exhausting.
            fps: Nominal frame rate used to compute timestamps.

        Raises:
            ValueError: If dimensions, count, or fps are non-positive.
        """
        if width <= 0 or height <= 0 or n_frames < 0 or fps <= 0:
            msg = "width/height/fps must be positive and n_frames non-negative"
            raise ValueError(msg)
        self.width = width
        self.height = height
        self.n_frames = n_frames
        self.fps = fps
        self._index = 0

    @property
    def is_available(self) -> bool:
        """Always available until exhausted."""
        return self._index < self.n_frames

    def read(self) -> Frame | None:
        """Return the next deterministic frame, or ``None`` when exhausted."""
        if self._index >= self.n_frames:
            return None
        # Deterministic content: a flat grey whose value depends on the index.
        value = np.uint8((self._index * 7) % 256)
        image = np.full((self.height, self.width, 3), value, dtype=np.uint8)
        frame = Frame(
            image=image,
            timestamp_ms=self._index * (1000.0 / self.fps),
            index=self._index,
        )
        self._index += 1
        return frame

    def close(self) -> None:
        """No resources to release."""
        self._index = self.n_frames
