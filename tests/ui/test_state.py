"""Unit tests for the pure (Qt-free) UI state mapping.

This is the seam where 'what the core reports' becomes 'what the UI shows'. It must
be testable with no Qt, no camera, no display — so it lives in ``ui/state.py`` with
zero Qt imports.
"""

from __future__ import annotations

import pytest

from privacy_guard.policy import PolicyState
from privacy_guard.ui.state import (
    CameraError,
    ProtectionState,
    UiSnapshot,
    derive_protection_state,
    is_engaging,
)

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# derive_protection_state — the core mapping
# --------------------------------------------------------------------------- #
def test_paused_wins_over_everything() -> None:
    # A user who paused is not watching; we never show an error or 'protected' then.
    assert (
        derive_protection_state(running=False, error_kind=CameraError.NO_CAMERA, is_masked=True)
        is ProtectionState.PAUSED
    )


def test_error_shown_when_running_and_error_present() -> None:
    assert (
        derive_protection_state(running=True, error_kind=CameraError.DISCONNECTED, is_masked=False)
        is ProtectionState.CAMERA_ERROR
    )


def test_error_takes_precedence_over_masked_while_running() -> None:
    # If the camera errored we cannot trust 'masked'; surface the error instead.
    assert (
        derive_protection_state(
            running=True, error_kind=CameraError.PERMISSION_DENIED, is_masked=True
        )
        is ProtectionState.CAMERA_ERROR
    )


def test_protected_when_masked_and_no_error() -> None:
    assert (
        derive_protection_state(running=True, error_kind=None, is_masked=True)
        is ProtectionState.PROTECTED
    )


def test_clear_when_running_no_error_not_masked() -> None:
    assert (
        derive_protection_state(running=True, error_kind=None, is_masked=False)
        is ProtectionState.CLEAR
    )


# --------------------------------------------------------------------------- #
# is_engaging — the transient 'observer spotted, not yet masked' hint
# --------------------------------------------------------------------------- #
def test_is_engaging_only_for_observer_detected() -> None:
    assert is_engaging(PolicyState.OBSERVER_DETECTED) is True
    assert is_engaging(PolicyState.CLEAR) is False
    assert is_engaging(PolicyState.MASKED) is False


# --------------------------------------------------------------------------- #
# UiSnapshot — immutable transport from controller to view-models
# --------------------------------------------------------------------------- #
def test_snapshot_is_frozen() -> None:
    snap = UiSnapshot()
    with pytest.raises(Exception):  # noqa: B017 - dataclass FrozenInstanceError
        snap.faces_count = 3  # type: ignore[misc]


def test_snapshot_derived_state_matches_helper() -> None:
    snap = UiSnapshot(running=True, error_kind=None, is_masked=True)
    assert snap.protection_state is ProtectionState.PROTECTED
    snap2 = UiSnapshot(running=False)
    assert snap2.protection_state is ProtectionState.PAUSED


def test_snapshot_defaults_are_paused_until_started() -> None:
    # Before the user enables protection, the app is paused (camera not opened).
    assert UiSnapshot().protection_state is ProtectionState.PAUSED


def test_camera_error_enum_is_exhaustive() -> None:
    # Guard against silently dropping an error kind the UI must handle.
    assert {e.name for e in CameraError} == {
        "NO_CAMERA",
        "DISCONNECTED",
        "PERMISSION_DENIED",
        "MODEL_UNAVAILABLE",
    }
