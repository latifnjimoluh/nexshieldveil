"""The bundled-font loader must never crash, with or without font files present."""

from __future__ import annotations

import pytest

from privacy_guard.ui.fonts import load_bundled_fonts

pytestmark = pytest.mark.unit


def test_load_bundled_fonts_returns_a_list(qapp) -> None:
    # No .ttf files are vendored, so this is typically empty — but it must be a list
    # and must not raise (the app must start regardless of bundled fonts).
    result = load_bundled_fonts()
    assert isinstance(result, list)
