"""Offscreen tests for the Qt mask presenter and overlay widgets (M-FP4).

The offscreen platform provides one virtual screen, which is enough to prove
the behavioural contract: one always-on-top click-through window per screen,
veil mode vs frame mode, geometry-based frame matching, crossfade, and frame
release on hide (P2). Real multi-monitor/DPI rendering is verified manually
with ``scripts/demo_overlay.py``.
"""

from __future__ import annotations

import gc
import time
import weakref

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from privacy_guard.overlay import QtMaskPresenter, QtOverlayRenderer, ScreenShot

pytestmark = pytest.mark.component

rng = np.random.default_rng(31)


@pytest.fixture
def presenter(qapp: QApplication):
    p = QtMaskPresenter(fade_ms=0)
    yield p
    p.close()
    qapp.processEvents()


def _frame_for_screen(qapp: QApplication) -> ScreenShot:
    geometry = qapp.screens()[0].geometry()
    image = rng.integers(0, 256, size=(48, 64, 3), dtype=np.uint8)
    return ScreenShot(
        image=image,
        x=geometry.x(),
        y=geometry.y(),
        width=geometry.width(),
        height=geometry.height(),
    )


def test_show_veil_covers_every_screen_with_a_click_through_window(
    presenter: QtMaskPresenter, qapp: QApplication
) -> None:
    presenter.show_veil()
    assert len(presenter.widgets) == len(qapp.screens())
    for widget in presenter.widgets:
        assert widget.isVisible()
        flags = widget.windowFlags()
        assert flags & Qt.WindowType.FramelessWindowHint
        assert flags & Qt.WindowType.WindowStaysOnTopHint
        assert flags & Qt.WindowType.WindowTransparentForInput
        assert widget.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        assert widget.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        assert not widget.has_frame  # veil mode until a frame arrives


def test_show_frames_attaches_the_frame_to_the_matching_screen(
    presenter: QtMaskPresenter, qapp: QApplication
) -> None:
    presenter.show_veil()
    presenter.show_frames([_frame_for_screen(qapp)])
    (widget,) = presenter.widgets
    assert widget.has_frame
    assert widget.frame_opacity == 1.0  # fade_ms=0: swapped in immediately


def test_frame_for_an_unknown_screen_is_ignored_and_the_veil_stays(
    presenter: QtMaskPresenter, qapp: QApplication
) -> None:
    presenter.show_veil()
    stray = ScreenShot(
        image=rng.integers(0, 256, size=(8, 8, 3), dtype=np.uint8),
        x=99_999,
        y=99_999,
        width=8,
        height=8,
    )
    presenter.show_frames([stray])  # must not raise (P4: that screen keeps the veil)
    (widget,) = presenter.widgets
    assert not widget.has_frame
    assert widget.isVisible()


def test_hide_releases_frames_and_windows(presenter: QtMaskPresenter, qapp: QApplication) -> None:
    presenter.show_veil()
    presenter.show_frames([_frame_for_screen(qapp)])
    presenter.hide()
    (widget,) = presenter.widgets
    assert not widget.isVisible()
    assert not widget.has_frame  # P2: nothing survives the lift


def test_reengaging_shows_a_fresh_veil_not_a_stale_frame(
    presenter: QtMaskPresenter, qapp: QApplication
) -> None:
    presenter.show_veil()
    presenter.show_frames([_frame_for_screen(qapp)])
    presenter.hide()
    presenter.show_veil()
    (widget,) = presenter.widgets
    assert widget.isVisible()
    assert not widget.has_frame


def test_presenter_does_not_retain_the_numpy_capture(
    presenter: QtMaskPresenter, qapp: QApplication
) -> None:
    # The QImage handed to the widget must own its pixels: once the caller
    # drops the ScreenShot, the captured numpy array has to be collectable
    # even while the frame is still displayed.
    frame = _frame_for_screen(qapp)
    array_ref = weakref.ref(frame.image)
    presenter.show_veil()
    presenter.show_frames([frame])
    del frame
    gc.collect()
    assert array_ref() is None
    assert presenter.widgets[0].has_frame  # still displayed, on its own copy


def test_crossfade_reaches_full_opacity(qapp: QApplication) -> None:
    presenter = QtMaskPresenter(fade_ms=40)
    try:
        presenter.show_veil()
        presenter.show_frames([_frame_for_screen(qapp)])
        (widget,) = presenter.widgets
        deadline = time.monotonic() + 5.0
        while widget.frame_opacity < 1.0 and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.005)
        assert widget.frame_opacity == 1.0
    finally:
        presenter.close()
        qapp.processEvents()


def test_paint_paths_render_offscreen_in_both_modes(
    presenter: QtMaskPresenter, qapp: QApplication
) -> None:
    # grab() executes paintEvent headlessly: veil-only first, then with frame.
    presenter.show_veil()
    (widget,) = presenter.widgets
    veil_shot = widget.grab()
    assert not veil_shot.isNull()
    presenter.show_frames([_frame_for_screen(qapp)])
    frame_shot = widget.grab()
    assert not frame_shot.isNull()


def test_renderer_veils_every_screen_and_tracks_state(qapp: QApplication) -> None:
    renderer = QtOverlayRenderer()
    try:
        assert renderer.is_masked is False
        renderer.set_masked(True)
        assert renderer.is_masked is True
        widgets = renderer._presenter.widgets
        assert len(widgets) == len(qapp.screens())
        assert all(w.isVisible() for w in widgets)
        renderer.set_masked(False)
        assert renderer.is_masked is False
        assert all(not w.isVisible() for w in widgets)
    finally:
        renderer.close()
        qapp.processEvents()
