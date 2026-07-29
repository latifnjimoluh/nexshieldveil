"""Decision state machine with hysteresis (anti-flicker).

Pure logic, no hardware dependency. The machine consumes two per-frame booleans —
"is an *observer* (a non-primary face) looking at the screen?" and "is anybody in
front of the camera at all?" — plus a timestamp in milliseconds, and decides
whether the masking layer should be engaged.

Hysteresis (two independent time thresholds) prevents rapid on/off flicker:

* Masking engages only after the observer has been looking for ``trigger_ms``.
* Masking lifts only after the observer has been absent for ``release_ms``
  (``release_ms >= trigger_ms`` by config invariant).

**Walk-away lock (AM-7).** With ``absence_ms > 0``, masking also engages once *no*
face has been seen for that long. This covers the most banal leak of all — you
step away and someone sits down at your screen — which the observer path cannot:
with a single face in frame, that face is by definition the primary user, so its
gaze is ignored. We still identify nobody; we react to *absence*, not to who came
back. Disabled by default (``0``): it changes when the screen hides, so it is the
user's call.

States::

    CLEAR --observer present--> OBSERVER_DETECTED --sustained--> MASKED
      ^                                  |                          ^
      |                       observer gone (before trigger)        |
      +----------------------------------+                         |
      ^                                       nobody for absence_ms |
      |                                  CLEAR --------------------+
      +-------------------- observer absent for release_ms ---------+
"""

from __future__ import annotations

from enum import Enum

from privacy_guard.config import PolicyConfig


class PolicyState(Enum):
    """States of the masking decision machine."""

    CLEAR = "clear"
    OBSERVER_DETECTED = "observer_detected"
    MASKED = "masked"


class MaskReason(Enum):
    """Why the masking layer is currently engaged (surfaced to the user)."""

    OBSERVER = "observer"  # someone else is looking at the screen
    ABSENCE = "absence"  # nobody in front of the camera (walk-away lock)


class DecisionStateMachine:
    """Hysteresis state machine driving the masking layer."""

    def __init__(self, trigger_ms: float, release_ms: float, absence_ms: float = 0.0) -> None:
        """Initialise the machine.

        Args:
            trigger_ms: Sustained observer-gaze duration before masking engages.
            release_ms: Sustained observer-absence duration before masking lifts.
            absence_ms: Sustained "no face at all" duration before the walk-away
                lock engages. ``0`` disables it.

        Raises:
            ValueError: If any threshold is negative, or ``release_ms`` is below
                ``trigger_ms`` (which would defeat the anti-flicker hysteresis).
        """
        if trigger_ms < 0 or release_ms < 0 or absence_ms < 0:
            msg = "trigger_ms, release_ms and absence_ms must be non-negative"
            raise ValueError(msg)
        if release_ms < trigger_ms:
            msg = "release_ms must be >= trigger_ms for hysteresis"
            raise ValueError(msg)
        self.trigger_ms = float(trigger_ms)
        self.release_ms = float(release_ms)
        self.absence_ms = float(absence_ms)
        self._state = PolicyState.CLEAR
        self._reason: MaskReason | None = None
        self._observer_since: float | None = None
        self._absent_since: float | None = None
        self._user_absent_since: float | None = None

    @classmethod
    def from_config(cls, cfg: PolicyConfig) -> DecisionStateMachine:
        """Build a machine from a :class:`PolicyConfig`."""
        return cls(trigger_ms=cfg.trigger_ms, release_ms=cfg.release_ms, absence_ms=cfg.absence_ms)

    @property
    def state(self) -> PolicyState:
        """The current state."""
        return self._state

    @property
    def is_masked(self) -> bool:
        """Whether the masking layer should currently be engaged."""
        return self._state is PolicyState.MASKED

    @property
    def mask_reason(self) -> MaskReason | None:
        """Why the mask is engaged, or ``None`` when it is not."""
        return self._reason if self._state is PolicyState.MASKED else None

    def reset(self) -> None:
        """Return to the initial CLEAR state and clear all timers."""
        self._state = PolicyState.CLEAR
        self._reason = None
        self._observer_since = None
        self._absent_since = None
        self._user_absent_since = None

    def update(
        self, observer_present: bool, timestamp_ms: float, user_present: bool = True
    ) -> PolicyState:
        """Advance the machine by one observation.

        Args:
            observer_present: Whether a non-primary observer is looking at the screen.
            timestamp_ms: Monotonic timestamp of this observation, in milliseconds.
            user_present: Whether *any* face is in front of the camera. Only used
                by the walk-away lock; defaults to ``True`` so callers that do not
                use it keep the previous behaviour exactly.

        Returns:
            The (possibly unchanged) state after processing the observation.
        """
        walked_away = self._update_absence(user_present, timestamp_ms)

        # The walk-away lock has already served its own delay, so it engages the
        # mask directly rather than going through the observer trigger.
        if walked_away and self._state is not PolicyState.MASKED:
            self._state = PolicyState.MASKED
            self._reason = MaskReason.ABSENCE
            self._observer_since = None
            self._absent_since = None
            return self._state

        if self._state is PolicyState.CLEAR and observer_present:
            self._state = PolicyState.OBSERVER_DETECTED
            self._observer_since = timestamp_ms

        # Not elif: allow CLEAR -> OBSERVER_DETECTED -> MASKED within one update
        # when trigger_ms == 0.
        if self._state is PolicyState.OBSERVER_DETECTED:
            if not observer_present:
                self._state = PolicyState.CLEAR
                self._observer_since = None
            else:
                since = timestamp_ms if self._observer_since is None else self._observer_since
                if timestamp_ms - since >= self.trigger_ms:
                    self._state = PolicyState.MASKED
                    self._reason = MaskReason.OBSERVER
                    self._absent_since = None

        elif self._state is PolicyState.MASKED:
            if observer_present or walked_away:
                # Keep the reason truthful about what is holding the mask *now*.
                self._reason = MaskReason.OBSERVER if observer_present else MaskReason.ABSENCE
                self._absent_since = None
            else:
                if self._absent_since is None:
                    self._absent_since = timestamp_ms
                if timestamp_ms - self._absent_since >= self.release_ms:
                    self._state = PolicyState.CLEAR
                    self._reason = None
                    self._observer_since = None
                    self._absent_since = None

        return self._state

    def _update_absence(self, user_present: bool, timestamp_ms: float) -> bool:
        """Whether the walk-away lock condition currently holds."""
        if self.absence_ms <= 0.0:  # feature off: never engage, never remember
            self._user_absent_since = None
            return False
        if user_present:
            self._user_absent_since = None
            return False
        if self._user_absent_since is None:
            self._user_absent_since = timestamp_ms
        return timestamp_ms - self._user_absent_since >= self.absence_ms
