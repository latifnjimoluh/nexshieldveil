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


def _block_mean_grid(
    image: Image, block_h: int, block_w: int
) -> tuple[NDArray[np.float32], NDArray[np.int64], NDArray[np.int64]]:
    """Per-block mean colours over a (block_h, block_w) grid, fully vectorised.

    Returns ``(means, row_counts, col_counts)`` where ``means`` has one entry per
    grid cell and the counts are each cell's true pixel extent (edge cells may be
    smaller). ``np.repeat`` over the counts reconstructs the exact input shape.
    Sums are taken in int64 (exact for uint8 inputs of any screen size) before a
    single float32 divide.
    """
    h, w = image.shape[:2]
    y_starts = np.arange(0, h, block_h)
    x_starts = np.arange(0, w, block_w)
    sums = np.add.reduceat(
        np.add.reduceat(image.astype(np.int64), y_starts, axis=0), x_starts, axis=1
    )
    row_counts = np.diff(np.append(y_starts, h)).astype(np.int64)
    col_counts = np.diff(np.append(x_starts, w)).astype(np.int64)
    area = (row_counts[:, None] * col_counts[None, :]).astype(np.float32)
    means: NDArray[np.float32] = sums.astype(np.float32) / area[:, :, None]
    return means, row_counts, col_counts


def _phase_block_mean(image: Image, scale: int) -> NDArray[np.float32]:
    """(scale x scale) block means of an exactly divisible image, in float32.

    Accumulates the scale**2 strided sub-grids of the uint8 input directly into
    one float32 buffer of the reduced size — the fastest pure-numpy formulation
    measured (no full-size integer/float copy, no reduceat, no fancy indexing).
    """
    h, w = image.shape[:2]
    hs, ws = h // scale, w // scale
    acc = np.zeros((hs, ws, 3), dtype=np.float32)
    for dy in range(scale):
        for dx in range(scale):
            acc += image[dy::scale, dx::scale]
    acc *= np.float32(1.0 / (scale * scale))
    return acc


def _phase_weights(scale: int) -> list[float]:
    """Per-phase fractional offsets for an integer bilinear upscale.

    Output sample ``i = j*scale + k`` sits at fractional offset
    ``f = (k + 0.5)/scale - 0.5`` from grid cell ``j``: negative offsets blend
    with the previous cell, positive ones with the next.
    """
    return [(k + 0.5) / scale - 0.5 for k in range(scale)]


def _phase_bilinear_upsample_to_uint8(small: NDArray[np.float32], scale: int) -> Image:
    """Bilinear x``scale`` upsample of ``small`` straight to uint8, via phase slices.

    Because the upscale factor is an exact integer, every output row/column of a
    given phase ``k`` uses the same pair of source cells and the same weight, so
    the whole resize decomposes into ``scale`` shifted-view blends per axis — no
    index gather at all. Gathers were the measured bottleneck at 4K (cache-hostile
    at full resolution); shifted views run at sequential-copy speed.
    """
    hs, ws = small.shape[:2]
    # X phases while the height is still small.
    cols = np.empty((hs, ws * scale, 3), dtype=np.float32)
    prev_x = np.concatenate([small[:, :1], small[:, :-1]], axis=1)  # clamp-left shift
    next_x = np.concatenate([small[:, 1:], small[:, -1:]], axis=1)  # clamp-right shift
    for k, f in enumerate(_phase_weights(scale)):
        if f < 0.0:
            cols[:, k::scale] = prev_x * np.float32(-f) + small * np.float32(1.0 + f)
        elif f == 0.0:
            cols[:, k::scale] = small
        else:
            cols[:, k::scale] = small * np.float32(1.0 - f) + next_x * np.float32(f)
    # Y phases at full width, converting each phase straight to uint8 rows.
    out = np.empty((hs * scale, ws * scale, 3), dtype=np.uint8)
    prev_y = np.concatenate([cols[:1], cols[:-1]], axis=0)
    next_y = np.concatenate([cols[1:], cols[-1:]], axis=0)
    for k, f in enumerate(_phase_weights(scale)):
        if f < 0.0:
            tmp = prev_y * np.float32(-f) + cols * np.float32(1.0 + f)
        elif f == 0.0:
            tmp = cols.copy()
        else:
            tmp = cols * np.float32(1.0 - f) + next_y * np.float32(f)
        tmp += np.float32(0.5)  # half-up rounding under the truncating uint8 cast
        np.clip(tmp, 0, 255, out=tmp)
        out[k::scale] = tmp
    return out


