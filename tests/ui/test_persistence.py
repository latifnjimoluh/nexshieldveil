"""Round-trip tests for user-settings persistence (M-R2, headless).

The store is a dict faking QSettings; restoring goes through the controller's
real setter slots, so these tests also prove that a corrupt/hand-edited store
degrades to defaults or clamped values — it can never crash startup.
"""

from __future__ import annotations

import pytest

from privacy_guard.ui.fake_controller import FakeController
from privacy_guard.ui.persistence import PERSISTED_FIELDS, restore_settings, save_settings
from privacy_guard.ui.state import UiSnapshot

pytestmark = pytest.mark.unit


class DictStore:
    """QSettings-shaped, dict-backed store."""

    def __init__(self, data: dict[str, object] | None = None) -> None:
        self.data = dict(data or {})

    def value(self, key: str) -> object:
        return self.data.get(key)

    def setValue(self, key: str, value: object) -> None:  # QSettings-shaped name
        self.data[key] = value


def _store(**settings: object) -> DictStore:
    return DictStore({f"settings/{k}": v for k, v in settings.items()})


@pytest.fixture
def ctrl(qapp) -> FakeController:
    return FakeController()


# --------------------------------------------------------------------------- #
# round trip: what the user set is exactly what comes back
# --------------------------------------------------------------------------- #
def test_round_trip_restores_every_user_setting(qapp) -> None:
    src = FakeController()
    src.set_masking_strategy("pixelate")
    src.set_opacity(0.75)
    src.set_blur_radius(31)
    src.set_pixelate_blocks(48)
    src.set_sensitivity_deg(24.0)
    src.set_trigger_ms(600)
    src.set_release_ms(900)
    src.set_start_at_login(True)

    store = DictStore()
    save_settings(src.snapshot, store)
    dst = FakeController()
    restore_settings(dst, store)

    for field in PERSISTED_FIELDS:
        assert getattr(dst.snapshot, field) == getattr(src.snapshot, field), field


def test_saved_keys_are_exactly_the_user_settings(ctrl: FakeController) -> None:
    # Session state (running/preview/errors) must never be persisted: the
    # preview is opt-in per session and errors are re-derived live.
    ctrl.enable()
    ctrl.set_preview_enabled(True)
    store = DictStore()
    save_settings(ctrl.snapshot, store)
    assert set(store.data) == {f"settings/{f}" for f in PERSISTED_FIELDS}
    assert "settings/running" not in store.data
    assert "settings/preview_enabled" not in store.data


def test_missing_keys_keep_the_defaults(ctrl: FakeController) -> None:
    defaults = {f: getattr(ctrl.snapshot, f) for f in PERSISTED_FIELDS}
    restore_settings(ctrl, DictStore())
    assert {f: getattr(ctrl.snapshot, f) for f in PERSISTED_FIELDS} == defaults


# --------------------------------------------------------------------------- #
# tolerance: registry stringification, junk, out-of-range
# --------------------------------------------------------------------------- #
def test_registry_stringified_values_are_coerced(ctrl: FakeController) -> None:
    restore_settings(
        ctrl,
        _store(
            masking_strategy="pixelate",
            opacity="0.85",
            blur_radius="31",
            pixelate_blocks="48",
            sensitivity_deg="22.5",
            trigger_ms="600",
            release_ms="900",
            start_at_login="true",
        ),
    )
    snap = ctrl.snapshot
    assert snap.masking_strategy == "pixelate"
    assert snap.opacity == 0.85
    assert snap.blur_radius == 31
    assert snap.pixelate_blocks == 48
    assert snap.sensitivity_deg == 22.5
    assert snap.trigger_ms == 600
    assert snap.release_ms == 900
    assert snap.start_at_login is True


def test_junk_values_are_dropped_without_crashing(ctrl: FakeController) -> None:
    defaults = {f: getattr(ctrl.snapshot, f) for f in PERSISTED_FIELDS}
    restore_settings(
        ctrl,
        _store(
            masking_strategy="hologram",  # not a runtime strategy
            opacity="abc",
            blur_radius="beaucoup",
            pixelate_blocks=None,
            sensitivity_deg="",
            trigger_ms="12.5.7",
            release_ms=object(),
            start_at_login="peut-etre",
        ),
    )
    assert {f: getattr(ctrl.snapshot, f) for f in PERSISTED_FIELDS} == defaults


