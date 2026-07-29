"""QML view tests (headless, offscreen): smoke, state-driven, interaction, a11y.

These instantiate the real .qml files wired to the FakeController, so binding errors,
missing context properties, and broken interactions are caught without a display.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject
from PySide6.QtGui import QAccessible

from privacy_guard.ui.qml_app import VIEWS
from privacy_guard.ui.state import CameraError, UiSnapshot

pytestmark = pytest.mark.unit

# Single source of truth, shared with the shell's `--check` selfcheck (AM-16):
# a view added there is automatically smoke-tested here.
ALL_VIEWS = list(VIEWS)


def _find(root: QObject, name: str) -> QObject:
    obj = root.findChild(QObject, name)
    assert obj is not None, f"object '{name}' not found in {root}"
    return obj


def _accessible_name(obj: QObject) -> str:
    iface = QAccessible.queryAccessibleInterface(obj)
    return iface.text(QAccessible.Text.Name) if iface else ""


# --------------------------------------------------------------------------- #
# smoke: every view instantiates and binds without error
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("view", ALL_VIEWS)
def test_view_loads(qml, view) -> None:
    h = qml()
    obj = h.load(view)
    assert obj is not None


def test_every_shipped_qml_file_is_listed() -> None:
    # A .qml added to views/ but not to VIEWS would be loaded by nothing — neither
    # this smoke test nor the shell's selfcheck would ever instantiate it.
    from privacy_guard.ui.qml_app import VIEWS_DIR

    on_disk = {path.name for path in VIEWS_DIR.glob("*.qml")}
    assert on_disk == set(VIEWS), f"views/ and VIEWS disagree: {on_disk ^ set(VIEWS)}"


# --------------------------------------------------------------------------- #
# state-driven: the status surface reflects each state
# --------------------------------------------------------------------------- #
STATE_CASES = [
    (UiSnapshot(running=False), "paused", "En pause"),
    (UiSnapshot(running=True), "clear", "Dégagé"),
    (UiSnapshot(running=True, is_masked=True), "protected", "Protégé"),
    (UiSnapshot(running=True, error_kind=CameraError.NO_CAMERA), "error", "Erreur caméra"),
]


@pytest.mark.parametrize(("snapshot", "role", "headline"), STATE_CASES)
def test_status_view_reflects_state(qml, snapshot, role, headline) -> None:
    h = qml(snapshot)
    root = h.load("StatusView.qml")
    pill = _find(root, "statusPill")
    assert pill.property("role") == role
    assert pill.property("label") == headline
    # The primary action label matches the view-model for this state.
    button = _find(root, "primaryAction")
    assert button.property("text") == h.status.property("primary_action_label")


def test_status_view_veil_engages_only_when_protected(qml) -> None:
    h1 = qml(UiSnapshot(running=True, is_masked=True))
    assert _find(h1.load("StatusView.qml"), "veil").property("engaged") is True
    h2 = qml(UiSnapshot(running=True))
    assert _find(h2.load("StatusView.qml"), "veil").property("engaged") is False


def test_status_view_camera_badge_tracks_activity(qml) -> None:
    h = qml(UiSnapshot(running=True, camera_active=True))
    badge = _find(h.load("StatusView.qml"), "cameraBadge")
    assert badge.property("active") is True


# --------------------------------------------------------------------------- #
# main window: options are on the interface, camera preview is opt-in
# --------------------------------------------------------------------------- #
def test_main_view_exposes_all_options(qml) -> None:
    h = qml()
    root = h.load("MainView.qml")
    for name in ("primaryAction", "previewToggle", "settingsButton", "aboutButton", "quitButton"):
        assert _find(root, name) is not None


def test_main_view_camera_hidden_by_default(qml) -> None:
    h = qml()
    cam = _find(h.load("MainView.qml"), "cameraView")
    assert cam.property("visible") is False  # preview is opt-in


def test_main_view_preview_toggle_reveals_camera(qml) -> None:
    h = qml()
    root = h.load("MainView.qml")
    cam = _find(root, "cameraView")
    assert cam.property("visible") is False
    _find(root, "previewToggle").clicked.emit()
    assert h.controller.property("preview_enabled") is True
    assert cam.property("visible") is True  # now shown


def test_main_view_buttons_open_settings_and_about(qml) -> None:
    h = qml()
    root = h.load("MainView.qml")
    _find(root, "settingsButton").clicked.emit()
    _find(root, "aboutButton").clicked.emit()
    assert h.controller.settings_opened == 1
    assert h.controller.about_opened == 1


def test_camera_view_shows_off_message_when_unavailable(qml) -> None:
    h = qml()
    img = _find(h.load("CameraView.qml"), "cameraImage")
    assert img.property("visible") is False  # nothing to show until a frame arrives


# --------------------------------------------------------------------------- #
# interaction: the primary button drives the view-model/controller
# --------------------------------------------------------------------------- #
def test_primary_button_click_resumes(qml) -> None:
    h = qml(UiSnapshot(running=False))
    root = h.load("StatusView.qml")
    button = _find(root, "primaryAction")
    button.clicked.emit()  # equivalent to a click / Return / Space on the button
    assert h.controller.property("running") is True


def test_onboarding_next_advances(qml) -> None:
    h = qml()
    root = h.load("OnboardingView.qml")
    _find(root, "nextButton").clicked.emit()
    assert h.onboarding.property("index") == 1


def test_onboarding_allow_then_finish_enables(qml) -> None:
    h = qml()
    root = h.load("OnboardingView.qml")
    _find(root, "nextButton").clicked.emit()  # -> consent step
    _find(root, "allowButton").clicked.emit()  # consent + advance to last
    _find(root, "finishButton").clicked.emit()
    assert h.controller.onboarding_done == 1
    assert h.controller.property("running") is True


# --------------------------------------------------------------------------- #
# accessibility: keyboard-focusable controls with accessible names
# --------------------------------------------------------------------------- #
def test_primary_button_is_keyboard_focusable_and_named(qml) -> None:
    h = qml()
    button = _find(h.load("StatusView.qml"), "primaryAction")
    assert button.property("activeFocusOnTab") is True
    assert _accessible_name(button), "primary action needs an accessible name"


def test_onboarding_controls_have_accessible_names(qml) -> None:
    h = qml()
    root = h.load("OnboardingView.qml")
    # On the first step the Next button is present and labelled.
    nxt = _find(root, "nextButton")
    assert nxt.property("activeFocusOnTab") is True
    assert _accessible_name(nxt)


def test_settings_controls_are_focusable_and_named(qml) -> None:
    h = qml()
    root = h.load("SettingsView.qml")
    for name in ("sensitivitySlider", "triggerSlider", "releaseSlider", "opacitySlider"):
        control = _find(root, name)
        assert control.property("activeFocusOnTab") is True, f"{name} not tab-focusable"
        assert _accessible_name(control), f"{name} missing accessible name"


def test_settings_slider_edits_forward_to_controller(qml) -> None:
    h = qml()
    root = h.load("SettingsView.qml")
    slider = _find(root, "sensitivitySlider")
    slider.setProperty("value", 30)
    slider.moved.emit()
    assert h.controller.property("sensitivity_deg") == pytest.approx(30.0)


# --------------------------------------------------------------------------- #
# reduced motion is honoured at the theme level the views bind to
# --------------------------------------------------------------------------- #
def test_reduced_motion_shortens_view_durations(qml) -> None:
    h = qml()
    h.load("StatusView.qml")
    h.theme.setProperty("reduced_motion", True)
    assert h.theme.duration("veil_settle") < 420


# --------------------------------------------------------------------------- #
# updates: the install button exists only for a release we can verify (AM-3/AM-4)
# --------------------------------------------------------------------------- #
class _FakeInfo:
    def __init__(self, sha: str | None) -> None:
        self.version = "v9.9.9"
        self.notes = "notes"
        self.html_url = "https://github.com/x/releases/v9.9.9"
        self.installer_url = "https://github.com/x/NexShieldVeil-Setup.exe"
        self.installer_sha256 = sha

    @property
    def can_auto_install(self) -> bool:
        return bool(self.installer_url) and bool(self.installer_sha256)


def test_update_view_shows_the_current_version_when_idle(qml) -> None:
    h = qml()
    root = h.load("UpdateView.qml")
    assert _find(root, "updateHeadline").property("text") == h.updates.property("headline")
    assert _find(root, "checkButton").property("enabled") is True
    assert _find(root, "installButton").property("visible") is False


def test_update_view_offers_the_install_for_a_verifiable_release(qml) -> None:
    h = qml()
    root = h.load("UpdateView.qml")
    h.updates.report_result(_FakeInfo("a" * 64))
    assert _find(root, "installButton").property("visible") is True
    assert _find(root, "pageButton").property("visible") is True
    assert "v9.9.9" in _find(root, "updateHeadline").property("text")


def test_update_view_hides_the_install_when_nothing_can_be_verified(qml) -> None:
    h = qml()
    root = h.load("UpdateView.qml")
    h.updates.report_result(_FakeInfo(None))
    # No verifiable installer: no one-click install, but the release page stays
    # reachable and the reason is spelled out rather than silently hidden.
    assert _find(root, "installButton").property("visible") is False
    assert _find(root, "pageButton").property("visible") is True
    assert _find(root, "updateDetail").property("text").strip()


def test_update_view_disables_actions_while_busy(qml) -> None:
    h = qml()
    root = h.load("UpdateView.qml")
    h.updates.check()  # -> checking (the shell would start the thread)
    assert _find(root, "checkButton").property("enabled") is False


def test_update_view_check_button_triggers_the_intent(qml, record) -> None:
    h = qml()
    root = h.load("UpdateView.qml")
    requests = record(h.updates.check_requested)
    _find(root, "checkButton").clicked.emit()
    assert requests == [()]


def test_settings_exposes_the_walk_away_lock(qml) -> None:
    h = qml()
    root = h.load("SettingsView.qml")
    switch = _find(root, "absenceLockSwitch")
    assert switch.property("checked") is False  # opt-in
    assert _accessible_name(switch)
    # The delay slider only appears once the lock is on.
    assert _find(root, "absenceLockSlider").property("visible") is False
    h.settings.set_absence_lock_enabled(True)
    assert _find(root, "absenceLockSlider").property("visible") is True
