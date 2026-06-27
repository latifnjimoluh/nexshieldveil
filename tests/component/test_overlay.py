"""Component tests for the overlay renderer interface (no real window)."""

from __future__ import annotations

import pytest

from privacy_guard.overlay import QtOverlayRenderer, RecordingRenderer, qt_available

pytestmark = pytest.mark.component


def test_recording_renderer_starts_unmasked() -> None:
    r = RecordingRenderer()
    assert r.is_masked is False
    assert r.transitions == []


def test_recording_renderer_records_only_transitions() -> None:
    r = RecordingRenderer()
    r.set_masked(False)  # no change
    r.set_masked(True)  # transition -> on
    r.set_masked(True)  # no change
    r.set_masked(False)  # transition -> off
    assert r.transitions == [True, False]
    assert r.calls == 4
    assert r.mask_engaged_count == 1


def test_recording_renderer_tracks_current_state() -> None:
    r = RecordingRenderer()
    r.set_masked(True)
    assert r.is_masked is True
    r.set_masked(False)
    assert r.is_masked is False


def test_recording_renderer_close_is_noop() -> None:
    r = RecordingRenderer()
    r.close()  # must not raise


def test_qt_available_is_bool() -> None:
    assert isinstance(qt_available(), bool)


@pytest.mark.skipif(qt_available(), reason="PySide6 present; degradation path not applicable")
def test_qt_overlay_degrades_without_pyside() -> None:
    with pytest.raises(RuntimeError, match="PySide6"):
        QtOverlayRenderer()
