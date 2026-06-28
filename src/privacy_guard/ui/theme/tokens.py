"""Design tokens — the single source of truth, mirrored in ``docs/DESIGN_TOKENS.md``.

Pure data + a couple of WCAG contrast helpers. No Qt here, so the palette and its
contrast guarantees are tested without a display.
"""

from __future__ import annotations

from typing import Literal

ThemeName = Literal["dark", "light"]

# Core palette per theme: a cool slate base + one diffused-aqua accent (not neon).
PALETTE: dict[str, dict[str, str]] = {
    "dark": {
        "base": "#13161B",
        "panel": "#1C212A",
        "line": "#2C333F",
        "ink": "#EAEEF4",
        "inkSoft": "#9CA7B6",
        "accent": "#74C7D6",
    },
    "light": {
        "base": "#EEF1F5",
        "panel": "#F7F9FC",
        "line": "#D3DAE3",
        "ink": "#1B2129",
        "inkSoft": "#5A6675",
        "accent": "#1F7E92",
    },
}

# Semantic state colours. 'protected' is reassuring (the accent), never alarming;
# 'error'/'paused' carry the attention.
STATE_COLORS: dict[str, dict[str, str]] = {
    "dark": {
        "clear": "#5FB58E",
        "protected": "#74C7D6",
        "paused": "#D9A441",
        "error": "#E0736A",
    },
    "light": {
        "clear": "#2E7D5B",
        "protected": "#1F7E92",
        "paused": "#9A6B12",
        "error": "#B4453C",
    },
}

# 4-based spacing scale.
SPACING: dict[str, int] = {
    "xxs": 2,
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "xxl": 32,
    "xxxl": 48,
}

# Generous radii for the frosted-glass material.
RADII: dict[str, int] = {"sm": 8, "md": 14, "lg": 20, "pill": 999}

# Type scale (px).
TYPE_SCALE: dict[str, int] = {
    "caption": 12,
    "body": 14,
    "base": 16,
    "title": 20,
    "display": 26,
    "hero": 34,
}

# Free-licence font families (OFL). Fallbacks keep the app usable if a TTF is absent.
FONTS: dict[str, str] = {
    "display": "Space Grotesk",
    "ui": "Inter",
    "mono": "JetBrains Mono",
}
FONT_FALLBACKS: dict[str, str] = {
    "display": "Space Grotesk, Segoe UI, Helvetica, Arial, sans-serif",
    "ui": "Inter, Segoe UI, Helvetica, Arial, sans-serif",
    "mono": "JetBrains Mono, Consolas, Menlo, monospace",
}

# Motion durations (ms). 'veil_settle' is the signature 'a veil settling' transition.
MOTION: dict[str, int] = {"quick": 120, "standard": 200, "veil_settle": 420}
# When prefers-reduced-motion is on, durations collapse to a short opacity-only fade.
REDUCED_MOTION_MS = 80


def color(theme: ThemeName, name: str) -> str:
    """Return a palette colour for a theme (e.g. ``color('dark', 'accent')``)."""
    return PALETTE[theme][name]


def state_color(theme: ThemeName, role: str) -> str:
    """Return a semantic state colour for a theme (clear/protected/paused/error)."""
    return STATE_COLORS[theme][role]


def _channel(value: int) -> float:
    c = value / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """WCAG relative luminance of an ``#rrggbb`` colour."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG contrast ratio between two ``#rrggbb`` colours (>= 1.0)."""
    lf, lb = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(lf, lb), min(lf, lb)
    return (hi + 0.05) / (lo + 0.05)
