"""Deciding the screen's physical size, instead of assuming a 24-inch one (AM-10).

``GeometryConfig`` defaults to 520 x 290 mm — a 24" 16:9 panel. On a 13" laptop
(~290 x 170 mm) the modelled rectangle is nearly **four times too large**, so the
"does this gaze land on my screen?" test is far more permissive than the
sensitivity slider suggests. Nobody is going to measure their screen with a ruler,
so the app should ask the operating system.

The OS answer cannot be trusted blindly, though: ``QScreen.physicalSize()`` comes
from EDID data, which is routinely absent (0 x 0), rounded to whole centimetres,
or plainly wrong on projectors, VMs and cheap adapters. This module is the pure
sanity filter between the two — it decides what to believe, and the Qt probe that
reads the value lives in the UI layer.
"""

from __future__ import annotations

from dataclasses import dataclass

# Bounds for a believable desktop/laptop display. Below: a phone or a bad EDID
# read. Above: a projector or a TV wall, where the gaze model is meaningless
# anyway and the configured value is more likely to be deliberate.
MIN_SCREEN_WIDTH_MM = 150.0
MAX_SCREEN_WIDTH_MM = 1500.0
MIN_SCREEN_HEIGHT_MM = 80.0
MAX_SCREEN_HEIGHT_MM = 900.0
# A real panel is between 4:3 (1.33) and 32:9 (3.56); anything outside means the
# reported millimetres do not describe the screen we are drawing on.
MIN_ASPECT = 1.2
MAX_ASPECT = 3.7


@dataclass(frozen=True)
class ScreenSize:
    """A screen's physical size, and where the number came from.

    ``auto_detected`` is what the UI needs to be honest: a size the OS gave us is
    worth showing as measured, a fallback is worth showing as an assumption.
    """

    width_mm: float
    height_mm: float
    auto_detected: bool


def is_plausible_screen_mm(width_mm: float, height_mm: float) -> bool:
    """Whether a reported physical size can describe a real display.

    Rejects the common EDID failure modes: zero/negative values, sizes that would
    be a phone or a stadium screen, and aspect ratios no monitor has.
    """
    if width_mm <= 0.0 or height_mm <= 0.0:
        return False
    if not MIN_SCREEN_WIDTH_MM <= width_mm <= MAX_SCREEN_WIDTH_MM:
        return False
    if not MIN_SCREEN_HEIGHT_MM <= height_mm <= MAX_SCREEN_HEIGHT_MM:
        return False
    return MIN_ASPECT <= width_mm / height_mm <= MAX_ASPECT


def resolve_screen_size(
    reported: tuple[float, float] | None,
    fallback: tuple[float, float],
    prefer_reported: bool = True,
) -> ScreenSize:
    """Pick the screen size to model, between the OS reading and the config.

    Args:
        reported: What the platform says, or ``None`` if it says nothing.
        fallback: The configured values (which are themselves defaults unless the
            user edited them).
        prefer_reported: ``False`` when the user set the size explicitly — an
            explicit choice always wins over a probe.

    Returns:
        The size to use, flagged with whether it was auto-detected.
    """
    if prefer_reported and reported is not None and is_plausible_screen_mm(*reported):
        return ScreenSize(float(reported[0]), float(reported[1]), auto_detected=True)
    return ScreenSize(float(fallback[0]), float(fallback[1]), auto_detected=False)
