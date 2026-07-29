"""Update surface of the QML app (AM-3): state machine, copy, and intents.

No network and no thread: the view-model only emits intents and consumes
outcomes, which is exactly what makes the whole update surface testable here.
"""

from __future__ import annotations

import pytest

from privacy_guard.ui.state import UpdateState, update_headline_key, update_is_busy
from privacy_guard.ui.translator import Translator
from privacy_guard.ui.viewmodels import UpdatesViewModel

pytestmark = pytest.mark.unit


class _Info:
    """Stand-in for update.UpdateInfo (kept structural, like the real signal payload)."""

    def __init__(
        self,
        version: str = "v0.4.0",
        installer_url: str | None = "https://github.com/x/NexShieldVeil-Setup.exe",
        installer_sha256: str | None = "a" * 64,
        notes: str = "notes",
        html_url: str = "https://github.com/x/releases/v0.4.0",
    ) -> None:
        self.version = version
        self.installer_url = installer_url
        self.installer_sha256 = installer_sha256
        self.notes = notes
        self.html_url = html_url

    @property
    def can_auto_install(self) -> bool:
        return bool(self.installer_url) and bool(self.installer_sha256)


@pytest.fixture
def vm(qapp) -> UpdatesViewModel:
    return UpdatesViewModel(Translator("fr"))


# --------------------------------------------------------------------------- #
# pure state helpers
# --------------------------------------------------------------------------- #
def test_every_state_has_a_headline_key() -> None:
    for state in UpdateState:
        assert update_headline_key(state).startswith("update.")


@pytest.mark.parametrize(
    ("state", "busy"),
    [
        (UpdateState.IDLE, False),
        (UpdateState.CHECKING, True),
        (UpdateState.DOWNLOADING, True),
        (UpdateState.AVAILABLE, False),
        (UpdateState.UP_TO_DATE, False),
        (UpdateState.MANUAL_ONLY, False),
        (UpdateState.FAILED, False),
    ],
)
def test_busy_states(state: UpdateState, busy: bool) -> None:
    assert update_is_busy(state) is busy


# --------------------------------------------------------------------------- #
# check flow
# --------------------------------------------------------------------------- #
def test_starts_idle(vm: UpdatesViewModel) -> None:
    assert vm.property("state_key") == "idle"
    assert vm.property("busy") is False
    assert vm.property("can_install") is False


def test_check_emits_the_intent_and_goes_busy(vm: UpdatesViewModel, record) -> None:
    requests = record(vm.check_requested)
    vm.check()
    assert requests == [()]
    assert vm.property("state_key") == "checking"
    assert vm.property("busy") is True


def test_a_second_check_while_running_is_ignored(vm: UpdatesViewModel, record) -> None:
    requests = record(vm.check_requested)
    vm.check()
    vm.check()
    assert len(requests) == 1


def test_no_update_reports_up_to_date(vm: UpdatesViewModel) -> None:
    vm.check()
    vm.report_result(None)
    assert vm.property("state_key") == "up_to_date"
    assert vm.property("can_install") is False
    assert vm.property("can_open_page") is False


def test_a_verifiable_update_is_installable(vm: UpdatesViewModel) -> None:
    vm.check()
    vm.report_result(_Info())
    assert vm.property("state_key") == "available"
    assert vm.property("can_install") is True
    assert vm.property("can_open_page") is True
    assert "v0.4.0" in vm.property("headline")


def test_an_unverifiable_update_is_not_installable(vm: UpdatesViewModel) -> None:
    # AM-4's rule surfaced in the UI: no published digest, no one-click install.
    vm.check()
    vm.report_result(_Info(installer_sha256=None))
    assert vm.property("state_key") == "manual_only"
    assert vm.property("can_install") is False
    # ...but the user is not left stranded: the release page is still offered.
    assert vm.property("can_open_page") is True


def test_an_update_without_any_installer_is_manual_only(vm: UpdatesViewModel) -> None:
    vm.check()
    vm.report_result(_Info(installer_url=None, installer_sha256=None))
    assert vm.property("state_key") == "manual_only"
    assert vm.property("can_install") is False


