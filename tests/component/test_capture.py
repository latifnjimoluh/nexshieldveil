"""Component tests for the capture abstraction (no real camera)."""

from __future__ import annotations

import numpy as np
import pytest

from privacy_guard.capture import (
    Frame,
    SyntheticFrameSource,
    VideoFileFrameSource,
    WebcamFrameSource,
    opencv_available,
)

pytestmark = pytest.mark.component


def test_synthetic_source_emits_n_frames() -> None:
    src = SyntheticFrameSource(width=320, height=240, n_frames=5, fps=10.0)
    frames = list(src)
    assert len(frames) == 5
    assert all(isinstance(f, Frame) for f in frames)
    assert frames[0].width == 320
    assert frames[0].height == 240


def test_synthetic_source_is_deterministic() -> None:
    a = list(SyntheticFrameSource(n_frames=4))
    b = list(SyntheticFrameSource(n_frames=4))
    for fa, fb in zip(a, b, strict=True):
        assert np.array_equal(fa.image, fb.image)
        assert fa.timestamp_ms == fb.timestamp_ms


def test_synthetic_timestamps_increase() -> None:
    src = SyntheticFrameSource(n_frames=6, fps=20.0)
    times = [f.timestamp_ms for f in src]
    assert times == sorted(times)
    assert times[1] - times[0] == pytest.approx(50.0)


def test_synthetic_read_returns_none_when_exhausted() -> None:
    src = SyntheticFrameSource(n_frames=1)
    assert src.read() is not None
    assert src.read() is None
    assert not src.is_available


def test_context_manager_closes() -> None:
    with SyntheticFrameSource(n_frames=3) as src:
        assert src.read() is not None
    assert not src.is_available


def test_synthetic_rejects_bad_params() -> None:
    with pytest.raises(ValueError, match="positive"):
        SyntheticFrameSource(width=0)


def test_synthetic_does_not_accumulate_buffers() -> None:
    # The source must not retain references to past frames in its own state.
    src = SyntheticFrameSource(n_frames=50)
    held = list(src)  # hold every frame so ids cannot be reused
    assert len({id(f.image) for f in held}) == 50  # all genuinely distinct objects
    # No growing container lives on the source instance (only scalar counters).
    assert not any(isinstance(v, (list, dict, set)) and len(v) > 0 for v in vars(src).values())


@pytest.mark.skipif(opencv_available(), reason="OpenCV present; degradation path not applicable")
def test_opencv_sources_raise_without_cv2() -> None:
    with pytest.raises(RuntimeError, match="OpenCV"):
        WebcamFrameSource()
    with pytest.raises(RuntimeError, match="OpenCV"):
        VideoFileFrameSource("nope.mp4")


@pytest.mark.skipif(not opencv_available(), reason="OpenCV not installed")
def test_video_source_missing_file_is_unavailable() -> None:
    src = VideoFileFrameSource("definitely-not-a-real-file.mp4")
    assert src.is_available is False
    assert src.read() is None
    src.close()
