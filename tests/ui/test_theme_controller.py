"""Tests for the Qt ThemeController (dark/light + reduced-motion exposure)."""

from __future__ import annotations

import pytest

from privacy_guard.ui.theme import tokens as T
from privacy_guard.ui.theme.theme_controller import ThemeController

pytestmark = pytest.mark.unit


def test_dark_light_switch_changes_palette(qapp) -> None:
    theme = ThemeController(dark=True)
    assert theme.property("base") == T.color("dark", "base")
    theme.toggle()
    assert theme.property("is_dark") is False
    assert theme.property("base") == T.color("light", "base")


def test_theme_changed_emitted_on_toggle(qapp, record) -> None:
    theme = ThemeController(dark=True)
    events = record(theme.theme_changed)
    theme.toggle()
    assert len(events) == 1


def test_state_color_follows_theme(qapp) -> None:
    assert ThemeController(dark=True).stateColor("protected") == T.state_color("dark", "protected")
    assert ThemeController(dark=False).stateColor("protected") == T.state_color(
        "light", "protected"
    )


def test_duration_collapses_under_reduced_motion(qapp) -> None:
    theme = ThemeController(reduced_motion=False)
    assert theme.duration("veil_settle") == T.MOTION["veil_settle"]
    theme.setProperty("reduced_motion", True)
    assert theme.duration("veil_settle") == T.REDUCED_MOTION_MS
    assert theme.duration("quick") == T.REDUCED_MOTION_MS


def test_token_lookups(qapp) -> None:
    theme = ThemeController()
    assert theme.space("md") == T.SPACING["md"]
    assert theme.radius("pill") == T.RADII["pill"]
    assert theme.fontSize("hero") == T.TYPE_SCALE["hero"]