def test_out_of_range_values_are_clamped_by_the_setters(ctrl: FakeController) -> None:
    restore_settings(
        ctrl,
        _store(
            opacity="5.0",
            blur_radius="10000",
            pixelate_blocks="1",
            sensitivity_deg="500",
            trigger_ms="-50",
        ),
    )
    snap = ctrl.snapshot
    assert snap.opacity == 1.0
    assert snap.blur_radius == 199
    assert snap.pixelate_blocks == 2
    assert snap.sensitivity_deg == 89.0
    assert snap.trigger_ms == 0


def test_bool_variants_from_the_registry(ctrl: FakeController) -> None:
    restore_settings(ctrl, _store(start_at_login="false"))
    assert ctrl.snapshot.start_at_login is False
    restore_settings(ctrl, _store(start_at_login=1))
    assert ctrl.snapshot.start_at_login is True
    restore_settings(ctrl, _store(start_at_login=True))
    assert ctrl.snapshot.start_at_login is True


# --------------------------------------------------------------------------- #
# hysteresis: trigger/release ordering and invariant survive the round trip
# --------------------------------------------------------------------------- #
def test_release_smaller_than_default_trigger_survives_restore(ctrl: FakeController) -> None:
    # Saved trigger=250/release=300 with defaults 400/800: restoring release
    # before trigger would inflate it to 400. The field order prevents that.
    restore_settings(ctrl, _store(trigger_ms=250, release_ms=300))
    assert ctrl.snapshot.trigger_ms == 250
    assert ctrl.snapshot.release_ms == 300


def test_hand_edited_release_below_trigger_keeps_the_invariant(ctrl: FakeController) -> None:
    restore_settings(ctrl, _store(trigger_ms=500, release_ms=200))
    assert ctrl.snapshot.trigger_ms == 500
    assert ctrl.snapshot.release_ms >= ctrl.snapshot.trigger_ms  # never a flickering config


# --------------------------------------------------------------------------- #
# screen geometry (AM-10b): persisted only when the user corrected it
# --------------------------------------------------------------------------- #
def test_a_measured_screen_size_is_not_frozen_into_the_store() -> None:
    # Persisting a value that merely came from the OS would keep the old
    # screen's size forever after plugging in a different monitor.
    store = DictStore()
    save_settings(UiSnapshot(screen_width_mm=290.0, screen_height_mm=170.0), store)
    assert store.data["settings/screen_width_mm"] is None
    assert store.data["settings/screen_height_mm"] is None


def test_a_manual_correction_is_persisted_and_restored(ctrl: FakeController) -> None:
    store = DictStore()
    save_settings(
        UiSnapshot(
            screen_width_mm=345.0,
            screen_height_mm=195.0,
            camera_above_mm=25.0,
            screen_size_manual=True,
        ),
        store,
    )
    assert store.data["settings/screen_width_mm"] == 345.0

    restore_settings(ctrl, store)
    assert ctrl.snapshot.screen_width_mm == 345.0
    assert ctrl.snapshot.screen_height_mm == 195.0
    assert ctrl.snapshot.camera_above_mm == 25.0
    # Restoring a correction means it IS a correction.
    assert ctrl.snapshot.screen_size_manual is True


def test_resetting_the_correction_forgets_it(ctrl: FakeController) -> None:
    store = DictStore()
    save_settings(UiSnapshot(screen_width_mm=345.0, screen_size_manual=True), store)
    # The user hits "measure again": the stored value must be cleared, not left
    # behind to be restored on the next start.
    save_settings(UiSnapshot(screen_width_mm=345.0, screen_size_manual=False), store)
    restore_settings(ctrl, store)
    assert ctrl.snapshot.screen_size_manual is False
    assert ctrl.snapshot.screen_width_mm == UiSnapshot().screen_width_mm
