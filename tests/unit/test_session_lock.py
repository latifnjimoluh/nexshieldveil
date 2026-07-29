"""Suspending watching while the session is locked (AM-14).

Only the decision is tested here — it is the part that can get the user's state
wrong. The platform monitors are thin OS adapters, verified manually (see the
module docstring for what is and is not implemented).
"""

from __future__ import annotations

import pytest

from privacy_guard.ui.session_lock import SessionSuspender

pytestmark = pytest.mark.unit


class _Watching:
    """Minimal stand-in for the controller's running state."""

    def __init__(self, running: bool = True) -> None:
        self.running = running
        self.pauses = 0
        self.resumes = 0

    def pause(self) -> None:
        self.running = False
        self.pauses += 1

    def resume(self) -> None:
        self.running = True
        self.resumes += 1


def _suspender(state: _Watching) -> SessionSuspender:
    return SessionSuspender(lambda: state.running, state.pause, state.resume)


def test_locking_pauses_active_watching() -> None:
    state = _Watching(running=True)
    _suspender(state).on_locked()
    assert state.running is False
    assert state.pauses == 1


def test_unlocking_resumes_what_the_lock_paused() -> None:
    state = _Watching(running=True)
    suspender = _suspender(state)
    suspender.on_locked()
    suspender.on_unlocked()
    assert state.running is True
    assert state.resumes == 1


def test_a_session_the_user_paused_stays_paused() -> None:
    # The whole point of remembering: unlocking must not silently start the
    # camera for someone who had deliberately turned watching off.
    state = _Watching(running=False)
    suspender = _suspender(state)
    suspender.on_locked()
    suspender.on_unlocked()
    assert state.running is False
    assert state.resumes == 0
    assert state.pauses == 0  # nothing to pause either


def test_repeated_lock_signals_are_idempotent() -> None:
    # Some platforms emit the lock signal more than once; a second one must not
    # overwrite the memory of what to restore (which would strand the user
    # paused after unlocking).
    state = _Watching(running=True)
    suspender = _suspender(state)
    suspender.on_locked()
    suspender.on_locked()
    suspender.on_locked()
    assert state.pauses == 1
    suspender.on_unlocked()
    assert state.running is True


def test_an_unlock_without_a_lock_does_nothing() -> None:
    # A stray unlock signal at startup must not start watching by itself.
    state = _Watching(running=False)
    suspender = _suspender(state)
    suspender.on_unlocked()
    assert state.resumes == 0
    assert state.running is False


def test_repeated_unlock_signals_do_not_resume_twice() -> None:
    state = _Watching(running=True)
    suspender = _suspender(state)
    suspender.on_locked()
    suspender.on_unlocked()
    suspender.on_unlocked()
    assert state.resumes == 1


def test_the_suspended_flag_tracks_the_lock() -> None:
    state = _Watching(running=True)
    suspender = _suspender(state)
    assert suspender.is_suspended is False
    suspender.on_locked()
    assert suspender.is_suspended is True
    suspender.on_unlocked()
    assert suspender.is_suspended is False


def test_a_full_lock_unlock_cycle_repeats_cleanly() -> None:
    state = _Watching(running=True)
    suspender = _suspender(state)
    for _ in range(5):
        suspender.on_locked()
        assert state.running is False
        suspender.on_unlocked()
        assert state.running is True
    assert state.pauses == 5
    assert state.resumes == 5


def test_the_state_restored_is_the_one_from_before_the_lock() -> None:
    # Documented contract: the suspender restores what was running when the
    # lock arrived. It does not re-read the state at unlock time, because the
    # only thing that could have changed it meanwhile is the suspender itself.
    state = _Watching(running=True)
    suspender = _suspender(state)
    suspender.on_locked()
    assert state.running is False  # only we touched it
    suspender.on_unlocked()
    assert state.running is True
