"""Capture downscaling (AM-12): sizing rules, wrapping behaviour, resampling.

Pure logic — no camera, no OpenCV. The resampler is injectable, so the wrapper's
contract is tested independently of which backend does the pixels.
"""

from __future__ import annotations

import numpy as np
import pytest

from privacy_guard.capture import (
    DownscaledFrameSource,
    Frame,
    FrameSource,
    SyntheticFrameSource,
    default_resizer,
    resize_nearest,
    target_size,
)

pytestmark = pytest.mark.unit


class _ScriptedSource(FrameSource):
    """Yields the given frames, then None. Records close() for lifecycle tests."""

    def __init__(self, frames: list[Frame]) -> None:
        self._frames = list(frames)
        self.closed = False
        self.available = True

    @property
    def is_available(self) -> bool:
        return self.available

    def read(self) -> Frame | None:
        return self._frames.pop(0) if self._frames else None

    def close(self) -> None:
        self.closed = True


def _frame(width: int, height: int, index: int = 0, timestamp_ms: float = 0.0) -> Frame:
    image = np.arange(height * width * 3, dtype=np.int64).reshape(height, width, 3) % 256
    return Frame(image=image.astype(np.uint8), timestamp_ms=timestamp_ms, index=index)


# --------------------------------------------------------------------------- #
# target_size: the pure sizing rule
# --------------------------------------------------------------------------- #
def test_target_size_preserves_aspect_ratio() -> None:
    assert target_size(1280, 720, 640) == (640, 360)
    assert target_size(1920, 1080, 640) == (640, 360)
    assert target_size(640, 480, 320) == (320, 240)


def test_target_size_never_upscales() -> None:
    # Already at or below the target: nothing to gain, so no resize at all.
    assert target_size(640, 480, 640) is None
    assert target_size(320, 240, 640) is None


def test_target_size_keeps_at_least_one_row() -> None:
    # A pathologically wide frame must not round its height down to zero.
    assert target_size(4000, 3, 64) == (64, 1)


@pytest.mark.parametrize(
    ("width", "height", "target"),
    [(0, 480, 640), (640, 0, 640), (-1, 480, 640), (640, 480, 0), (640, 480, -5)],
)
def test_target_size_rejects_non_positive_dimensions(width, height, target) -> None:
    with pytest.raises(ValueError):
        target_size(width, height, target)


# --------------------------------------------------------------------------- #
# resize_nearest: the pure numpy fallback
# --------------------------------------------------------------------------- #
def test_resize_nearest_produces_the_requested_shape() -> None:
    out = resize_nearest(_frame(1280, 720).image, 640, 360)
    assert out.shape == (360, 640, 3)
    assert out.dtype == np.uint8


def test_resize_nearest_preserves_a_flat_image() -> None:
    flat = np.full((480, 640, 3), 77, dtype=np.uint8)
    out = resize_nearest(flat, 320, 240)
    assert np.all(out == 77)


def test_resize_nearest_samples_within_bounds() -> None:
    # Corner sampling must stay inside the source, whatever the ratio.
    out = resize_nearest(_frame(7, 5).image, 3, 2)
    assert out.shape == (2, 3, 3)


def test_default_resizer_returns_a_working_callable() -> None:
    resize = default_resizer()
    out = resize(_frame(800, 600).image, 400, 300)
    assert out.shape == (300, 400, 3)


# --------------------------------------------------------------------------- #
# DownscaledFrameSource: the wrapper contract
# --------------------------------------------------------------------------- #
def test_frames_are_resized_to_the_target_width() -> None:
    source = DownscaledFrameSource(_ScriptedSource([_frame(1280, 720)]), 640)
    frame = source.read()
    assert frame is not None
    assert (frame.width, frame.height) == (640, 360)


def test_index_and_timestamp_pass_through_untouched() -> None:
    # Unlike the resilient wrapper, this one must NOT renumber: MediaPipe's
    # strictly-increasing timestamps stay the inner source's contract.
    inner = _ScriptedSource([_frame(1280, 720, index=7, timestamp_ms=1234.5)])
    frame = DownscaledFrameSource(inner, 640).read()
    assert frame is not None
    assert frame.index == 7
    assert frame.timestamp_ms == pytest.approx(1234.5)


def test_frames_below_the_target_are_passed_through_unchanged() -> None:
    original = _frame(320, 240)
    inner = _ScriptedSource([original])
    frame = DownscaledFrameSource(inner, 640).read()
    # Same object: no copy, no resample, no allocation on the hot path.
    assert frame is original


def test_exhaustion_propagates_as_none() -> None:
    assert DownscaledFrameSource(_ScriptedSource([]), 640).read() is None


def test_close_and_availability_delegate_to_the_wrapped_source() -> None:
    inner = _ScriptedSource([])
    source = DownscaledFrameSource(inner, 640)
    assert source.is_available is True
    inner.available = False
    assert source.is_available is False
    source.close()
    assert inner.closed is True


def test_injected_resizer_receives_the_computed_size() -> None:
    calls: list[tuple[int, int]] = []

    def spy(image, width, height):
        calls.append((width, height))
        return np.zeros((height, width, 3), dtype=np.uint8)

    DownscaledFrameSource(_ScriptedSource([_frame(1920, 1080)]), 640, resizer=spy).read()
    assert calls == [(640, 360)]


def test_output_is_contiguous_uint8() -> None:
    # MediaPipe/OpenCV both expect a contiguous uint8 buffer.
    frame = DownscaledFrameSource(_ScriptedSource([_frame(1280, 720)]), 640).read()
    assert frame is not None
    assert frame.image.dtype == np.uint8
    assert frame.image.flags["C_CONTIGUOUS"]


def test_rejects_a_non_positive_target_width() -> None:
    with pytest.raises(ValueError):
        DownscaledFrameSource(SyntheticFrameSource(n_frames=1), 0)


def test_wraps_a_real_synthetic_source_end_to_end() -> None:
    source = DownscaledFrameSource(SyntheticFrameSource(width=1280, height=720, n_frames=3), 640)
    frames = list(source)
    assert len(frames) == 3
    assert [f.index for f in frames] == [0, 1, 2]
    assert all((f.width, f.height) == (640, 360) for f in frames)


def test_holds_no_reference_to_the_frame_it_returned() -> None:
    # Privacy: frames live in RAM for one iteration and are collectable at once.
    import weakref

    source = DownscaledFrameSource(_ScriptedSource([_frame(1280, 720)]), 640)
    frame = source.read()
    assert frame is not None
    ref = weakref.ref(frame.image)
    del frame
    assert ref() is None
