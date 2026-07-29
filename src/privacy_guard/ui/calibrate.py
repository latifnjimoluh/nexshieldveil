"""Applying the detected screen size to the running config (AM-10).

The judgement lives in :mod:`privacy_guard.geometry.calibration` (pure) and the
reading in :mod:`privacy_guard.ui.screen_probe` (Qt). This is the thin seam
between them, kept Qt-free so the merge rule itself is unit-tested: the probe is
injected, so a test can hand it any reading — including a nonsensical one.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from privacy_guard.config import AppConfig, GeometryConfig
from privacy_guard.geometry import resolve_screen_size

logger = logging.getLogger("privacy_guard.ui")

ScreenProbe = Callable[[], tuple[float, float] | None]


def apply_detected_screen_size(
    config: AppConfig,
    explicit: bool = False,
    probe: ScreenProbe | None = None,
) -> AppConfig:
    """Return ``config`` with the screen size the OS reports, when believable.

    Args:
        config: The configuration to refine.
        explicit: ``True`` when the user supplied a config file. A size someone
            typed is a deliberate statement about their setup and must beat any
            probe — including on a multi-monitor desk, where the primary screen
            may not be the one the camera sits above.
        probe: Injectable reader; defaults to the Qt primary-screen probe.

    Returns:
        The same config, or a copy with ``geometry`` updated.
    """
    if probe is None:  # pragma: no cover - the default path needs a display
        from privacy_guard.ui.screen_probe import primary_screen_mm

        probe = primary_screen_mm

    try:
        reported = probe()
    except Exception as exc:  # a screen probe must never take startup down
        logger.warning("Screen-size probe failed (%s); keeping the configured size.", exc)
        reported = None

    resolved = resolve_screen_size(
        reported=reported,
        fallback=(config.geometry.screen_width_mm, config.geometry.screen_height_mm),
        prefer_reported=not explicit,
    )
    if not resolved.auto_detected:
        return config

    logger.info(
        "Screen measured at %.0f x %.0f mm (was %.0f x %.0f).",
        resolved.width_mm,
        resolved.height_mm,
        config.geometry.screen_width_mm,
        config.geometry.screen_height_mm,
    )
    geometry = GeometryConfig(
        **{
            **config.geometry.model_dump(),
            "screen_width_mm": resolved.width_mm,
            "screen_height_mm": resolved.height_mm,
        }
    )
    return config.model_copy(update={"geometry": geometry})
