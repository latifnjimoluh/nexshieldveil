"""Performance budgets for the masking transforms at real screen resolutions.

M-FP1 of docs/ROADMAP_FLOU_PIXELISATION.md: before wiring blur/pixelate to the
live overlay (freeze-frame path), the transforms must handle full-screen captures
within budget. The opaque veil is shown instantly while the transform runs (P1),
so these budgets bound how long the veil stays plain, not the masking latency.

Budgets (per the roadmap): < 150 ms at 1080p, < 400 ms at 4K, with the *default*
config parameters (blur_radius=21, pixelate_blocks=24).
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from privacy_guard.config import MaskingConfig
from privacy_guard.masking import make_mask_strategy

pytestmark = [pytest.mark.performance, pytest.mark.slow]

BUDGET_1080P_MS = 150.0
BUDGET_4K_MS = 400.0

RESOLUTIONS = {
    "1080p": (1080, 1920, BUDGET_1080P_MS),
    "4k": (2160, 3840, BUDGET_4K_MS),
}

_rng = np.random.default_rng(42)


def _screen_like(h: int, w: int) -> np.ndarray:
    # Noise, not a flat fill: realistic worst case for cache behaviour and unique
    # colours, and it defeats any accidental constant-input fast path.
    return _rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


def _best_of(strategy_name: str, image: np.ndarray, runs: int = 3) -> float:
    """Best-of-N wall time in ms (best-of absorbs CI scheduler noise)."""
    strategy = make_mask_strategy(MaskingConfig(strategy=strategy_name))  # type: ignore[arg-type]
    best = float("inf")
    for _ in range(runs):
        start = time.perf_counter()
        out = strategy.apply(image)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        best = min(best, elapsed_ms)
    assert out.shape == image.shape
    assert out.dtype == np.uint8
    return best


@pytest.mark.parametrize("res", RESOLUTIONS)
@pytest.mark.parametrize("strategy_name", ["blur", "pixelate", "veil"])
def test_mask_transform_within_screen_budget(strategy_name: str, res: str) -> None:
    h, w, budget_ms = RESOLUTIONS[res]
    elapsed = _best_of(strategy_name, _screen_like(h, w))
    assert elapsed < budget_ms, (
        f"{strategy_name} on {res} ({w}x{h}) took {elapsed:.1f} ms, budget {budget_ms} ms"
    )
