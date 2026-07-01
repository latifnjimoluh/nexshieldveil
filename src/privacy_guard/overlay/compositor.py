"""Freeze-frame compositor: the pure orchestration behind blur/pixelate (M-FP3).

One masking engagement runs: capture every screen (before anything is shown, or
the capture would photograph our own veil) → show the opaque veil immediately
(P1 — the transform never delays protection) → transform off the caller's
thread → swap the veil for the transformed frames. Lifting the mask hides
everything and drops every frame reference (P2).

This module is deliberately Qt-free. It talks to three injected abstractions —
:class:`~privacy_guard.overlay.grabber.ScreenGrabber`, :class:`MaskPresenter`
and :class:`TransformExecutor` — so every rule is unit-testable headlessly.
The Qt implementations live in their own adapter modules.

Threading contract: all :class:`FreezeFrameCompositor` methods (including the
executor's completion callback) must run on the owning thread. The Qt executor
guarantees this by delivering results through a queued signal.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from enum import Enum, auto
from typing import Protocol

from privacy_guard.masking import MaskStrategy
from privacy_guard.overlay.grabber import ScreenGrabber, ScreenShot, looks_blank

logger = logging.getLogger(__name__)

TransformCallback = Callable[[list[ScreenShot]], None]


class CompositorState(Enum):
    """Where an engagement currently is (capture itself is transient)."""

    IDLE = auto()
    VEILED = auto()  # opaque veil visible; a transform may still be in flight
    TRANSFORMED = auto()  # transformed frames visible


# MaskPresenter and TransformExecutor are structural Protocols (not ABCs) on
# purpose: their Qt implementations inherit QObject, whose metaclass is
# incompatible with ABCMeta.
class MaskPresenter(Protocol):
    """Displays the masking layer. Implementations own the actual windows."""

    def show_veil(self) -> None:
        """Show the plain opaque veil on every screen, immediately."""
        ...

    def show_frames(self, frames: list[ScreenShot]) -> None:
        """Swap in transformed frames; screens without a frame keep the veil."""
        ...

    def hide(self) -> None:
        """Lift the masking layer and release any displayed frames (P2)."""
        ...


@dataclass
class RecordingPresenter:
    """Headless presenter that records calls — the test double for the compositor."""

    log: list[str] = field(default_factory=list)
    veil_calls: int = 0
    hide_calls: int = 0
    frames_shown: list[list[ScreenShot]] = field(default_factory=list)

    def show_veil(self) -> None:
        """Record the veil request."""
        self.veil_calls += 1
        self.log.append("veil")

    def show_frames(self, frames: list[ScreenShot]) -> None:
        """Record the swapped-in frames."""
        self.frames_shown.append(frames)
        self.log.append("frames")

    def hide(self) -> None:
        """Record the lift and drop displayed frames (P2, like a real presenter)."""
        self.hide_calls += 1
        self.frames_shown = []
        self.log.append("hide")


def transform_shots(shots: list[ScreenShot], strategy: MaskStrategy) -> list[ScreenShot]:
    """Apply ``strategy`` to every shot, preserving each screen's geometry."""
    return [replace(shot, image=strategy.apply(shot.image)) for shot in shots]


def _safe_transform(shots: list[ScreenShot], strategy: MaskStrategy) -> list[ScreenShot]:
    """Like :func:`transform_shots`, but a failure yields ``[]`` (P4), never raises."""
    try:
        return transform_shots(shots, strategy)
    except Exception:
        logger.warning("Mask transform failed; staying on the opaque veil.", exc_info=True)
        return []


class TransformExecutor(Protocol):
    """Runs the mask transform and delivers the result on the owning thread."""

    def submit(
        self, shots: list[ScreenShot], strategy: MaskStrategy, on_done: TransformCallback
    ) -> None:
        """Transform ``shots`` and call ``on_done`` with the result (``[]`` on failure)."""
        ...


