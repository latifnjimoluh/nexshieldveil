"""Unit tests for the screen-capture interface (M-FP2, freeze-frame path).

Everything here runs headless against the pure contract: ``ScreenShot``
validation, the scriptable ``FakeScreenGrabber``, and the blank-capture
detector used for the locked-screen/DRM fallback (P4).
"""

from __future__ import annotations

import numpy as np
import pytest

from privacy_guard.overlay import (
    FakeScreenGrabber,
    ScreenGrabber,
    ScreenShot,
    looks_blank,
)

pytestmark = pytest.mark.unit

rng = np.random.default_rng(3)


def _noisy(h: int = 48, w: int = 64) -> np.ndarray:
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


def _shot(image: np.ndarray | None = None) -> ScreenShot:
    img = _noisy() if image is None else image
    return ScreenShot(image=img, x=0, y=0, width=img.shape[1], height=img.shape[0])


# --------------------------------------------------------------------------- #
# ScreenShot validation
# --------------------------------------------------------------------------- #
def test_screenshot_accepts_valid_rgb_image() -> None:
    shot = _shot()
    assert shot.image.shape == (48, 64, 3)


@pytest.mark.parametrize(
    "bad",
    [
        np.zeros((10, 10), dtype=np.uint8),  # missing channel axis
        np.zeros((10, 10, 4), dtype=np.uint8),  # RGBA, not RGB
        np.zeros((10, 10, 3), dtype=np.float32),  # wrong dtype
        np.zeros((0, 10, 3), dtype=np.uint8),  # empty
    ],
)
def test_screenshot_rejects_invalid_images(bad: np.ndarray) -> None:
    with pytest.raises(ValueError, match="H, W, 3"):
        ScreenShot(image=bad, x=0, y=0, width=10, height=10)


# --------------------------------------------------------------------------- #
# FakeScreenGrabber (the test double every higher layer builds on)
# --------------------------------------------------------------------------- #
def test_fake_grabber_is_a_screen_grabber() -> None:
    assert isinstance(FakeScreenGrabber(), ScreenGrabber)


def test_fake_grabber_default_shot_is_usable_and_not_blank() -> None:
    shots = FakeScreenGrabber().grab_all()
    assert len(shots) == 1
    assert shots[0].image.dtype == np.uint8
    assert not looks_blank(shots[0].image)


def test_fake_grabber_returns_scripted_shots() -> None:
    scripted = [_shot(), _shot(_noisy(32, 32))]
    grabber = FakeScreenGrabber(shots=scripted)
    assert grabber.grab_all() == scripted


def test_fake_grabber_failure_yields_empty_list_and_counts_calls() -> None:
    grabber = FakeScreenGrabber(fail=True)
    assert grabber.grab_all() == []
    grabber.fail = False
    assert len(grabber.grab_all()) == 1
    assert grabber.calls == 2


# --------------------------------------------------------------------------- #
# Blank-capture detection (locked screen / DRM gives a flat frame -> P4 veil)
# --------------------------------------------------------------------------- #
def test_black_capture_is_blank() -> None:
    assert looks_blank(np.zeros((32, 32, 3), dtype=np.uint8))


def test_uniform_gray_capture_is_blank() -> None:
    assert looks_blank(np.full((32, 32, 3), 87, dtype=np.uint8))


def test_barely_noisy_black_capture_is_blank() -> None:
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    img[::16, ::16] = 1  # sensor-level speckle, still no content
    assert looks_blank(img)


def test_real_content_is_not_blank() -> None:
    assert not looks_blank(_noisy())


def test_looks_blank_rejects_non_rgb_image() -> None:
    with pytest.raises(ValueError, match="H, W, 3"):
        looks_blank(np.zeros((10, 10), dtype=np.uint8))
