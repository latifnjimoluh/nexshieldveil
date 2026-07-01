"""Unit tests for the freeze-frame compositor (M-FP3) — one rule per test.

Non-negotiable rules from docs/ROADMAP_FLOU_PIXELISATION.md:
P1 — the opaque veil shows immediately; the transform never delays masking.
P2 — screen frames are released as soon as the mask lifts.
P3 — exactly one capture per engagement, never a stream.
P4 — any capture/transform failure degrades to the opaque veil, never to
     "no masking" and never to an exception.
"""

from __future__ import annotations

import gc
import weakref

import numpy as np
import pytest

from privacy_guard.masking import BlurMask, MaskStrategy
from privacy_guard.overlay import (
    CompositorState,
    FakeScreenGrabber,
    FreezeFrameCompositor,
    ManualTransformExecutor,
    RecordingPresenter,
    ScreenShot,
    SynchronousTransformExecutor,
    transform_shots,
)

pytestmark = pytest.mark.unit

rng = np.random.default_rng(11)


def _noisy_shot(h: int = 40, w: int = 56, x: int = 0) -> ScreenShot:
    image = rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
    return ScreenShot(image=image, x=x, y=0, width=w, height=h)


def _blank_shot() -> ScreenShot:
    return ScreenShot(image=np.zeros((40, 56, 3), dtype=np.uint8), x=0, y=0, width=56, height=40)