def _to_uint8(work: NDArray[np.float32]) -> Image:
    """Round-then-clip back to uint8, mutating ``work`` (callers pass fresh arrays).

    Adding 0.5 before the truncating uint8 cast rounds half-up for the whole
    non-negative range, so flat float inputs (e.g. 119.9999 vs 120.0001 from
    float noise on a constant image) land on the same value.
    """
    work += np.float32(0.5)
    np.clip(work, 0, 255, out=work)
    return work.astype(np.uint8)


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
        """Return a block-averaged (pixelated) version of ``image``.

        Fully vectorised (no per-block Python loop): block sums via
        ``np.add.reduceat`` on both axes, then ``np.repeat`` to expand each mean
        back to its exact tile extent.
        """
        _validate_image(image)
        h, w = image.shape[:2]
        block_h = max(1, h // self.blocks)
        block_w = max(1, w // self.blocks)
        means, row_counts, col_counts = _block_mean_grid(image, block_h, block_w)
        tiles = _to_uint8(means)
        return np.repeat(np.repeat(tiles, row_counts, axis=0), col_counts, axis=1)


class BlurMask(MaskStrategy):
    """Box-blur the image with a configurable radius (separable, integral-image).

    Performance (M-FP1, docs/ROADMAP_FLOU_PIXELISATION.md): work happens in
    float32, and for wide radii (>= ``_DOWNSCALE_RADIUS_DIVISOR``) the image is
    first reduced by block means, blurred at the reduced size with a
    proportionally reduced radius, then bilinearly upsampled. Visually equivalent
    for a strong blur, and it keeps full-screen (1080p/4K) captures within the
    freeze-frame budget. Small radii on large images stay on the direct path:
    such a weak blur barely masks anything, so it is not the case to optimise.
    """

    _DOWNSCALE_RADIUS_DIVISOR = 6
    _MAX_DOWNSCALE = 8
    _MIN_REDUCED_SIDE = 32

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

    def _scale_for(self, h: int, w: int) -> int:
        """Downscale factor: grows with the radius, never shrinks a side below 32 px."""
        scale = min(self._MAX_DOWNSCALE, max(1, self.radius // self._DOWNSCALE_RADIUS_DIVISOR))
        return min(scale, max(1, min(h, w) // self._MIN_REDUCED_SIDE))

    def apply(self, image: Image) -> Image:
        """Return a box-blurred version of ``image``."""
        _validate_image(image)
        h, w = image.shape[:2]
        scale = self._scale_for(h, w)
        if scale == 1:
            work = image.astype(np.float32)
            work = self._blur_axis(work, self.radius, axis=0)
            work = self._blur_axis(work, self.radius, axis=1)
            return _to_uint8(work)
        # Reduced path: edge-pad to an exact multiple of ``scale`` (usually a
        # no-op for real screen sizes), block-mean down, blur at the reduced
        # size with a proportionally reduced radius, then phase-bilinear back up.
        pad_y = -h % scale
        pad_x = -w % scale
        work_img = image
        if pad_y or pad_x:
            work_img = np.pad(image, ((0, pad_y), (0, pad_x), (0, 0)), mode="edge")
        small = _phase_block_mean(work_img, scale)
        reduced_radius = max(1, round(self.radius / scale))
        small = self._blur_axis(small, reduced_radius, axis=0)
        small = self._blur_axis(small, reduced_radius, axis=1)
        out = _phase_bilinear_upsample_to_uint8(small, scale)
        if pad_y or pad_x:
            return np.ascontiguousarray(out[:h, :w])
        return out

    @staticmethod
    def _blur_axis(a: NDArray[np.float32], r: int, axis: int) -> NDArray[np.float32]:
        window = 2 * r + 1
        n = a.shape[axis]
        pad_width = [(0, 0)] * a.ndim
        pad_width[axis] = (r, r)
        padded = np.pad(a, pad_width, mode="edge")
        csum = np.cumsum(padded, axis=axis, dtype=np.float32)
        zero_shape = list(csum.shape)
        zero_shape[axis] = 1
        csum = np.concatenate([np.zeros(zero_shape, dtype=np.float32), csum], axis=axis)
        hi = [slice(None)] * a.ndim
        lo = [slice(None)] * a.ndim
        hi[axis] = slice(window, window + n)
        lo[axis] = slice(0, n)
        result: NDArray[np.float32] = (csum[tuple(hi)] - csum[tuple(lo)]) / np.float32(window)
        return result


# Strategies the *live overlay* can apply today. The overlay only paints an
# opaque veil; it does not capture the screen, so the pixel-transforming
# strategies (pixelate/blur) are tested building blocks for the future
# capture-based masking path and are NOT yet wired to the live overlay.
RUNTIME_OVERLAY_STRATEGIES = frozenset({"veil"})


def overlay_strategy_is_live(strategy: str) -> bool:
    """Whether ``strategy`` is actually applied by the live overlay today.

    ``pixelate``/``blur`` require capturing on-screen pixels (a future evolution),
    so selecting them at runtime falls back to an opaque veil with a warning.
    """
    return strategy in RUNTIME_OVERLAY_STRATEGIES


def make_mask_strategy(config: MaskingConfig) -> MaskStrategy:
    """Build the configured :class:`MaskStrategy` from a :class:`MaskingConfig`.

    Note: this builds the pure image transform. Whether the *live overlay* applies
    it is a separate question — see :func:`overlay_strategy_is_live`.
    """
    if config.strategy == "veil":
        return VeilMask(opacity=config.opacity)
    if config.strategy == "pixelate":
        return PixelateMask(blocks=config.pixelate_blocks)
    if config.strategy == "blur":
        return BlurMask(radius=config.blur_radius)
    msg = f"Unknown masking strategy: {config.strategy}"  # pragma: no cover - guarded by config
    raise ValueError(msg)
