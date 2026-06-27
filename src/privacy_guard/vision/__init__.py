"""Face detection (geometry only, never identity)."""

from __future__ import annotations

from privacy_guard.vision.detector import FaceDetector, ScriptedFaceDetector
from privacy_guard.vision.mediapipe_detector import MediaPipeFaceDetector, mediapipe_available
from privacy_guard.vision.observation import FaceObservation

__all__ = [
    "FaceDetector",
    "FaceObservation",
    "MediaPipeFaceDetector",
    "ScriptedFaceDetector",
    "mediapipe_available",
]