def test_a_failed_check_keeps_the_reason_visible(vm: UpdatesViewModel) -> None:
    vm.check()
    vm.report_failed("connexion refusée")
    assert vm.property("state_key") == "failed"
    assert "connexion refusée" in vm.property("detail")


# --------------------------------------------------------------------------- #
# install flow
# --------------------------------------------------------------------------- #
def test_install_passes_the_url_and_digest_to_the_shell(vm: UpdatesViewModel, record) -> None:
    installs = record(vm.install_requested)
    vm.check()
    vm.report_result(_Info())
    vm.install()
    assert installs == [("https://github.com/x/NexShieldVeil-Setup.exe", "a" * 64)]
    assert vm.property("state_key") == "downloading"


def test_install_is_refused_without_a_verifiable_update(vm: UpdatesViewModel, record) -> None:
    installs = record(vm.install_requested)
    vm.check()
    vm.report_result(_Info(installer_sha256=None))
    vm.install()
    assert installs == []
    assert vm.property("state_key") == "manual_only"


def test_install_is_refused_before_any_check(vm: UpdatesViewModel, record) -> None:
    installs = record(vm.install_requested)
    vm.install()
    assert installs == []


def test_progress_is_clamped(vm: UpdatesViewModel) -> None:
    vm.report_progress(-1.0)
    assert vm.property("progress") == 0.0
    vm.report_progress(2.0)
    assert vm.property("progress") == 1.0
    vm.report_progress(0.42)
    assert vm.property("progress") == pytest.approx(0.42)


def test_a_verified_download_asks_the_shell_to_launch_it(vm: UpdatesViewModel, record) -> None:
    launches = record(vm.launch_requested)
    vm.check()
    vm.report_result(_Info())
    vm.install()
    vm.report_downloaded("/tmp/private/NexShieldVeil-Setup.exe")
    assert launches == [("/tmp/private/NexShieldVeil-Setup.exe",)]


def test_a_failed_download_surfaces_as_a_failure(vm: UpdatesViewModel, record) -> None:
    launches = record(vm.launch_requested)
    vm.check()
    vm.report_result(_Info())
    vm.install()
    vm.report_failed("installer checksum mismatch")
    assert launches == []
    assert vm.property("state_key") == "failed"
    assert "checksum" in vm.property("detail")


# --------------------------------------------------------------------------- #
# release page + preferences + i18n
# --------------------------------------------------------------------------- #
def test_open_release_page_emits_the_url(vm: UpdatesViewModel, record) -> None:
    pages = record(vm.page_requested)
    vm.check()
    vm.report_result(_Info())
    vm.open_release_page()
    assert pages == [("https://github.com/x/releases/v0.4.0",)]


def test_open_release_page_is_a_noop_without_one(vm: UpdatesViewModel, record) -> None:
    pages = record(vm.page_requested)
    vm.open_release_page()
    assert pages == []


def test_auto_check_toggles_and_notifies(vm: UpdatesViewModel, record) -> None:
    changes = record(vm.changed)
    assert vm.property("auto_check") is True
    vm.set_auto_check(False)
    assert vm.property("auto_check") is False
    assert len(changes) == 1
    vm.set_auto_check(False)  # no-op: no spurious notification
    assert len(changes) == 1


def test_copy_follows_the_language(qapp) -> None:
    translator = Translator("fr")
    vm = UpdatesViewModel(translator)
    vm.check()
    vm.report_result(None)
    french = vm.property("headline")
    translator.language = "en"
    assert vm.property("headline") != french
    assert vm.property("check_label") == "Check now"


def test_auto_check_change_is_signalled_once_for_the_shell(vm: UpdatesViewModel, record) -> None:
    # The shell persists on this signal, so it must fire on a real decision only —
    # never on the repaints that every check/progress update triggers.
    toggles = record(vm.auto_check_changed)
    vm.set_auto_check(False)
    vm.set_auto_check(False)
    vm.check()
    vm.report_progress(0.5)
    assert toggles == [(False,)]
