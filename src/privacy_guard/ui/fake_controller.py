"""A hand-drivable :class:`AppController` for headless tests and QML previews.

It adds no behaviour beyond the base — it only exposes convenience helpers to *push*
states/errors/faces in, and records the intent signals so tests can assert that a
command reached the controller without wiring a real pipeline.
"""

from __future__ import annotations

from PySide6.QtCore import QObject

from privacy_guard.policy import PolicyState
from privacy_guard.ui.controller import AppController
from privacy_guard.ui.state import CameraError, UiSnapshot


class FakeController(AppController):
    """Drive the controller by hand; record intents (settings/onboarding/quit)."""

    def __init__(self, snapshot: UiSnapshot | None = None, parent: QObject | None = None) -> None:
        """Start from an optional snapshot and begin recording intents."""
        super().__init__(snapshot, parent)
        self.settings_opened = 0
        self.about_opened = 0
        self.onboarding_done = 0
        self.quit_calls = 0
        self.settings_requested.connect(self._count_settings)
        self.about_requested.connect(self._count_about)
        self.onboarding_finished.connect(self._count_onboarding)
        self.quit_requested.connect(self._count_quit)

    def _count_settings(self) -> None:
        self.settings_opened += 1

    def _count_about(self) -> None:
        self.about_opened += 1

    def _count_onboarding(self) -> None:
        self.onboarding_done += 1

    def _count_quit(self) -> None:
        self.quit_calls += 1

    # ---- push helpers (simulate the core) -------------------------------- #
    def emit_running(self, running: bool) -> None:
        """Force the running flag (bypassing the enable/pause commands)."""
        self._update(running=running)

    def emit_masked(self, masked: bool, *, policy_state: PolicyState | None = None) -> None:
        """Simulate the veil engaging/lifting, optionally setting the policy state."""
        state = policy_state or (PolicyState.MASKED if masked else PolicyState.CLEAR)
        self._update(is_masked=masked, policy_state=state, running=True, error_kind=None)

    def emit_observer_detected(self) -> None:
        """Simulate the transient 'observer spotted, not yet masked' phase."""
        self._update(
            running=True,
            error_kind=None,
            is_masked=False,
            policy_state=PolicyState.OBSERVER_DETECTED,
        )

    def emit_error(self, error: CameraError | None) -> None:
        """Simulate a camera/detection error appearing (or clearing with ``None``)."""
        self._update(running=True, error_kind=error)

    def emit_camera_active(self, active: bool) -> None:
        """Simulate the camera starting/stopping frame delivery."""
        self._update(camera_active=active)

    def emit_faces(self, count: int) -> None:
        """Simulate the number of detected faces (never an image, never an identity)."""
        self._update(faces_count=max(0, count))