class SynchronousTransformExecutor:
    """Runs the transform inline — deterministic tests and simple callers."""

    def submit(
        self, shots: list[ScreenShot], strategy: MaskStrategy, on_done: TransformCallback
    ) -> None:
        """Transform now and deliver immediately."""
        on_done(_safe_transform(shots, strategy))


class ManualTransformExecutor:
    """Queues jobs until the test flushes them — models in-flight transforms/races."""

    def __init__(self) -> None:
        """Start with an empty queue."""
        self.pending: list[tuple[list[ScreenShot], MaskStrategy, TransformCallback]] = []

    def submit(
        self, shots: list[ScreenShot], strategy: MaskStrategy, on_done: TransformCallback
    ) -> None:
        """Park the job; nothing runs until :meth:`flush_one`/:meth:`flush`."""
        self.pending.append((shots, strategy, on_done))

    def flush_one(self) -> None:
        """Run and deliver the oldest pending job."""
        shots, strategy, on_done = self.pending.pop(0)
        on_done(_safe_transform(shots, strategy))

    def flush(self) -> None:
        """Run and deliver every pending job, in order."""
        while self.pending:
            self.flush_one()

    def deliver_empty(self) -> None:
        """Complete the oldest job with ``[]`` (models an executor-side failure)."""
        _shots, _strategy, on_done = self.pending.pop(0)
        on_done([])


class FreezeFrameCompositor:
    """Drives one masking engagement: grab → veil now → transform → swap → lift.

    ``strategy=None`` is the plain-veil mode (v0.2.1 behaviour): no capture is
    ever attempted. The compositor itself retains no frame reference at any
    point — shots flow straight from grabber to executor to presenter (P2).
    """

    def __init__(
        self,
        grabber: ScreenGrabber,
        strategy: MaskStrategy | None,
        presenter: MaskPresenter,
        executor: TransformExecutor,
    ) -> None:
        """Wire the collaborators; starts idle."""
        self._grabber = grabber
        self._strategy = strategy
        self._presenter = presenter
        self._executor = executor
        self._state = CompositorState.IDLE
        # Bumped on every engage/disengage: a completion carrying an older
        # generation is stale (the mask was lifted or re-engaged meanwhile).
        self._generation = 0

    @property
    def state(self) -> CompositorState:
        """Current engagement state."""
        return self._state

    @property
    def is_engaged(self) -> bool:
        """Whether the masking layer is currently shown (veil or frames)."""
        return self._state is not CompositorState.IDLE

    def engage(self) -> None:
        """Mask now. Re-engaging while masked is a no-op (P3: no second capture)."""
        if self._state is not CompositorState.IDLE:
            return
        self._generation += 1
        if self._strategy is None:
            self._presenter.show_veil()
            self._state = CompositorState.VEILED
            return
        # Capture FIRST: once the veil is up, a grab would photograph the veil.
        shots = self._grabber.grab_all()
        self._presenter.show_veil()  # P1: protection is on before any heavy work
        self._state = CompositorState.VEILED
        usable = [shot for shot in shots if not looks_blank(shot.image)]
        if not shots:
            logger.warning("Screen capture failed; keeping the opaque veil (P4).")
            return
        if not usable:
            logger.warning("All captured screens look blank; keeping the opaque veil (P4).")
            return
        generation = self._generation
        strategy = self._strategy
        self._executor.submit(
            usable, strategy, lambda frames: self._on_transformed(generation, frames)
        )

    def disengage(self) -> None:
        """Lift the mask, drop frames (P2) and invalidate in-flight transforms."""
        if self._state is CompositorState.IDLE:
            return
        self._generation += 1
        self._presenter.hide()
        self._state = CompositorState.IDLE

    def _on_transformed(self, generation: int, frames: list[ScreenShot]) -> None:
        if generation != self._generation or self._state is not CompositorState.VEILED:
            return  # stale: the mask was lifted or re-engaged since this was submitted
        if not frames:
            return  # transform failed (P4): the opaque veil is already protecting
        self._presenter.show_frames(frames)
        self._state = CompositorState.TRANSFORMED
