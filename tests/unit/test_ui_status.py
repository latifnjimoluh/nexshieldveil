"""Unit tests for the pure UI presentation helpers (no Qt needed)."""

from __future__ import annotations

import pytest

from privacy_guard.policy import PolicyState
from privacy_guard.ui import face_tag, sensitivity_descriptor, status_badge

pytestmark = pytest.mark.unit


def test_status_badge_masked_takes_precedence() -> None:
    # Masked wins regardless of the underlying state.
    for state in PolicyState:
        badge = status_badge(state, masked=True)
        assert badge.label == "MASQUÉ"
        assert badge.color == "#e23b3b"


def test_status_badge_observer_detected_is_amber() -> None:
    badge = status_badge(PolicyState.OBSERVER_DETECTED, masked=False)
    assert badge.label == "OBSERVATEUR…"
    assert badge.color == "#e0a020"


def test_status_badge_clear_is_green() -> None:
    badge = status_badge(PolicyState.CLEAR, masked=False)
    assert badge.label == "CLAIR"
    assert badge.color == "#27ae60"


def test_face_tag_primary_beats_looking() -> None:
    # A primary user is always shown as primary even if their gaze hits the screen.
    tag = face_tag(is_primary=True, is_looking=True)
    assert tag.label == "principal"
    assert tag.color == "#9aa0a6"


def test_face_tag_observer_looking_is_red() -> None:
    tag = face_tag(is_primary=False, is_looking=True)
    assert tag.label == "REGARDE"
    assert tag.color == "#e23b3b"


def test_face_tag_not_looking_is_green() -> None:
    tag = face_tag(is_primary=False, is_looking=False)
    assert tag.label == "ne regarde pas"
    assert tag.color == "#27ae60"


@pytest.mark.parametrize(
    ("deg", "word"),
    [
        (5.0, "strict"),
        (10.0, "strict"),
        (11.0, "équilibré"),
        (18.0, "équilibré"),
        (20.0, "équilibré"),
        (25.0, "large"),
        (30.0, "large"),
        (40.0, "très large"),
    ],
)
def test_sensitivity_descriptor_boundaries(deg: float, word: str) -> None:
    assert sensitivity_descriptor(deg) == word
