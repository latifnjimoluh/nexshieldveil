"""Unit + property tests for masking strategies."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from privacy_guard.config import MaskingConfig
from privacy_guard.masking import (
    RUNTIME_OVERLAY_STRATEGIES,
    BlurMask,
    MaskStrategy,
    PixelateMask,
    VeilMask,
    make_mask_strategy,
    overlay_strategy_is_live,
)

pytestmark = pytest.mark.unit

rng = np.random.default_rng(0)


def _noisy(h: int = 64, w: int = 80) -> np.ndarray:
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


def _constant(value: int = 120, h: int = 64, w: int = 80) -> np.ndarray:
    return np.full((h, w, 3), value, dtype=np.uint8)


ALL_STRATEGIES: list[MaskStrategy] = [
    VeilMask(opacity=0.9),
    PixelateMask(blocks=8),
    BlurMask(radius=5),
]


# --------------------------------------------------------------------------- #
# shared invariants
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("strategy", ALL_STRATEGIES, ids=lambda s: s.name)
def test_preserves_shape_and_dtype(strategy: MaskStrategy) -> None:
    img = _noisy()
    out = strategy.apply(img)
    assert out.shape == img.shape
    assert out.dtype == np.uint8


@pytest.mark.parametrize("strategy", ALL_STRATEGIES, ids=lambda s: s.name)
def test_does_not_mutate_input(strategy: MaskStrategy) -> None:
    img = _noisy()
    snapshot = img.copy()
    strategy.apply(img)
    assert np.array_equal(img, snapshot)


@pytest.mark.parametrize("strategy", ALL_STRATEGIES, ids=lambda s: s.name)
def test_constant_image_stays_constant(strategy: MaskStrategy) -> None:
    # Blur/pixelate of a flat image is the same flat image; veil shifts it uniformly.
    img = _constant(120)
    out = strategy.apply(img)
    assert np.all(out == out[0, 0])


@pytest.mark.parametrize("strategy", ALL_STRATEGIES, ids=lambda s: s.name)
def test_rejects_non_rgb_image(strategy: MaskStrategy) -> None:
    with pytest.raises(ValueError, match="H, W, 3"):
        strategy.apply(np.zeros((10, 10), dtype=np.uint8))


# --------------------------------------------------------------------------- #
# VeilMask
# --------------------------------------------------------------------------- #
def test_veil_opacity_zero_is_identity() -> None:
    img = _noisy()
    assert np.array_equal(VeilMask(opacity=0.0).apply(img), img)


def test_veil_opacity_one_is_solid_color() -> None:
    img = _noisy()
    out = VeilMask(opacity=1.0, color=(16, 16, 16)).apply(img)
    assert np.all(out == 16)


def test_veil_rejects_bad_opacity() -> None:
    with pytest.raises(ValueError, match="opacity"):
        VeilMask(opacity=1.5)


@given(op=st.floats(0.0, 1.0))
@settings(max_examples=30)
def test_veil_reduces_or_preserves_contrast(op: float) -> None:
    img = _noisy()
    out = VeilMask(opacity=op, color=(0, 0, 0)).apply(img)
    # Blending toward a single colour never increases the spread of values.
    assert out.std() <= img.std() + 1e-6


# --------------------------------------------------------------------------- #
# PixelateMask
# --------------------------------------------------------------------------- #
def test_pixelate_reduces_distinct_colors() -> None:
    img = _noisy(64, 64)
    out = PixelateMask(blocks=8).apply(img)
    distinct_in = len(np.unique(img.reshape(-1, 3), axis=0))
    distinct_out = len(np.unique(out.reshape(-1, 3), axis=0))
    assert distinct_out < distinct_in
    assert distinct_out <= 8 * 8


def test_pixelate_rejects_too_few_blocks() -> None:
    with pytest.raises(ValueError, match="blocks"):
        PixelateMask(blocks=1)


# --------------------------------------------------------------------------- #
# BlurMask
# --------------------------------------------------------------------------- #
def test_blur_reduces_variance_of_noise() -> None:
    img = _noisy(96, 96)
    out = BlurMask(radius=6).apply(img)
    assert out.var() < img.var()


def test_blur_preserves_mean_approximately() -> None:
    img = _noisy(96, 96)
    out = BlurMask(radius=4).apply(img)
    assert out.mean() == pytest.approx(img.mean(), abs=2.0)


def test_blur_rejects_bad_radius() -> None:
    with pytest.raises(ValueError, match="radius"):
        BlurMask(radius=0)


# The wide-radius path (M-FP1) downsamples, blurs small, then upsamples. It must
# honour the exact same invariants as the direct path, including on image sizes
# that are not multiples of the internal scale (edge-pad branch).
@pytest.mark.parametrize(("h", "w"), [(96, 96), (97, 101)])
def test_blur_reduced_path_invariants(h: int, w: int) -> None:
    strategy = BlurMask(radius=21)
    assert strategy._scale_for(h, w) > 1  # guard: this size/radius takes the reduced path
    img = _noisy(h, w)
    out = strategy.apply(img)
    assert out.shape == img.shape
    assert out.dtype == np.uint8
    assert out.var() < img.var()
    assert out.mean() == pytest.approx(img.mean(), abs=2.0)


@pytest.mark.parametrize(("h", "w"), [(96, 96), (97, 101)])
def test_blur_reduced_path_keeps_flat_image_flat(h: int, w: int) -> None:
    out = BlurMask(radius=21).apply(_constant(120, h, w))
    assert np.all(out == 120)


def test_blur_reduced_path_close_to_direct_blur() -> None:
    # The downscale approximation must stay visually equivalent to the direct
    # full-resolution box blur. Pure noise is the worst case; the size is large
    # enough that edge-clamp differences don't dominate the statistics.
    img = _noisy(360, 480)
    strategy = BlurMask(radius=21)
    reduced = strategy.apply(img).astype(np.float64)
    direct = img.astype(np.float32)
    direct = strategy._blur_axis(direct, strategy.radius, axis=0)
    direct = strategy._blur_axis(direct, strategy.radius, axis=1)
    diff = np.abs(reduced - np.clip(direct + 0.5, 0, 255).astype(np.uint8))
    assert diff.mean() < 2.0
    assert np.percentile(diff, 99) < 12.0


def test_blur_scale_grows_with_radius_and_clamps_on_small_images() -> None:
    assert BlurMask(radius=5)._scale_for(2160, 3840) == 1  # weak blur: direct path
    assert BlurMask(radius=21)._scale_for(2160, 3840) == 3
    assert BlurMask(radius=199)._scale_for(2160, 3840) == 8  # capped
    assert BlurMask(radius=21)._scale_for(40, 40) == 1  # never below ~32 px a side


# --------------------------------------------------------------------------- #
# factory
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", ["veil", "pixelate", "blur"])
def test_factory_builds_configured_strategy(name: str) -> None:
    strategy = make_mask_strategy(MaskingConfig(strategy=name))  # type: ignore[arg-type]
    assert strategy.name == name
    out = strategy.apply(_noisy())
    assert out.shape == (64, 80, 3)


# --------------------------------------------------------------------------- #
# live-overlay support (since M-FP5 all three strategies are wired live)
# --------------------------------------------------------------------------- #
def test_all_configured_strategies_are_live_on_the_overlay() -> None:
    assert overlay_strategy_is_live("veil") is True
    assert overlay_strategy_is_live("pixelate") is True
    assert overlay_strategy_is_live("blur") is True
    assert set(RUNTIME_OVERLAY_STRATEGIES) == {"veil", "pixelate", "blur"}


def test_unknown_strategies_are_still_gated() -> None:
    # The honesty gate stays meaningful for anything not actually implemented.
    assert overlay_strategy_is_live("hologram") is False
