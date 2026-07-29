"""Screen-size detection (AM-10): what to believe, and what to keep.

The OS reading comes from EDID data, which is routinely absent, rounded, or
plainly wrong. All the judgement is pure, so it is tested here without a display.
"""

from __future__ import annotations

import pytest

from privacy_guard.config import AppConfig
from privacy_guard.geometry import is_plausible_screen_mm, resolve_screen_size
from privacy_guard.ui.calibrate import apply_detected_screen_size

pytestmark = pytest.mark.unit

_DEFAULT = (520.0, 290.0)  # the 24" assumption the config ships with


# --------------------------------------------------------------------------- #
# plausibility
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("width", "height"),
    [
        (290.0, 170.0),  # 13" laptop
        (344.0, 194.0),  # 15.6" laptop
        (520.0, 290.0),  # 24" desktop
        (700.0, 390.0),  # 32" desktop
        (1200.0, 340.0),  # 49" ultrawide (32:9)
    ],
)
def test_real_displays_are_believed(width: float, height: float) -> None:
    assert is_plausible_screen_mm(width, height) is True


@pytest.mark.parametrize(
    ("width", "height", "why"),
    [
        (0.0, 0.0, "EDID absent — the most common failure by far"),
        (-520.0, 290.0, "negative"),
        (520.0, 0.0, "half-missing"),
        (60.0, 120.0, "a phone, and portrait"),
        (5000.0, 3000.0, "a video wall"),
        (520.0, 500.0, "aspect ratio no monitor has"),
        (2000.0, 100.0, "absurdly wide strip"),
    ],
)
def test_implausible_readings_are_rejected(width: float, height: float, why: str) -> None:
    assert is_plausible_screen_mm(width, height) is False, why


# --------------------------------------------------------------------------- #
# resolution between probe and config
# --------------------------------------------------------------------------- #
def test_a_believable_reading_wins_over_the_default() -> None:
    resolved = resolve_screen_size(reported=(290.0, 170.0), fallback=_DEFAULT)
    assert (resolved.width_mm, resolved.height_mm) == (290.0, 170.0)
    assert resolved.auto_detected is True


def test_no_reading_falls_back_to_the_config() -> None:
    resolved = resolve_screen_size(reported=None, fallback=_DEFAULT)
    assert (resolved.width_mm, resolved.height_mm) == _DEFAULT
    assert resolved.auto_detected is False


def test_a_nonsense_reading_falls_back_to_the_config() -> None:
    resolved = resolve_screen_size(reported=(0.0, 0.0), fallback=_DEFAULT)
    assert (resolved.width_mm, resolved.height_mm) == _DEFAULT
    assert resolved.auto_detected is False


def test_an_explicit_configuration_beats_the_probe() -> None:
    # Someone who typed their screen size made a deliberate statement about
    # their setup — including which screen the camera actually sits above.
    resolved = resolve_screen_size(
        reported=(290.0, 170.0), fallback=(600.0, 340.0), prefer_reported=False
    )
    assert (resolved.width_mm, resolved.height_mm) == (600.0, 340.0)
    assert resolved.auto_detected is False


# --------------------------------------------------------------------------- #
# merging into the app config
# --------------------------------------------------------------------------- #
def test_the_detected_size_reaches_the_geometry_config() -> None:
    config = apply_detected_screen_size(AppConfig(), probe=lambda: (290.0, 170.0))
    assert config.geometry.screen_width_mm == 290.0
    assert config.geometry.screen_height_mm == 170.0


def test_other_geometry_settings_are_preserved() -> None:
    base = AppConfig()
    base = base.model_copy(
        update={
            "geometry": base.geometry.model_copy(
                update={"gaze_tolerance_deg": 25.0, "camera_above_screen_mm": 40.0}
            )
        }
    )
    config = apply_detected_screen_size(base, probe=lambda: (290.0, 170.0))
    assert config.geometry.gaze_tolerance_deg == 25.0
    assert config.geometry.camera_above_screen_mm == 40.0


def test_an_unreadable_screen_leaves_the_config_untouched() -> None:
    base = AppConfig()
    assert apply_detected_screen_size(base, probe=lambda: None) is base


def test_an_explicit_config_file_is_left_untouched() -> None:
    base = AppConfig()
    result = apply_detected_screen_size(base, explicit=True, probe=lambda: (290.0, 170.0))
    assert result is base


def test_a_probe_that_raises_is_not_fatal() -> None:
    # This runs on the startup path: a screen probe failing must degrade to the
    # configured size, never take the whole application down.
    def boom() -> tuple[float, float] | None:
        raise RuntimeError("no display")

    base = AppConfig()
    result = apply_detected_screen_size(base, probe=boom)
    assert result.geometry.screen_width_mm == base.geometry.screen_width_mm
    assert result.geometry.screen_height_mm == base.geometry.screen_height_mm
