"""Tests for the view-models against the FakeController + a real Translator (headless).

This is the bulk of the presentation-logic coverage: state mapping, property updates,
signal emission, command handling, and i18n re-translation — all without a display.
"""

from __future__ import annotations

import re

import pytest

from privacy_guard import __version__
from privacy_guard.ui.fake_controller import FakeController
from privacy_guard.ui.state import CameraError, UiSnapshot
from privacy_guard.ui.translator import Translator
from privacy_guard.ui.viewmodels import (
    AboutViewModel,
    OnboardingViewModel,
    SettingsViewModel,
    StatusViewModel,
    TrayViewModel,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def env(qapp):
    ctrl = FakeController()
    tr = Translator("fr")
    return ctrl, tr


# --------------------------------------------------------------------------- #
# StatusViewModel
# --------------------------------------------------------------------------- #
def test_status_reflects_each_state(env) -> None:
    ctrl, tr = env
    vm = StatusViewModel(ctrl, tr)

    # paused (default)
    assert vm.property("state_key") == "paused"
    assert vm.property("color_role") == "paused"
    assert vm.property("headline") == "En pause"

    ctrl.enable()
    assert vm.property("state_key") == "clear"
    assert vm.property("color_role") == "clear"

    ctrl.emit_masked(True)
    assert vm.property("state_key") == "protected"
    assert vm.property("color_role") == "protected"
    assert vm.property("headline") == "Protégé"

    ctrl.emit_error(CameraError.NO_CAMERA)
    assert vm.property("state_key") == "camera_error"
    assert vm.property("color_role") == "error"
    assert vm.property("is_error") is True
    assert "Aucune caméra" in vm.property("detail")


def test_status_engaging_detail(env) -> None:
    ctrl, tr = env
    vm = StatusViewModel(ctrl, tr)
    ctrl.emit_observer_detected()
    assert vm.property("state_key") == "clear"
    assert vm.property("detail") == "Observateur repéré…"


def test_status_camera_badge_and_faces(env) -> None:
    ctrl, tr = env
    vm = StatusViewModel(ctrl, tr)
    ctrl.enable()
    ctrl.emit_camera_active(True)
    ctrl.emit_faces(2)
    assert vm.property("camera_active") is True
    assert vm.property("camera_label") == "Caméra active"
    assert vm.property("show_faces") is True
    assert vm.property("faces_text") == "Visages vus : 2"


def test_status_faces_hidden_when_error(env) -> None:
    ctrl, tr = env
    vm = StatusViewModel(ctrl, tr)
    ctrl.emit_error(CameraError.DISCONNECTED)
    assert vm.property("show_faces") is False


def test_status_changed_emitted_on_state_change(env, record) -> None:
    ctrl, tr = env
    vm = StatusViewModel(ctrl, tr)
    events = record(vm.changed)
    ctrl.enable()
    assert len(events) >= 1


def test_status_activate_primary_toggles(env) -> None:
    ctrl, tr = env
    vm = StatusViewModel(ctrl, tr)
    # paused -> resume -> running
    vm.activate_primary()
    assert ctrl.property("running") is True
    # running -> pause
    vm.activate_primary()
    assert ctrl.property("running") is False


def test_status_activate_primary_retry_on_recoverable_error(env) -> None:
    ctrl, tr = env
    vm = StatusViewModel(ctrl, tr)
    ctrl.emit_error(CameraError.NO_CAMERA)
    vm.activate_primary()  # 'retry' -> enable()
    assert ctrl.property("running") is True


def test_status_activate_primary_defers_permission_to_shell(env, record) -> None:
    ctrl, tr = env
    vm = StatusViewModel(ctrl, tr)
    requested = record(vm.action_requested)
    ctrl.emit_error(CameraError.PERMISSION_DENIED)
    vm.activate_primary()
    assert requested == [("open_system_settings",)]


def test_status_language_switch_retranslates(env) -> None:
    ctrl, tr = env
    vm = StatusViewModel(ctrl, tr)
    assert vm.property("headline") == "En pause"
    tr.language = "en"
    assert vm.property("headline") == "Paused"


# --------------------------------------------------------------------------- #
# TrayViewModel
# --------------------------------------------------------------------------- #
def test_tray_icon_and_tooltip(env) -> None:
    ctrl, tr = env
    vm = TrayViewModel(ctrl, tr)
    assert vm.property("icon_state") == "paused"
    assert vm.property("tooltip") == "NexShieldVeil — En pause"
    ctrl.emit_masked(True)
    assert vm.property("icon_state") == "protected"
    assert "Protégé" in vm.property("tooltip")


def test_tray_toggle_label_mirrors_running(env) -> None:
    ctrl, tr = env
    vm = TrayViewModel(ctrl, tr)
    assert vm.property("toggle_label") == "Reprendre la surveillance"
    ctrl.enable()
    assert vm.property("toggle_label") == "Mettre en pause"


def test_tray_commands_forward_to_controller(env) -> None:
    ctrl, tr = env
    vm = TrayViewModel(ctrl, tr)
    vm.toggle()
    assert ctrl.property("running") is True
    vm.open_settings()
    vm.quit()
    assert ctrl.settings_opened == 1
    assert ctrl.quit_calls == 1


def test_tray_menu_labels(env) -> None:
    ctrl, tr = env
    vm = TrayViewModel(ctrl, tr)
    assert vm.property("settings_label") == "Réglages…"
    assert vm.property("about_label") == "À propos & limites"
    assert vm.property("quit_label") == "Quitter"
    assert vm.property("camera_label") == "Caméra inactive"
    ctrl.emit_camera_active(True)
    assert vm.property("camera_label") == "Caméra active"


# --------------------------------------------------------------------------- #
# SettingsViewModel
# --------------------------------------------------------------------------- #
def test_settings_sensitivity_caption(env) -> None:
    ctrl, tr = env
    vm = SettingsViewModel(ctrl, tr)
    ctrl.set_sensitivity_deg(18.0)
    assert vm.property("sensitivity_caption") == "18° · équilibré"
    ctrl.set_sensitivity_deg(5.0)
    assert vm.property("sensitivity_caption") == "5° · strict"


def test_settings_trigger_raises_release(env) -> None:
    ctrl, tr = env
    vm = SettingsViewModel(ctrl, tr)
    vm.set_release_ms(800)
    vm.set_trigger_ms(1000)
    assert vm.property("trigger_ms") == 1000
    assert vm.property("release_ms") == 1000
    assert vm.property("release_floor") == 1000


def test_settings_masking_options_all_live_since_mfp5(env) -> None:
    ctrl, tr = env
    vm = SettingsViewModel(ctrl, tr)
    options = {o["id"]: o for o in vm.property("masking_options")}
    for name in ("veil", "blur", "pixelate"):
        assert options[name]["live"] is True
        assert options[name]["note"] == ""  # no more "soon" note anywhere


def test_settings_forwards_edits(env) -> None:
    ctrl, tr = env
    vm = SettingsViewModel(ctrl, tr)
    vm.set_masking_strategy("blur")
    vm.set_opacity(0.5)
    vm.select_camera(3)
    vm.set_start_at_login(True)
    assert ctrl.property("masking_strategy") == "blur"
    assert ctrl.property("opacity") == 0.5
    assert ctrl.property("camera_index") == 3
    assert ctrl.property("start_at_login") is True


def test_settings_masking_parameters_and_captions(env) -> None:
    ctrl, tr = env
    vm = SettingsViewModel(ctrl, tr)
    vm.set_blur_radius(41)
    vm.set_pixelate_blocks(12)
    assert vm.property("blur_radius") == 41
    assert vm.property("blur_radius_caption") == "41 px"
    assert vm.property("pixelate_blocks") == 12
    assert vm.property("pixelate_blocks_caption") == "12 blocs"  # env fixture is fr


def test_settings_language_switch(env) -> None:
    ctrl, tr = env
    vm = SettingsViewModel(ctrl, tr)
    assert vm.property("language") == "fr"
    vm.set_language("en")
    assert vm.property("language") == "en"
    assert tr.language == "en"
    # languages list carries endonyms in both locales
    langs = {entry["code"]: entry["label"] for entry in vm.property("languages")}
    assert langs == {"fr": "Français", "en": "English"}


def test_settings_changed_on_config(env, record) -> None:
    ctrl, tr = env
    vm = SettingsViewModel(ctrl, tr)
    events = record(vm.changed)
    vm.set_sensitivity_deg(22.0)
    assert len(events) >= 1


# --------------------------------------------------------------------------- #
# OnboardingViewModel
# --------------------------------------------------------------------------- #
def test_onboarding_steps_and_clamping(env) -> None:
    ctrl, tr = env
    vm = OnboardingViewModel(ctrl, tr)
    assert vm.property("index") == 0
    assert vm.property("is_first") is True
    assert vm.property("show_limits") is True
    vm.back()  # clamped
    assert vm.property("index") == 0
    vm.next()
    assert vm.property("index") == 1
    assert vm.property("show_camera_consent") is True
    vm.next()
    assert vm.property("is_last") is True
    vm.next()  # clamped
    assert vm.property("index") == 2


def test_onboarding_back_from_later_step(env) -> None:
    ctrl, tr = env
    vm = OnboardingViewModel(ctrl, tr)
    vm.next()
    vm.next()
    assert vm.property("index") == 2
    vm.back()
    assert vm.property("index") == 1


def test_onboarding_titles_translate_per_step(env) -> None:
    ctrl, tr = env
    vm = OnboardingViewModel(ctrl, tr)
    assert "voile" in vm.property("title").lower()
    assert vm.property("limits_title") == "Ce qu'il ne protège pas"


def test_onboarding_consent_then_finish_enables(env) -> None:
    ctrl, tr = env
    vm = OnboardingViewModel(ctrl, tr)
    vm.next()  # to consent step
    vm.allow_camera()
    assert vm.property("camera_granted") is True
    assert vm.property("index") == 2
    vm.finish()
    assert ctrl.onboarding_done == 1
    assert ctrl.property("running") is True


def test_onboarding_skip_then_finish_does_not_enable(env) -> None:
    ctrl, tr = env
    vm = OnboardingViewModel(ctrl, tr)
    vm.next()
    vm.skip_camera()
    vm.finish()
    assert ctrl.onboarding_done == 1
    assert ctrl.property("running") is False


# --------------------------------------------------------------------------- #
# AboutViewModel
# --------------------------------------------------------------------------- #
def test_about_version_and_limits(env) -> None:
    _, tr = env
    vm = AboutViewModel(tr)
    assert __version__ in vm.property("version")
    limits = vm.property("limits")
    assert len(limits) == 5
    assert all(isinstance(item, str) and item for item in limits)


def test_about_states_the_screen_capture_honestly(env) -> None:
    # M-FP6: the About screen must disclose the freeze-frame capture in plain
    # words — local, memory-only, released on lift.
    _, tr = env
    vm = AboutViewModel(tr)
    text = vm.property("capture_text")
    assert "capture" in text.lower()
    assert "mémoire" in text  # env fixture is fr


def test_about_tagline_translates(env) -> None:
    _, tr = env
    vm = AboutViewModel(tr)
    assert "sans le supprimer" in vm.property("tagline")
    tr.language = "en"
    assert "does not remove" in vm.property("tagline")


def test_about_starts_from_snapshot_independent(qapp) -> None:
    # AboutViewModel needs only a translator, no controller/snapshot.
    tr = Translator("en")
    vm = AboutViewModel(tr)
    assert vm.property("limits_title") == "What NexShieldVeil does not protect against"


# --------------------------------------------------------------------------- #
# all keys referenced by view-models actually resolve (no key == translation)
# --------------------------------------------------------------------------- #
def test_no_missing_translation_in_built_viewmodels(qapp) -> None:
    # A missing translation returns the raw key (e.g. "status.protected.headline"):
    # dotted, no spaces. Real copy never matches that shape.
    looks_like_key = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")
    for lang in ("fr", "en"):
        tr = Translator(lang)
        ctrl = FakeController(UiSnapshot(running=True, error_kind=CameraError.PERMISSION_DENIED))
        status = StatusViewModel(ctrl, tr)
        tray = TrayViewModel(ctrl, tr)
        settings = SettingsViewModel(ctrl, tr)
        about = AboutViewModel(tr)
        onboarding = OnboardingViewModel(ctrl, tr)
        texts = [
            status.property("headline"),
            status.property("detail"),
            status.property("primary_action_label"),
            tray.property("toggle_label"),
            tray.property("settings_label"),
            settings.property("sensitivity_caption"),
            about.property("tagline"),
            onboarding.property("title"),
        ]
        for text in texts:
            assert text, "empty translation"
            assert not looks_like_key.match(text), f"untranslated key leaked: {text}"
