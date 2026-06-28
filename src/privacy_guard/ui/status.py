"""Pure presentation helpers for the UI (no Qt import, fully unit-testable).

These map decision state into the text/colour shown on the status badge and on each
detected face, so the visual mapping is tested headlessly while the Qt widgets stay
out of coverage.
"""

from __future__ import annotations

from dataclasses import dataclass

from privacy_guard.policy import PolicyState

# Shared palette (hex), reused by the status badge and face tags.
_GREEN = "#27ae60"
_AMBER = "#e0a020"
_RED = "#e23b3b"
_GREY = "#9aa0a6"


@dataclass(frozen=True)
class StatusBadge:
    """Label + colour describing the overall masking state."""

    label: str
    color: str


@dataclass(frozen=True)
class FaceTag:
    """Label + colour describing one detected face's role."""

    label: str
    color: str


def status_badge(state: PolicyState, masked: bool) -> StatusBadge:
    """Map the policy state to the top status badge (text + hex colour)."""
    if masked:
        return StatusBadge("MASQUÉ", _RED)
    if state is PolicyState.OBSERVER_DETECTED:
        return StatusBadge("OBSERVATEUR…", _AMBER)
    return StatusBadge("CLAIR", _GREEN)


def sensitivity_descriptor(tolerance_deg: float) -> str:
    """Short qualitative word for a gaze-tolerance value, in degrees.

    Higher tolerance = the veil engages more readily (a gaze counts as "looking at
    the screen" even when fairly off-axis); lower tolerance = stricter (the gaze must
    point almost straight at the screen). 18 deg is the balanced default.
    """
    if tolerance_deg <= 10.0:
        return "strict"
    if tolerance_deg <= 20.0:
        return "équilibré"
    if tolerance_deg <= 30.0:
        return "large"
    return "très large"


def face_tag(*, is_primary: bool, is_looking: bool) -> FaceTag:
    """Map a face's role to its on-preview tag (text + hex colour).

    Precedence: the primary user is always shown as primary (their gaze is exempt),
    otherwise a looking face is the observer that drives masking.
    """
    if is_primary:
        return FaceTag("principal", _GREY)
    if is_looking:
        return FaceTag("REGARDE", _RED)
    return FaceTag("ne regarde pas", _GREEN)
