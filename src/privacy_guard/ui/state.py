"""Pure, Qt-free UI state: enums, an immutable snapshot, and the state mapping.

This is the testable heart of the presentation layer's *data*. It turns what the
core reports (a :class:`~privacy_guard.policy.PolicyState`, camera availability,
errors) into the small vocabulary the UI speaks (:class:`ProtectionState`). No Qt,
no hardware — so every mapping rule is exercised headlessly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from privacy_guard.policy import PolicyState


class ProtectionState(Enum):
    """The four states the UI ever shows the user.

    Deliberately smaller than the core's :class:`PolicyState`: the user does not need
    to distinguish ``OBSERVER_DETECTED`` from ``CLEAR`` (that is a transient hint, see
    :func:`is_engaging`), but does need to know when the app is paused or errored.
    """

    CLEAR = "clear"  # running, watching, nobody snooping
    PROTECTED = "protected"  # the veil is engaged
    PAUSED = "paused"  # the user paused; camera released
    CAMERA_ERROR = "camera_error"  # something needs the user's attention


class CameraError(Enum):
    """Why the camera/detection path cannot run. Each maps to an actionable message."""

    NO_CAMERA = "no_camera"
    DISCONNECTED = "disconnected"
    PERMISSION_DENIED = "permission_denied"
    MODEL_UNAVAILABLE = "model_unavailable"


def derive_protection_state(
    *, running: bool, error_kind: CameraError | None, is_masked: bool
) -> ProtectionState:
    """Combine the core signals into the single state the UI displays.

    Precedence (documented in ``docs/UI_PLAN.md`` §2):

    1. Not running -> ``PAUSED`` (an explicit user choice; the camera is released, so
       any stale error is irrelevant).
    2. Running with an error -> ``CAMERA_ERROR`` (we cannot trust ``is_masked`` then).
    3. Running, no error, masked -> ``PROTECTED``.
    4. Otherwise -> ``CLEAR``.
    """
    if not running:
        return ProtectionState.PAUSED
    if error_kind is not None:
        return ProtectionState.CAMERA_ERROR
    if is_masked:
        return ProtectionState.PROTECTED
    return ProtectionState.CLEAR


def is_engaging(policy_state: PolicyState) -> bool:
    """Whether an observer has been spotted but the veil has not engaged *yet*.

    Used only as a subtle visual hint on top of ``CLEAR`` ("observer spotted…"); it
    never changes the logical :class:`ProtectionState`, to avoid icon flicker.
    """
    return policy_state is PolicyState.OBSERVER_DETECTED


@dataclass(frozen=True)
class UiSnapshot:
    """Immutable, Qt-free view of everything the UI needs for one moment in time.

    The controller produces snapshots; view-models read them. Frozen so a snapshot
    can be passed around and compared without anyone mutating shared UI state.
    """

    running: bool = False
    error_kind: CameraError | None = None
    is_masked: bool = False
    policy_state: PolicyState = PolicyState.CLEAR
    camera_active: bool = False
    faces_count: int = 0
    # Mirrors of the relevant config the UI lets the user change.
    masking_strategy: str = "veil"
    sensitivity_deg: float = 18.0
    trigger_ms: int = 400
    release_ms: int = 800
    camera_index: int = 0
    start_at_login: bool = False

    @property
    def protection_state(self) -> ProtectionState:
        """The state the UI shows, derived from the core signals."""
        return derive_protection_state(
            running=self.running, error_kind=self.error_kind, is_masked=self.is_masked
        )

    @property
    def engaging(self) -> bool:
        """Whether to show the transient 'observer spotted…' hint."""
        return self.running and self.error_kind is None and is_engaging(self.policy_state)
