"""Offscreen smoke test for the Qt screen grabber (M-FP2).

The offscreen platform has no real screen, so what matters here is the
*contract*, not a successful capture: ``grab_all`` must never raise, and must
return either valid ``ScreenShot`` objects or ``[]`` (the P4 failure signal).
The real-capture path is exercised manually on a machine with a display.
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtGui import QGuiApplication

from privacy_guard.overlay import QtScreenGrabber, ScreenShot

pytestmark = pytest.mark.component


def test_grab_all_honours_the_contract_offscreen(qapp: QGuiApplication) -> None:
    shots = QtScreenGrabber().grab_all()
    assert isinstance(shots, list)
    for shot in shots:
        # ScreenShot.__post_init__ already validated shape/dtype; check coherence.
        assert isinstance(shot, ScreenShot)
        assert shot.image.dtype == np.uint8
        assert shot.width > 0
        assert shot.height > 0


def test_grab_all_never_persists_anything(qapp: QGuiApplication, tmp_path) -> None:
    # Belt-and-braces alongside tests/privacy: a capture attempt must not touch disk.
    before = sorted(tmp_path.iterdir())
    QtScreenGrabber().grab_all()
    assert sorted(tmp_path.iterdir()) == before
