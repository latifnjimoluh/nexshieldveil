"""Masking strategies: pure image transforms that obscure sensitive content.

These operate on numpy image arrays only (no GPU, no cv2 dependency) so they are
fully unit-testable. The overlay adapter composites the result on screen.

Honesty note: masking hides content from a *casual* observer. It does not defend
against a camera recording the screen, an out-of-frame onlooker, or reflections;
see ``docs/LIMITATIONS.md``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from numpy.typing import NDArray

from privacy_guard.config import MaskingConfig

Image = NDArray[np.uint8]


def _validate_image(image: Image) -> None:
    if image.ndim != 3 or image.shape[2] != 3:
        msg = f"Expected an (H, W, 3) image, got shape {image.shape}"
        raise ValueError(msg)


class MaskStrategy(ABC):
    """Transforms an image into an obscured version of the same shape."""

    @abstractmethod
    def apply(self, image: Image) -> Image:
        """Return an obscured copy of ``image`` (same shape and dtype)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier for the strategy."""


class VeilMask(MaskStrategy):
    """Blend the image toward a solid colour by ``opacity`` (0 = clear, 1 = solid)."""

    def __init__(self, opacity: float = 0.92, color: tuple[int, int, int] = (16, 16, 16)) -> None:
        """Initialise the veil.

        Raises:
            ValueError: If ``opacity`` is outside ``[0, 1]``.
        """
        if not 0.0 <= opacity <= 1.0:
            msg = f"opacity must be in [0, 1], got {opacity}"
            raise ValueError(msg)
        self.opacity = opacity
        self.color = np.array(color, dtype=np.float64)

    @property
    def name(self) -> str:
        """Strategy identifier."""
        return "veil"

    def apply(self, image: Image) -> Image:
        """Blend ``image`` toward the veil colour."""
        _validate_image(image)
        blended = image.astype(np.float64) * (1.0 - self.opacity) + self.color * self.opacity
        return np.clip(blended, 0, 255).astype(np.uint8)


class PixelateMask(MaskStrategy):
    """Pixelate the image into coarse blocks so text/detail become unreadable."""

    def __init__(self, blocks: int = 24) -> None:
        """Initialise the pixelation.

        Args:
            blocks: Number of blocks along the larger image dimension (>= 2).

        Raises:
            ValueError: If ``blocks`` < 2.
        """
        if blocks < 2:
            msg = f"blocks must be >= 2, got {blocks}"
            raise ValueError(msg)
        self.blocks = blocks

    @property
    def name(self) -> str:
        """Strategy identifier."""
        return "pixelate"

    def apply(self, image: Image) -> Image:
        """Return a block-averaged (pixelated) version of ``image``."""
        _validate_image(image)
        h, w = image.shape[:2]
        block_h = max(1, h // self.blocks)
        block_w = max(1, w // self.blocks)
        out = image.copy()
        for y in range(0, h, block_h):
            for x in range(0, w, block_w):
                tile = image[y : y + block_h, x : x + block_w]
                mean = tile.reshape(-1, 3).mean(axis=0)
                out[y : y + block_h, x : x + block_w] = mean.astype(np.uint8)
        return out


class BlurMask(MaskStrategy):
    """Box-blur the image with a configurable radius (separable, integral-image)."""

    def __init__(self, radius: int = 21) -> None:
        """Initialise the blur.

        Args:
            radius: Box-blur radius in pixels (>= 1).

        Raises:
            ValueError: If ``radius`` < 1.
        """
        if radius < 1:
            msg = f"radius must be >= 1, got {radius}"
            raise ValueError(msg)
        self.radius = radius

    @property
    def name(self) -> str:
        """Strategy identifier."""
        return "blur"

    def apply(self, image: Image) -> Image:
        """Return a box-blurred version of ``image``."""
        _validate_image(image)
        work = image.astype(np.float64)
        work = self._blur_axis(work, self.radius, axis=0)
        work = self._blur_axis(work, self.radius, axis=1)
        return np.clip(work, 0, 255).astype(np.uint8)

    @staticmethod
    def _blur_axis(a: NDArray[np.float64], r: int, axis: int) -> NDArray[np.float64]:
        window = 2 * r + 1
        n = a.shape[axis]
        pad_width = [(0, 0)] * a.ndim
        pad_width[axis] = (r, r)
        padded = np.pad(a, pad_width, mode="edge")
        csum = np.cumsum(padded, axis=axis)
        zero_shape = list(csum.shape)
        zero_shape[axis] = 1
        csum = np.concatenate([np.zeros(zero_shape), csum], axis=axis)
        hi = [slice(None)] * a.ndim
        lo = [slice(None)] * a.ndim
        hi[axis] = slice(window, window + n)
        lo[axis] = slice(0, n)
        return (csum[tuple(hi)] - csum[tuple(lo)]) / window


def make_mask_strategy(config: MaskingConfig) -> MaskStrategy:
    """Build the configured :class:`MaskStrategy` from a :class:`MaskingConfig`."""
    if config.strategy == "veil":
        return VeilMask(opacity=config.opacity)
    if config.strategy == "pixelate":
        return PixelateMask(blocks=config.pixelate_blocks)
    if config.strategy == "blur":
        return BlurMask(radius=config.blur_radius)
    msg = f"Unknown masking strategy: {config.strategy}"  # pragma: no cover - guarded by config
    raise ValueError(msg)
