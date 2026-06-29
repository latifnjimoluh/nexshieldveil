"""Tests for the opt-in camera preview: view-model, painter, image provider."""

from __future__ import annotations

import numpy as np
import pytest

from privacy_guard.ui.fake_controller import FakeController
from privacy_guard.ui.translator import Translator
from privacy_guard.ui.viewmodels.camera import CameraViewModel
from privacy_guard.vision import FaceObservation

pytestmark = pytest.mark.unit


def _obs(cx: float, cy: float, size: float) -> FaceObservation:
    return FaceObservation(
        center_x=cx,
        center_y=cy,
        size=size,
        position_mm=np.array([0.0, -150.0, 500.0]),
        yaw_deg=0.0,
        pitch_deg=0.0,
    )


# --------------------------------------------------------------------------- #
# CameraViewModel
# --------------------------------------------------------------------------- #
@pytest.fixture
def env(qapp):
    return FakeController(), Translator("fr")


def test_preview_off_by_default(env) -> None:
    ctrl, tr = env
    vm = CameraViewModel(ctrl, tr)
    assert vm.property("preview_enabled") is False
    assert vm.property("available") is False
    assert vm.property("toggle_label") == "Afficher la caméra"


def test_toggle_enables_and_relabels(env) -> None:
    ctrl, tr = env
    vm = CameraViewModel(ctrl, tr)
    vm.toggle()
    assert ctrl.property("preview_enabled") is True
    assert vm.property("preview_enabled") is True
    assert vm.property("toggle_label") == "Masquer la caméra"


def test_available_requires_preview_and_camera(env) -> None:
    ctrl, tr = env
    vm = CameraViewModel(ctrl, tr)
    ctrl.set_preview_enabled(True)
    assert vm.property("available") is False  # camera not delivering yet
    ctrl.emit_camera_active(True)
    assert vm.property("available") is True


def test_legend_has_three_entries_with_colors(env) -> None:
    ctrl, tr = env
    vm = CameraViewModel(ctrl, tr)
    legend = vm.property("legend")
    assert len(legend) == 3
    assert all(e["label"] and e["color"].startswith("#") for e in legend)


def test_push_frame_bumps_tick(env, record) -> None:
    ctrl, tr = env
    vm = CameraViewModel(ctrl, tr)  # no provider -> just counts
    ticks = record(vm.frame_tick_changed)
    from PySide6.QtGui import QImage

    vm.push_frame(QImage(4, 4, QImage.Format.Format_RGB888))
    vm.push_frame(QImage(4, 4, QImage.Format.Format_RGB888))
    assert vm.property("frame_tick") == 2
    assert len(ticks) == 2


def test_legend_translates(env) -> None:
    ctrl, tr = env
    vm = CameraViewModel(ctrl, tr)
    tr.language = "en"
    assert vm.property("legend")[0]["label"] == "You (primary)"


def test_set_enabled_forwards(env) -> None:
    ctrl, tr = env
    vm = CameraViewModel(ctrl, tr)
    vm.set_enabled(True)
    assert ctrl.property("preview_enabled") is True
    vm.set_enabled(False)
    assert ctrl.property("preview_enabled") is False


def test_push_frame_updates_provider(env) -> None:
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QImage

    from privacy_guard.ui.preview import CameraImageProvider

    ctrl, tr = env
    provider = CameraImageProvider()
    vm = CameraViewModel(ctrl, tr, provider)
    vm.push_frame(QImage(12, 8, QImage.Format.Format_RGB888))
    assert provider.requestImage("x", QSize(), QSize()).width() == 12


# --------------------------------------------------------------------------- #
# painter + provider
# --------------------------------------------------------------------------- #
def test_annotate_frame_returns_qimage_of_same_size(qapp) -> None:
    from privacy_guard.ui.preview import annotate_frame

    image = np.zeros((120, 160, 3), dtype=np.uint8)
    observations = [_obs(0.5, 0.5, 0.3), _obs(0.85, 0.45, 0.08)]
    qimg = annotate_frame(image, observations, [True, True], primary_index=0)
    assert not qimg.isNull()
    assert qimg.width() == 160
    assert qimg.height() == 120


def test_annotate_frame_handles_no_faces(qapp) -> None:
    from privacy_guard.ui.preview import annotate_frame

    qimg = annotate_frame(np.zeros((60, 80, 3), dtype=np.uint8), [], [], None)
    assert qimg.width() == 80


def test_image_provider_serves_latest(qapp) -> None:
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QImage

    from privacy_guard.ui.preview import CameraImageProvider

    provider = CameraImageProvider()
    img = QImage(10, 10, QImage.Format.Format_RGB888)
    provider.set_image(img)
    served = provider.requestImage("1", QSize(), QSize())
    assert served.width() == 10
