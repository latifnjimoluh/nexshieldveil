"""Privacy guarantees for the freeze-frame SCREEN capture (M-FP6).

The screen frame is *more* sensitive than the camera frame: it contains the
very content the product protects. These tests encode the non-negotiable rules
from docs/ROADMAP_FLOU_PIXELISATION.md on the full capture->transform->present
orchestration (Qt-free stack, so this suite runs even on a core-only checkout):

- P2: no screen frame (captured or transformed) survives the mask lift;
- P3: exactly one capture per engagement, never a stream, and no accumulation
  across many mask/lift cycles;
- no outbound network and no disk write anywhere on the capture path.

The Qt side of the same guarantee (the presenter's QImage copy releasing the
numpy buffer, frames cleared on hide) is proven offscreen in
``tests/ui/test_qt_presenter.py``.
"""

from __future__ import annotations

import builtins
import gc
import socket
import weakref

import numpy as np
import pytest

from privacy_guard.masking import BlurMask
from privacy_guard.overlay import (
    FreezeFrameCompositor,
    RecordingPresenter,
    ScreenGrabber,
    ScreenShot,
    SynchronousTransformExecutor,
)

pytestmark = pytest.mark.privacy

rng = np.random.default_rng(41)


class _FreshGrabber(ScreenGrabber):
    """Generates a brand-new screen frame per grab and weak-tracks every one."""

    def __init__(self) -> None:
        self.calls = 0
        self.capture_refs: list[weakref.ref[np.ndarray]] = []

    def grab_all(self) -> list[ScreenShot]:
        self.calls += 1
        image = rng.integers(0, 256, size=(48, 64, 3), dtype=np.uint8)
        self.capture_refs.append(weakref.ref(image))
        return [ScreenShot(image=image, x=0, y=0, width=64, height=48)]


class _TrackingPresenter(RecordingPresenter):
    """Recording presenter that also weak-tracks every transformed frame shown."""

    def __init__(self) -> None:
        super().__init__()
        self.frame_refs: list[weakref.ref[np.ndarray]] = []

    def show_frames(self, frames: list[ScreenShot]) -> None:
        for frame in frames:
            self.frame_refs.append(weakref.ref(frame.image))
        super().show_frames(frames)


def _build() -> tuple[FreezeFrameCompositor, _FreshGrabber, _TrackingPresenter]:
    grabber = _FreshGrabber()
    presenter = _TrackingPresenter()
    compositor = FreezeFrameCompositor(
        grabber=grabber,
        strategy=BlurMask(radius=5),
        presenter=presenter,
        executor=SynchronousTransformExecutor(),
    )
    return compositor, grabber, presenter


def _alive(refs: list[weakref.ref[np.ndarray]]) -> int:
    gc.collect()
    return sum(1 for ref in refs if ref() is not None)


def test_no_screen_frame_survives_the_mask_lift() -> None:
    compositor, grabber, presenter = _build()
    compositor.engage()
    assert _alive(presenter.frame_refs) == 1  # displayed while masked (its own copy)
    compositor.disengage()
    assert _alive(grabber.capture_refs) == 0, "captured screen frame outlived the lift (P2)"
    assert _alive(presenter.frame_refs) == 0, "transformed screen frame outlived the lift (P2)"


def test_one_capture_per_engagement_and_no_accumulation_over_cycles() -> None:
    compositor, grabber, presenter = _build()
    cycles = 30
    for _ in range(cycles):
        compositor.engage()
        compositor.disengage()
    assert grabber.calls == cycles  # P3: exactly one grab per engagement
    assert _alive(grabber.capture_refs) == 0, "screen captures are accumulating"
    assert _alive(presenter.frame_refs) == 0, "transformed frames are accumulating"


def test_no_outbound_network_on_the_capture_path(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbid(*args: object, **kwargs: object) -> object:
        raise AssertionError("outbound network attempted on the screen-capture path")

    monkeypatch.setattr(socket, "socket", forbid)
    monkeypatch.setattr(socket, "create_connection", forbid)
    monkeypatch.setattr(socket, "getaddrinfo", forbid)

    compositor, _grabber, presenter = _build()
    for _ in range(5):
        compositor.engage()
        compositor.disengage()
    assert presenter.veil_calls == 5  # the path really ran


def test_no_file_written_on_the_capture_path(monkeypatch: pytest.MonkeyPatch) -> None:
    real_open = builtins.open
    writes: list[tuple[str, str]] = []

    def spy_open(file: object, mode: str = "r", *args: object, **kwargs: object) -> object:
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            writes.append((str(file), mode))
        return real_open(file, mode, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "open", spy_open)

    def forbid_save(*args: object, **kwargs: object) -> None:
        raise AssertionError("screen frame persistence attempted")

    monkeypatch.setattr(np, "save", forbid_save)
    monkeypatch.setattr(np, "savez", forbid_save)

    compositor, _grabber, _presenter = _build()
    for _ in range(5):
        compositor.engage()
        compositor.disengage()
    assert writes == [], f"unexpected file writes on the capture path: {writes}"


def test_no_image_files_appear_on_disk(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.rglob("*"))
    compositor, _grabber, _presenter = _build()
    for _ in range(5):
        compositor.engage()
        compositor.disengage()
    new_files = set(tmp_path.rglob("*")) - before
    image_exts = {".png", ".jpg", ".jpeg", ".bmp", ".npy", ".npz", ".tiff"}
    assert not [p for p in new_files if p.suffix.lower() in image_exts]


def test_compositor_itself_holds_no_frame_while_masked() -> None:
    # Even WHILE masked, the compositor object retains nothing: frames flow
    # grabber -> executor -> presenter only. The presenter (the display) is the
    # single holder, and it drops them on hide (previous tests).
    compositor, _grabber, _presenter = _build()
    compositor.engage()
    held = [v for v in vars(compositor).values() if isinstance(v, np.ndarray)]
    assert held == []
    compositor.disengage()
