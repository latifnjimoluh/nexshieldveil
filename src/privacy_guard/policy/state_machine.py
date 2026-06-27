"""Decision state machine with hysteresis (anti-flicker).

Pure logic, no hardware dependency. The machine consumes a per-frame boolean
("is an *observer* — i.e. a non-primary face — currently looking at the screen?")
plus a timestamp in milliseconds, and decides whether the masking layer should be
engaged.

Hysteresis (two independent time thresholds) prevents rapid on/off flicker:

* Masking engages only after the observer has been looking for ``trigger_ms``.
* Masking lifts only after the observer has been absent for ``release_ms``
  (``release_ms >= trigger_ms`` by config invariant).

States::

    CLEAR --observer present--> OBSERVER_DETECTED --sustained--> MASKED
      ^                                  |                          |
      |                       observer gone (before trigger)        |
      +----------------------------------+                          |
      ^                                                             |
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


class DecisionStateMachine:
    """Hysteresis state machine driving the masking layer."""

    def __init__(self, trigger_ms: float, release_ms: float) -> None:
        """Initialise the machine.

        Args:
            trigger_ms: Sustained observer-gaze duration before masking engages.
            release_ms: Sustained observer-absence duration before masking lifts.

        Raises:
            ValueError: If either threshold is negative, or ``release_ms`` is below
                ``trigger_ms`` (which would defeat the anti-flicker hysteresis).
        """
        if trigger_ms < 0 or release_ms < 0:
            msg = "trigger_ms and release_ms must be non-negative"
            raise ValueError(msg)
        if release_ms < trigger_ms:
            msg = "release_ms must be >= trigger_ms for hysteresis"
            raise ValueError(msg)
        self.trigger_ms = float(trigger_ms)
        self.release_ms = float(release_ms)
        self._state = PolicyState.CLEAR
        self._observer_since: float | None = None
        self._absent_since: float | None = None

    @classmethod
    def from_config(cls, cfg: PolicyConfig) -> DecisionStateMachine:
        """Build a machine from a :class:`PolicyConfig`."""
        return cls(trigger_ms=cfg.trigger_ms, release_ms=cfg.release_ms)

    @property
    def state(self) -> PolicyState:
        """The current state."""
        return self._state

    @property
    def is_masked(self) -> bool:
        """Whether the masking layer should currently be engaged."""
        return self._state is PolicyState.MASKED

    def reset(self) -> None:
        """Return to the initial CLEAR state and clear all timers."""
        self._state = PolicyState.CLEAR
        self._observer_since = None
        self._absent_since = None

    def update(self, observer_present: bool, timestamp_ms: float) -> PolicyState:
        """Advance the machine by one observation.

        Args:
            observer_present: Whether a non-primary observer is looking at the screen.
            timestamp_ms: Monotonic timestamp of this observation, in milliseconds.

        Returns:
            The (possibly unchanged) state after processing the observation.
        """
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
                    self._absent_since = None

        elif self._state is PolicyState.MASKED:
            if observer_present:
                self._absent_since = None
            else:
                if self._absent_since is None:
                    self._absent_since = timestamp_ms
                if timestamp_ms - self._absent_since >= self.release_ms:
                    self._state = PolicyState.CLEAR
                    self._observer_since = None
                    self._absent_since = None

        return self._state
