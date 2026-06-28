"""MediaPipe Face Landmarker wrapper (optional, degradable).

This is a hardware/heavy-library adapter. Both MediaPipe and OpenCV are optional;
if either is missing, or no local model is provided, construction fails with a
clear, catchable error so the application degrades gracefully (it keeps running,
masking can still be driven manually or by tests).

Honesty: head-pose/gaze from a webcam is approximate (typically 1.5-3 degrees of
error). The angles produced here are coarse and meant to be used with the generous,
configurable tolerance in :mod:`privacy_guard.geometry`.

The heavy inference path is excluded from coverage (`pragma: no cover`) because CI
runs headless without these libraries; it is exercised manually on a real machine.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from privacy_guard.capture.frame_source import Frame
from privacy_guard.vision.detector import FaceDetector
from privacy_guard.vision.observation import FaceObservation

try:  # pragma: no cover - import guard
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision

    _DEPS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _DEPS_AVAILABLE = False


def mediapipe_available() -> bool:
    """Return whether MediaPipe and OpenCV are both importable."""
    return _DEPS_AVAILABLE


# Canonical 3D face model points (mm), matching the MediaPipe landmark indices below.
# A coarse generic model is sufficient for solvePnP head-pose estimation.
_MODEL_POINTS = np.array(
    [
        [0.0, 0.0, 0.0],  # nose tip (idx 1)
        [0.0, -63.6, -12.5],  # chin (idx 152)
        [-43.3, 32.7, -26.0],  # left eye outer corner (idx 33)
        [43.3, 32.7, -26.0],  # right eye outer corner (idx 263)
        [-28.9, -28.9, -24.1],  # left mouth corner (idx 61)
        [28.9, -28.9, -24.1],  # right mouth corner (idx 291)
    ],
    dtype=np.float64,
)
_LANDMARK_IDS = (1, 152, 33, 263, 61, 291)


def _wrap_pitch_deg(pitch_deg: float) -> float:
    """Normalize a solvePnP pitch angle into ``[-90, 90)``.

    Our 3D model points use ``+y`` up, while OpenCV's image frame is ``+y`` down, so
    ``solvePnP`` returns a pitch offset by ~180 degrees (it reads ~+-170 when the user
    faces the camera). Wrapping it back makes "facing forward" ~0, matching
    :func:`privacy_guard.geometry.gaze.gaze_vector` (pitch ~0 => gaze ~ ``-z``, into
    the screen). The residual up/down sign is approximate, which is acceptable given
    the deliberately generous angular tolerance in the geometry layer.

    This is pure (no OpenCV) so it is unit-tested headlessly.
    """
    return (pitch_deg + 90.0) % 180.0 - 90.0


class MediaPipeFaceDetector(FaceDetector):
    """Face/landmark detector backed by MediaPipe's Face Landmarker task."""

    def __init__(self, model_path: str, max_faces: int = 4, min_confidence: float = 0.5) -> None:
        """Load the Face Landmarker model.

        Args:
            model_path: Local path to the ``.task`` model file (no auto-download).
            max_faces: Maximum number of faces to detect.
            min_confidence: Minimum detection confidence.

        Raises:
            RuntimeError: If MediaPipe/OpenCV are unavailable.
        """
        if not _DEPS_AVAILABLE:  # pragma: no cover - trivial guard
            msg = "MediaPipe/OpenCV unavailable; install the 'vision' extra and provide a model."
            raise RuntimeError(msg)
        self._build_landmarker(model_path, max_faces, min_confidence)

    def _build_landmarker(  # pragma: no cover - requires mediapipe
        self, model_path: str, max_faces: int, min_confidence: float
    ) -> None:
        base = mp_python.BaseOptions(model_asset_path=model_path)
        options = mp_vision.FaceLandmarkerOptions(
            base_options=base,
            num_faces=max_faces,
            min_face_detection_confidence=min_confidence,
            running_mode=mp_vision.RunningMode.VIDEO,
        )
        self._landmarker = mp_vision.FaceLandmarker.create_from_options(options)

    @property
    def is_available(self) -> bool:
        """Whether the backend libraries are usable."""
        return _DEPS_AVAILABLE

    def detect(
        self, frame: Frame
    ) -> list[FaceObservation]:  # pragma: no cover - requires mediapipe
        """Detect faces and estimate coarse head pose for each."""
        rgb = cv2.cvtColor(frame.image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(mp_image, int(frame.timestamp_ms))
        observations: list[FaceObservation] = []
        h, w = frame.height, frame.width
        for face_landmarks in result.face_landmarks:
            observations.append(self._landmarks_to_observation(face_landmarks, w, h))
        return observations

    def _landmarks_to_observation(  # pragma: no cover - requires mediapipe
        self, landmarks: list, w: int, h: int
    ) -> FaceObservation:
        xs = [lm.x for lm in landmarks]
        ys = [lm.y for lm in landmarks]
        center_x = float(np.clip(np.mean(xs), 0.0, 1.0))
        center_y = float(np.clip(np.mean(ys), 0.0, 1.0))
        size = float(np.clip((max(xs) - min(xs)) * (max(ys) - min(ys)), 0.0, 1.0))

        image_points = np.array(
            [[landmarks[i].x * w, landmarks[i].y * h] for i in _LANDMARK_IDS],
            dtype=np.float64,
        )
        yaw, pitch, position = self._solve_head_pose(image_points, w, h)
        return FaceObservation(
            center_x=center_x,
            center_y=center_y,
            size=size,
            position_mm=position,
            yaw_deg=yaw,
            pitch_deg=pitch,
            gaze_estimable=True,
        )

    @staticmethod
    def _solve_head_pose(  # pragma: no cover - requires opencv
        image_points: NDArray[np.float64], w: int, h: int
    ) -> tuple[float, float, NDArray[np.float64]]:
        focal = float(w)
        cam_matrix = np.array(
            [[focal, 0, w / 2.0], [0, focal, h / 2.0], [0, 0, 1]], dtype=np.float64
        )
        dist = np.zeros((4, 1), dtype=np.float64)
        ok, rvec, tvec = cv2.solvePnP(
            _MODEL_POINTS, image_points, cam_matrix, dist, flags=cv2.SOLVEPNP_ITERATIVE
        )
        if not ok:
            return 0.0, 0.0, np.array([0.0, 0.0, 600.0], dtype=np.float64)
        rmat, _ = cv2.Rodrigues(rvec)
        # Yaw about vertical axis, pitch about horizontal axis (degrees).
        yaw = math.degrees(math.atan2(-rmat[2, 0], math.hypot(rmat[2, 1], rmat[2, 2])))
        # The +y-up model vs +y-down image frame leaves pitch offset by ~180 deg; wrap
        # it so "facing the camera" is ~0 (see _wrap_pitch_deg). Without this, gaze
        # points away from the screen and nothing is ever detected as "looking".
        pitch = _wrap_pitch_deg(math.degrees(math.atan2(rmat[2, 1], rmat[2, 2])))
        # cv2 camera frame: +x right, +y down, +z forward. Convert to our frame
        # (+y up, +z toward viewer): flip y and z signs of the translation.
        t = tvec.reshape(3)
        position = np.array([t[0], -t[1], abs(t[2])], dtype=np.float64)
        return yaw, pitch, position

    def close(self) -> None:  # pragma: no cover - requires mediapipe
        """Release the landmarker."""
        closer = getattr(self, "_landmarker", None)
        if closer is not None:
            closer.close()
