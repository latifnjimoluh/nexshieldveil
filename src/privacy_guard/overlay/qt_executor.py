"""Qt transform executor: runs mask transforms off the UI thread (M-FP3, P7).

The blur/pixelate of a full-screen capture takes tens to hundreds of
milliseconds (budgets in ``tests/performance/test_masking_perf.py``) — far too
long for the Qt event loop. Jobs run on ``QThreadPool`` worker threads and the
result comes back through a queued signal, so the compositor's callback always
executes on the thread that owns it (its documented threading contract).

Unlike the display adapters this module needs no screen — only threads and an
event loop — so it IS exercised in CI by the offscreen UI tests.
"""

from __future__ import annotations

import logging

from privacy_guard.masking import MaskStrategy
from privacy_guard.overlay.compositor import TransformCallback, _safe_transform
from privacy_guard.overlay.grabber import ScreenShot

try:  # pragma: no cover - import guard
    from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

    _QT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _QT_AVAILABLE = False

logger = logging.getLogger(__name__)


if _QT_AVAILABLE:

    class _Job(QRunnable):
        """One transform, executed on a pool thread; result emitted, never returned."""

        def __init__(
            self,
            emitter: QtTransformExecutor,
            shots: list[ScreenShot],
            strategy: MaskStrategy,
            on_done: TransformCallback,
        ) -> None:
            super().__init__()
            self._emitter = emitter
            self._shots = shots
            self._strategy = strategy
            self._on_done = on_done

        def run(self) -> None:
            frames = _safe_transform(self._shots, self._strategy)
            # Drop the input reference before signalling: once delivered, the
            # only live copies are the frames travelling to the presenter (P2).
            self._shots = []
            self._emitter.job_finished.emit(self._on_done, frames)

    class QtTransformExecutor(QObject):
        """Executor backed by the global ``QThreadPool``.

        Satisfies the :class:`~privacy_guard.overlay.compositor.TransformExecutor`
        protocol structurally (QObject's metaclass forbids ABC bases). Create it
        (and call :meth:`submit`) on the thread that must receive the callbacks —
        signal delivery is queued back to this object's thread.
        """

        job_finished = Signal(object, object)  # (callback, frames)

        def __init__(self, pool: QThreadPool | None = None) -> None:
            """Wire the delivery signal; uses the global pool by default."""
            super().__init__()
            self._pool = pool or QThreadPool.globalInstance()
            self.job_finished.connect(self._deliver)

        def submit(
            self, shots: list[ScreenShot], strategy: MaskStrategy, on_done: TransformCallback
        ) -> None:
            """Queue the transform on a worker thread; delivery is asynchronous."""
            self._pool.start(_Job(self, shots, strategy, on_done))

        @Slot(object, object)
        def _deliver(self, on_done: TransformCallback, frames: list[ScreenShot]) -> None:
            on_done(frames)

else:  # pragma: no cover - only without the [ui] extra

    class QtTransformExecutor:  # type: ignore[no-redef]
        """Placeholder that fails loudly when PySide6 is missing."""

        def __init__(self, pool: object = None) -> None:
            """Refuse to build without PySide6."""
            msg = "PySide6 unavailable; install the 'ui' extra to use QtTransformExecutor."
            raise RuntimeError(msg)

        def submit(
            self, shots: list[ScreenShot], strategy: MaskStrategy, on_done: TransformCallback
        ) -> None:
            """Unreachable: construction always raises."""
            raise NotImplementedError
