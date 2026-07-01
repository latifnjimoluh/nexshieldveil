"""Offscreen tests for the Qt transform executor (M-FP3, P7).

No display needed: only worker threads + the event loop. The point proven here
is the threading contract — the transform runs off the calling thread and the
callback is delivered back ON the calling (owning) thread via a queued signal.
"""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest
from PySide6.QtGui import QGuiApplication

from privacy_guard.masking import BlurMask, MaskStrategy
from privacy_guard.overlay import QtTransformExecutor, ScreenShot

pytestmark = pytest.mark.component

rng = np.random.default_rng(23)


def _shot() -> ScreenShot:
    image = rng.integers(0, 256, size=(48, 64, 3), dtype=np.uint8)
    return ScreenShot(image=image, x=0, y=0, width=64, height=48)


class _ThreadRecordingStrategy(MaskStrategy):
    """Records which thread ran the transform, then delegates to a real blur."""

    def __init__(self) -> None:
        self.ran_on: list[int] = []
        self._inner = BlurMask(radius=3)

    def apply(self, image: np.ndarray) -> np.ndarray:
        self.ran_on.append(threading.get_ident())
        return self._inner.apply(image)

    @property
    def name(self) -> str:
        return "thread-recording"


def _wait_for(app: QGuiApplication, done: list, timeout_s: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not done and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    assert done, "executor never delivered its result"


def test_transform_runs_off_thread_and_delivers_on_owner_thread(
    qapp: QGuiApplication,
) -> None:
    executor = QtTransformExecutor()
    strategy = _ThreadRecordingStrategy()
    shot = _shot()
    delivered: list[tuple[int, list[ScreenShot]]] = []
    executor.submit(
        [shot], strategy, lambda frames: delivered.append((threading.get_ident(), frames))
    )
    _wait_for(qapp, delivered)

    owner_thread = threading.get_ident()
    delivery_thread, frames = delivered[0]
    assert strategy.ran_on[0] != owner_thread  # heavy work off the UI thread (P7)
    assert delivery_thread == owner_thread  # callback back on the owning thread
    assert len(frames) == 1
    assert np.array_equal(frames[0].image, BlurMask(radius=3).apply(shot.image))


def test_transform_failure_delivers_empty_result_not_exception(
    qapp: QGuiApplication,
) -> None:
    class _Exploding(MaskStrategy):
        def apply(self, image: np.ndarray) -> np.ndarray:
            raise RuntimeError("boom")

        @property
        def name(self) -> str:
            return "exploding"

    executor = QtTransformExecutor()
    delivered: list[list[ScreenShot]] = []
    executor.submit([_shot()], _Exploding(), delivered.append)
    _wait_for(qapp, delivered)
    assert delivered[0] == []  # P4: failure signal, never an exception
