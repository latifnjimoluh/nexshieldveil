"""Shared deterministic scenario builders for the test suites.

Frames and observation scripts are generated in code (never loaded from disk) so
the suite is reproducible and respects the project's no-frame-persistence rule.
"""

from __future__ import annotations

import numpy as np
import pytest

from privacy_guard.vision import FaceObservation

FPS = 20.0  # 50 ms per frame


def primary_user() -> FaceObservation:
    """Central, large face = the primary user (its gaze is ignored)."""
    return FaceObservation(
        center_x=0.5,
        center_y=0.5,
        size=0.30,
        position_mm=np.array([0.0, -150.0, 500.0]),
        yaw_deg=0.0,
        pitch_deg=0.0,
    )


def observer_looking() -> FaceObservation:
    """Off-centre face positioned so a straight gaze lands on the screen."""
    return FaceObservation(
        center_x=0.85,
        center_y=0.45,
        size=0.08,
        position_mm=np.array([200.0, -150.0, 600.0]),
        yaw_deg=0.0,
        pitch_deg=0.0,
    )


def observer_looking_away() -> FaceObservation:
    """Off-centre face turned far to the side: not looking at the screen."""
    return FaceObservation(
        center_x=0.15,
        center_y=0.45,
        size=0.08,
        position_mm=np.array([-200.0, -150.0, 600.0]),
        yaw_deg=70.0,
        pitch_deg=0.0,
    )


def session_script(
    intro_clear: int = 10,
    observer_frames: int = 16,
    outro_clear: int = 30,
) -> list[list[FaceObservation]]:
    """A realistic session: user alone, an observer appears and lingers, then leaves."""
    script: list[list[FaceObservation]] = [[primary_user()] for _ in range(intro_clear)]
    script += [[primary_user(), observer_looking()] for _ in range(observer_frames)]
    script += [[primary_user()] for _ in range(outro_clear)]
    return script


@pytest.fixture
def make_primary_user():
    return primary_user


@pytest.fixture
def make_observer_looking():
    return observer_looking
