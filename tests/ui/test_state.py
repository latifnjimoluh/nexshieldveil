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
    color_role,
    derive_protection_state,
    detail_key,
    headline_key,
    is_engaging,
    primary_action_id,
    primary_action_label_key,
    sensitivity_key,
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


# --------------------------------------------------------------------------- #
# pure presentation mappings (keys/roles consumed by view-models)
# --------------------------------------------------------------------------- #
def test_color_role_covers_every_state() -> None:
    roles = {color_role(s) for s in ProtectionState}
    assert roles == {"protected", "clear", "paused", "error"}


def test_headline_key_shape() -> None:
    assert headline_key(ProtectionState.PROTECTED) == "status.protected.headline"
    assert headline_key(ProtectionState.CAMERA_ERROR) == "status.error.headline"


def test_detail_key_uses_engaging_hint_over_clear() -> None:
    from privacy_guard.policy import PolicyState

    snap = UiSnapshot(running=True, policy_state=PolicyState.OBSERVER_DETECTED)
    assert snap.protection_state is ProtectionState.CLEAR
    assert detail_key(snap) == "status.clear.engaging"


def test_detail_key_uses_error_detail_when_running_and_errored() -> None:
    snap = UiSnapshot(running=True, error_kind=CameraError.PERMISSION_DENIED)
    assert detail_key(snap) == "error.permission_denied.detail"


def test_primary_action_id_per_state() -> None:
    assert primary_action_id(UiSnapshot(running=False)) == "resume"
    assert primary_action_id(UiSnapshot(running=True)) == "pause"
    assert primary_action_id(UiSnapshot(running=True, error_kind=CameraError.NO_CAMERA)) == "retry"
    assert (
        primary_action_id(UiSnapshot(running=True, error_kind=CameraError.PERMISSION_DENIED))
        == "open_system_settings"
    )
    assert (
        primary_action_id(UiSnapshot(running=True, error_kind=CameraError.MODEL_UNAVAILABLE))
        == "open_docs"
    )


def test_primary_action_label_key_matches_catalog_shape() -> None:
    assert primary_action_label_key(UiSnapshot(running=False)) == "action.resume"
    assert primary_action_label_key(UiSnapshot(running=True)) == "action.pause"
    assert (
        primary_action_label_key(UiSnapshot(running=True, error_kind=CameraError.DISCONNECTED))
        == "error.disconnected.action"
    )


@pytest.mark.parametrize(
    ("deg", "key"),
    [(5.0, "strict"), (10.0, "strict"), (18.0, "balanced"), (25.0, "wide"), (40.0, "very_wide")],
)
def test_sensitivity_key_buckets(deg: float, key: str) -> None:
    assert sensitivity_key(deg) == key


def test_camera_error_enum_is_exhaustive() -> None:
    # Guard against silently dropping an error kind the UI must handle.
    assert {e.name for e in CameraError} == {
        "NO_CAMERA",
        "DISCONNECTED",
        "PERMISSION_DENIED",
        "MODEL_UNAVAILABLE",
    }
