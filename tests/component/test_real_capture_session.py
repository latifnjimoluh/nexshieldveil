"""A real session through the real OpenCV capture path (AM-17).

The CI matrix installs ``[dev,ui]`` but never ``[vision]``, so ``opencv_sources``
and ``mediapipe_detector`` were imported by nothing: a regression in either would
have been caught only by someone running the app by hand. This module closes that
gap for everything that does not need a model file — real ``cv2.VideoCapture``
reads, real timestamps, real downscaling — and runs under the same no-network /
no-image-on-disk guards as the synthetic privacy suite.

What is still *not* covered here: MediaPipe inference itself, which needs the
model the project deliberately never downloads. The detector's degradation path is
checked instead.

Skipped wholesale without OpenCV, like the other capture component tests.
"""

from __future__ import annotations

import builtins
import socket
from pathlib import Path

import numpy as np
import pytest

from privacy_guard.app import PrivacyGuardPipeline
from privacy_guard.capture import (
    DownscaledFrameSource,
    VideoFileFrameSource,
    opencv_available,
)
from privacy_guard.config import AppConfig
from privacy_guard.overlay import RecordingRenderer
from privacy_guard.vision import ScriptedFaceDetector

pytestmark = [
    pytest.mark.component,
    pytest.mark.skipif(not opencv_available(), reason="OpenCV not installed"),
]

_WIDTH, _HEIGHT, _FRAMES, _FPS = 1280, 720, 24, 12.0


@pytest.fixture
def clip(tmp_path: Path) -> Path:
    """A short synthetic clip: moving grey blocks, deliberately no faces.

    Generated rather than committed — this repository must not carry image data,
    let alone anything that could show a real person.
    """
    import cv2

    path = tmp_path / "clip.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), _FPS, (_WIDTH, _HEIGHT))
    assert writer.isOpened(), "could not open a VideoWriter; codec unavailable?"
    for index in range(_FRAMES):
        frame = np.full((_HEIGHT, _WIDTH, 3), 40, dtype=np.uint8)
        x = 40 * index
        frame[200:400, x : x + 160] = 200
        writer.write(frame)
    writer.release()
    assert path.is_file()
    return path


def test_the_real_video_source_yields_usable_frames(clip: Path) -> None:
    source = VideoFileFrameSource(str(clip))
    try:
        assert source.is_available is True
        frames = list(source)
        assert len(frames) == _FRAMES
        assert frames[0].image.shape == (_HEIGHT, _WIDTH, 3)
        assert frames[0].image.dtype == np.uint8
        # Index and timestamp are the contract MediaPipe's video mode relies on.
        assert [f.index for f in frames] == list(range(_FRAMES))
        timestamps = [f.timestamp_ms for f in frames]
        assert timestamps == sorted(timestamps)
    finally:
        source.close()


def test_reading_past_the_end_returns_none(clip: Path) -> None:
    source = VideoFileFrameSource(str(clip))
    try:
        assert len(list(source)) == _FRAMES
        assert source.read() is None  # exhausted, not an error
    finally:
        source.close()


def test_closing_releases_the_capture(clip: Path) -> None:
    source = VideoFileFrameSource(str(clip))
    source.close()
    assert source.is_available is False
    assert source.read() is None


def test_downscaling_a_real_capture(clip: Path) -> None:
    # AM-12 against real decoded frames rather than synthetic arrays.
    source = DownscaledFrameSource(VideoFileFrameSource(str(clip)), 640)
    try:
        frame = source.read()
        assert frame is not None
        assert (frame.width, frame.height) == (640, 360)
    finally:
        source.close()


def test_a_full_pipeline_run_over_a_real_clip(clip: Path) -> None:
    # The assembled decision path, fed by the real decoder: this is the wiring
    # that CI never exercised.
    source = DownscaledFrameSource(VideoFileFrameSource(str(clip)), 640)
    pipeline = PrivacyGuardPipeline(
        AppConfig(), source, ScriptedFaceDetector([]), RecordingRenderer()
    )
    try:
        results = pipeline.run()
        assert len(results) == _FRAMES
        assert not any(r.is_masked for r in results)  # no faces in the clip
    finally:
        pipeline.close()


def test_a_real_session_opens_no_socket_and_writes_no_file(
    clip: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The same guards as the synthetic privacy suite, this time with the real
    # decoder in the loop — the component that actually *could* touch the disk.
    def forbid(*args: object, **kwargs: object) -> object:
        raise AssertionError("outbound network attempted")

    monkeypatch.setattr(socket, "socket", forbid)
    monkeypatch.setattr(socket, "create_connection", forbid)
    monkeypatch.setattr(socket, "getaddrinfo", forbid)

    real_open = builtins.open
    writes: list[str] = []

    def spy_open(file: object, mode: str = "r", *args: object, **kwargs: object) -> object:
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            writes.append(str(file))
        return real_open(file, mode, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "open", spy_open)

    before = set(tmp_path.rglob("*"))
    source = DownscaledFrameSource(VideoFileFrameSource(str(clip)), 640)
    pipeline = PrivacyGuardPipeline(
        AppConfig(), source, ScriptedFaceDetector([]), RecordingRenderer()
    )
    try:
        pipeline.run()
    finally:
        pipeline.close()

    assert writes == []
    assert set(tmp_path.rglob("*")) == before, "the session created files on disk"


def test_the_mediapipe_adapter_degrades_without_a_model() -> None:
    # Imports the real adapter module (the other thing CI never loaded) and
    # checks the failure it is designed to have: a clear, catchable error.
    from privacy_guard.vision import MediaPipeFaceDetector, mediapipe_available

    if not mediapipe_available():
        pytest.skip("MediaPipe not installed")
    with pytest.raises(Exception):  # noqa: B017 - backend raises its own type
        MediaPipeFaceDetector(model_path="definitely-not-a-model.task")