class _LoggingGrabber(FakeScreenGrabber):
    """Fake grabber that also appends to a shared event log (ordering tests)."""

    def __init__(self, log: list[str], **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._log = log

    def grab_all(self) -> list[ScreenShot]:
        self._log.append("grab")
        return super().grab_all()


class _ExplodingStrategy(MaskStrategy):
    def apply(self, image: np.ndarray) -> np.ndarray:
        raise RuntimeError("boom")

    @property
    def name(self) -> str:
        return "exploding"


_DEFAULT = object()  # sentinel: "strategy not overridden" (None means veil-only mode)


def _build(
    *,
    strategy: MaskStrategy | None | object = _DEFAULT,
    grabber: FakeScreenGrabber | None = None,
    executor: object | None = None,
) -> tuple[FreezeFrameCompositor, FakeScreenGrabber, RecordingPresenter]:
    if strategy is _DEFAULT:
        strategy = BlurMask(radius=5)
    grabber = grabber if grabber is not None else FakeScreenGrabber(shots=[_noisy_shot()])
    presenter = RecordingPresenter()
    compositor = FreezeFrameCompositor(
        grabber=grabber,
        strategy=strategy,
        presenter=presenter,
        executor=executor if executor is not None else SynchronousTransformExecutor(),
    )
    return compositor, grabber, presenter


# --------------------------------------------------------------------------- #
# transform_shots (the pure transform step)
# --------------------------------------------------------------------------- #
def test_transform_shots_applies_strategy_and_keeps_geometry() -> None:
    shot = _noisy_shot(x=1920)
    strategy = BlurMask(radius=5)
    (out,) = transform_shots([shot], strategy)
    assert np.array_equal(out.image, strategy.apply(shot.image))
    assert (out.x, out.y, out.width, out.height) == (1920, 0, 56, 40)
    assert out.image.dtype == np.uint8


# --------------------------------------------------------------------------- #
# veil-only mode (v0.2.1 behaviour unchanged: no capture, ever)
# --------------------------------------------------------------------------- #
def test_veil_only_mode_never_captures() -> None:
    compositor, grabber, presenter = _build(strategy=None)
    compositor.engage()
    assert grabber.calls == 0
    assert presenter.veil_calls == 1
    assert compositor.state is CompositorState.VEILED
    compositor.disengage()
    assert presenter.hide_calls == 1
    assert compositor.state is CompositorState.IDLE


# --------------------------------------------------------------------------- #
# P1 + ordering: capture first (or we'd capture the veil), veil immediately
# --------------------------------------------------------------------------- #
def test_capture_happens_before_the_veil_is_shown() -> None:
    log: list[str] = []
    grabber = _LoggingGrabber(log, shots=[_noisy_shot()])
    presenter = RecordingPresenter(log=log)
    compositor = FreezeFrameCompositor(
        grabber=grabber,
        strategy=BlurMask(radius=5),
        presenter=presenter,
        executor=SynchronousTransformExecutor(),
    )
    compositor.engage()
    assert log[:2] == ["grab", "veil"]


def test_veil_shows_even_while_transform_is_still_pending() -> None:
    executor = ManualTransformExecutor()
    compositor, _grabber, presenter = _build(executor=executor)
    compositor.engage()
    assert presenter.veil_calls == 1  # P1: veiled instantly...
    assert presenter.frames_shown == []  # ...while the transform hasn't landed
    assert compositor.state is CompositorState.VEILED
    executor.flush()
    assert len(presenter.frames_shown) == 1
    assert compositor.state is CompositorState.TRANSFORMED


# --------------------------------------------------------------------------- #
# happy path
# --------------------------------------------------------------------------- #
def test_engage_shows_transformed_frames() -> None:
    strategy = BlurMask(radius=5)
    shot = _noisy_shot()
    compositor, _grabber, presenter = _build(
        strategy=strategy, grabber=FakeScreenGrabber(shots=[shot])
    )
    compositor.engage()
    assert compositor.state is CompositorState.TRANSFORMED
    (frames,) = presenter.frames_shown
    assert np.array_equal(frames[0].image, strategy.apply(shot.image))


def test_disengage_hides_and_returns_to_idle_and_can_reengage() -> None:
    compositor, grabber, presenter = _build()
    assert not compositor.is_engaged
    compositor.engage()
    assert compositor.is_engaged
    compositor.disengage()
    assert not compositor.is_engaged
    assert presenter.hide_calls == 1
    assert compositor.state is CompositorState.IDLE
    compositor.engage()
    assert grabber.calls == 2
    assert compositor.state is CompositorState.TRANSFORMED


def test_disengage_when_idle_is_a_no_op() -> None:
    compositor, _grabber, presenter = _build()
    compositor.disengage()
    assert presenter.hide_calls == 0
    assert compositor.state is CompositorState.IDLE


# --------------------------------------------------------------------------- #
# P3: one capture per engagement
# --------------------------------------------------------------------------- #
def test_reengage_while_masked_never_recaptures() -> None:
    compositor, grabber, presenter = _build()
    compositor.engage()
    assert compositor.state is CompositorState.TRANSFORMED
    compositor.engage()  # the overlay is visible: a new grab would capture the veil
    assert grabber.calls == 1
    assert presenter.veil_calls == 1
    assert compositor.state is CompositorState.TRANSFORMED


def test_reengage_while_veiled_never_recaptures() -> None:
    executor = ManualTransformExecutor()
    compositor, grabber, _presenter = _build(executor=executor)
    compositor.engage()
    compositor.engage()
    assert grabber.calls == 1
    assert len(executor.pending) == 1


# --------------------------------------------------------------------------- #
# P4: every failure degrades to the opaque veil, never to an exception
# --------------------------------------------------------------------------- #
def test_capture_failure_stays_on_opaque_veil() -> None:
    compositor, _grabber, presenter = _build(grabber=FakeScreenGrabber(fail=True))
    compositor.engage()
    assert presenter.veil_calls == 1
    assert presenter.frames_shown == []
    assert compositor.state is CompositorState.VEILED


def test_all_blank_capture_stays_on_opaque_veil() -> None:
    compositor, _grabber, presenter = _build(grabber=FakeScreenGrabber(shots=[_blank_shot()]))
    compositor.engage()
    assert presenter.frames_shown == []
    assert compositor.state is CompositorState.VEILED


def test_blank_screens_are_dropped_but_real_ones_get_transformed() -> None:
    real = _noisy_shot(x=1920)
    grabber = FakeScreenGrabber(shots=[_blank_shot(), real])
    compositor, _grabber, presenter = _build(grabber=grabber)
    compositor.engage()
    (frames,) = presenter.frames_shown
    assert len(frames) == 1
    assert frames[0].x == 1920  # the blank screen keeps the opaque veil


def test_transform_failure_stays_on_opaque_veil() -> None:
    compositor, _grabber, presenter = _build(strategy=_ExplodingStrategy())
    compositor.engage()  # must not raise
    assert presenter.frames_shown == []
    assert compositor.state is CompositorState.VEILED


# --------------------------------------------------------------------------- #
# races: a transform landing after (or across) a lift is discarded
# --------------------------------------------------------------------------- #
def test_transform_arriving_after_lift_is_discarded() -> None:
    executor = ManualTransformExecutor()
    compositor, _grabber, presenter = _build(executor=executor)
    compositor.engage()
    compositor.disengage()  # user/policy lifted the mask while transforming
    executor.flush()
    assert presenter.frames_shown == []
    assert compositor.state is CompositorState.IDLE


def test_stale_transform_from_previous_engagement_is_discarded() -> None:
    executor = ManualTransformExecutor()
    compositor, _grabber, presenter = _build(executor=executor)
    compositor.engage()
    compositor.disengage()
    compositor.engage()  # second engagement queues a second job
    executor.flush_one()  # stale job from the first engagement
    assert presenter.frames_shown == []
    executor.flush_one()  # current job
    assert len(presenter.frames_shown) == 1
    assert compositor.state is CompositorState.TRANSFORMED


def test_empty_transform_result_stays_on_opaque_veil() -> None:
    executor = ManualTransformExecutor()
    compositor, _grabber, presenter = _build(executor=executor)
    compositor.engage()
    executor.deliver_empty()
    assert presenter.frames_shown == []
    assert compositor.state is CompositorState.VEILED


# --------------------------------------------------------------------------- #
# P2: no frame reference survives the lift
# --------------------------------------------------------------------------- #
def test_no_frame_reference_survives_disengage() -> None:
    shot = _noisy_shot()
    captured_ref = weakref.ref(shot.image)
    compositor, grabber, presenter = _build(grabber=FakeScreenGrabber(shots=[shot]))
    compositor.engage()
    transformed_ref = weakref.ref(presenter.frames_shown[0][0].image)
    compositor.disengage()
    # Drop every test-side handle, then the frames must be collectable.
    del shot
    grabber.shots.clear()
    presenter.frames_shown.clear()
    gc.collect()
    assert captured_ref() is None
    assert transformed_ref() is None
