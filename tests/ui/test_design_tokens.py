"""Design-token guarantees: parity across themes + WCAG AA contrast (Qt-free)."""

from __future__ import annotations

import pytest

from privacy_guard.ui.theme import tokens as T

pytestmark = pytest.mark.unit

THEMES = ("dark", "light")
AA_BODY = 4.5  # normal text
AA_LARGE = 3.0  # large text / UI components


def test_themes_define_identical_palette_keys() -> None:
    keys = {frozenset(T.PALETTE[t]) for t in THEMES}
    assert len(keys) == 1, "dark/light palettes must define the same names"


def test_themes_define_identical_state_keys() -> None:
    keys = {frozenset(T.STATE_COLORS[t]) for t in THEMES}
    assert len(keys) == 1
    assert frozenset(T.STATE_COLORS["dark"]) == {"clear", "protected", "paused", "error"}


def test_body_text_meets_aa_on_base_and_panel() -> None:
    for theme in THEMES:
        base = T.color(theme, "base")
        panel = T.color(theme, "panel")
        for ink in ("ink", "inkSoft"):
            fg = T.color(theme, ink)
            assert T.contrast_ratio(fg, base) >= AA_BODY, f"{theme}:{ink} on base"
            assert T.contrast_ratio(fg, panel) >= AA_BODY, f"{theme}:{ink} on panel"


def test_accent_and_state_colors_meet_aa_large_on_base() -> None:
    # Accent + state colours are used for UI components / large text -> AA large (3:1).
    for theme in THEMES:
        base = T.color(theme, "base")
        assert T.contrast_ratio(T.color(theme, "accent"), base) >= AA_LARGE
        for role in ("clear", "protected", "paused", "error"):
            assert T.contrast_ratio(T.state_color(theme, role), base) >= AA_LARGE, f"{theme}:{role}"


def test_contrast_ratio_is_symmetric_and_bounded() -> None:
    white, black = "#FFFFFF", "#000000"
    assert T.contrast_ratio(white, black) == pytest.approx(21.0, abs=0.1)
    assert T.contrast_ratio(white, black) == pytest.approx(T.contrast_ratio(black, white))
    assert T.contrast_ratio("#777777", "#777777") == pytest.approx(1.0)


def test_scales_are_monotonic() -> None:
    spacing = list(T.SPACING.values())
    assert spacing == sorted(spacing)
    type_scale = list(T.TYPE_SCALE.values())
    assert type_scale == sorted(type_scale)


def test_reduced_motion_is_shorter_than_signature_transition() -> None:
    assert T.MOTION["veil_settle"] > T.REDUCED_MOTION_MS
