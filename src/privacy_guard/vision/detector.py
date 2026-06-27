"""Face detector interface and a deterministic scripted detector for tests."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from privacy_guard.capture.frame_source import Frame
from privacy_guard.vision.observation import FaceObservation


class FaceDetector(ABC):
    """Detects faces (as geometry, never identity) in a frame."""

    @abstractmethod
    def detect(self, frame: Frame) -> list[FaceObservation]:
        """Return the faces observed in ``frame`` (possibly empty)."""

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether the detector backend is usable."""

    def close(self) -> None:  # noqa: B027 - optional override; default is intentionally a no-op
        """Release any backend resources (no-op by default)."""


class ScriptedFaceDetector(FaceDetector):
    """Detector that replays a predetermined script of observations per frame.

    This is the deterministic backbone of integration/system tests: it lets the
    full pipeline run headless without MediaPipe or a camera, yet exercise the real
    geometry/policy/masking code paths.
    """

    def __init__(self, script: Sequence[Sequence[FaceObservation]]) -> None:
        """Initialise with one list of observations per frame.

        Args:
            script: ``script[i]`` is returned for the i-th call to :meth:`detect`.
                Once exhausted, subsequent calls return an empty list.
        """
        self._script: list[list[FaceObservation]] = [list(obs) for obs in script]
        self._call = 0

    @property
    def is_available(self) -> bool:
        """Always available."""
        return True

    def detect(self, frame: Frame) -> list[FaceObservation]:
        """Return the scripted observations for the current call index."""
        observations = self._script[self._call] if self._call < len(self._script) else []
        self._call += 1
        return list(observations)
