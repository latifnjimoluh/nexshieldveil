"""Start at login (AM-1): planning rules for all three OSes, then applying.

The planning half is pure, so Windows/macOS/Linux rules are all checked here on
whatever machine runs the suite. The applying half is exercised for the two
file-based mechanisms inside ``tmp_path``; the Windows registry adapter needs a
real registry and is verified manually.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from privacy_guard.ui.autostart import (
    APP_NAME,
    LAUNCH_AGENT_LABEL,
    AutostartKind,
    apply_plan,
    autostart_argv,
    current_plan,
    desktop_entry,
    launch_agent_plist,
    plan_for,
    plan_is_enabled,
    quote_command,
)

pytestmark = pytest.mark.unit

_HOME = Path("/home/user")


# --------------------------------------------------------------------------- #
# the command to launch
# --------------------------------------------------------------------------- #
def test_a_frozen_build_launches_itself() -> None:
    assert autostart_argv(r"C:\Program Files\NexShieldVeil\NexShieldVeil.exe", frozen=True) == [
        r"C:\Program Files\NexShieldVeil\NexShieldVeil.exe"
    ]


def test_a_source_checkout_launches_the_qml_shell() -> None:
    # Not `-m privacy_guard.ui`: that entry point is the LEGACY widgets window.
    assert autostart_argv("/usr/bin/python3", frozen=False) == [
        "/usr/bin/python3",
        "-m",
        "privacy_guard.ui.shell",
    ]


def test_paths_with_spaces_are_quoted() -> None:
    quoted = quote_command([r"C:\Program Files\NexShieldVeil\NexShieldVeil.exe"])
    assert quoted == r'"C:\Program Files\NexShieldVeil\NexShieldVeil.exe"'


def test_plain_paths_are_left_alone() -> None:
    assert quote_command(["/usr/bin/python3", "-m", "privacy_guard.ui.shell"]) == (
        "/usr/bin/python3 -m privacy_guard.ui.shell"
    )


# --------------------------------------------------------------------------- #
# per-platform plans
# --------------------------------------------------------------------------- #
def test_windows_plan_targets_the_run_key() -> None:
    plan = plan_for("win32", _HOME, [r"C:\App\NexShieldVeil.exe"])
    assert plan.kind is AutostartKind.REGISTRY
    assert plan.target == APP_NAME
    assert plan.command == r"C:\App\NexShieldVeil.exe"
    assert plan.supported is True


def test_macos_plan_targets_a_launch_agent() -> None:
    plan = plan_for("darwin", _HOME, ["/usr/bin/python3", "-m", "privacy_guard.ui.shell"])
    assert plan.kind is AutostartKind.LAUNCH_AGENT
    assert plan.target == str(_HOME / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist")
    assert "<key>RunAtLoad</key>" in plan.content
    assert "<string>privacy_guard.ui.shell</string>" in plan.content


def test_linux_plan_targets_the_xdg_autostart_dir() -> None:
    plan = plan_for("linux", _HOME, ["/usr/bin/python3", "-m", "privacy_guard.ui.shell"])
    assert plan.kind is AutostartKind.DESKTOP_ENTRY
    assert plan.target == str(_HOME / ".config" / "autostart" / "nexshieldveil.desktop")
    assert "Exec=/usr/bin/python3 -m privacy_guard.ui.shell" in plan.content


def test_linux_plan_honours_xdg_config_home() -> None:
    plan = plan_for("linux", _HOME, ["/usr/bin/python3"], config_home="/custom/cfg")
    assert plan.target == str(Path("/custom/cfg") / "autostart" / "nexshieldveil.desktop")


def test_an_unknown_platform_is_reported_as_unsupported() -> None:
    # The UI must be able to say "not available here" instead of pretending.
    plan = plan_for("sunos5", _HOME, ["/usr/bin/python3"])
    assert plan.kind is AutostartKind.UNSUPPORTED
    assert plan.supported is False


def test_current_plan_describes_this_machine() -> None:
    plan = current_plan()
    assert plan.command  # always knows what it would launch
    assert isinstance(plan.kind, AutostartKind)


# --------------------------------------------------------------------------- #
# generated content
# --------------------------------------------------------------------------- #
def test_desktop_entry_is_a_valid_autostart_entry() -> None:
    content = desktop_entry("/usr/bin/python3 -m privacy_guard.ui.shell")
    assert content.startswith("[Desktop Entry]\n")
    assert "Type=Application" in content
    assert f"Name={APP_NAME}" in content
    assert "X-GNOME-Autostart-enabled=true" in content


def test_launch_agent_plist_escapes_its_arguments() -> None:
    # An unescaped '&' or '<' in a path would produce an invalid plist that
    # launchd silently ignores — i.e. autostart that fails quietly again.
    content = launch_agent_plist(["/Applications/Rock & Roll/NexShieldVeil"])
    assert "&amp;" in content
    assert "Rock & Roll" not in content


def test_launch_agent_plist_lists_every_argument() -> None:
    content = launch_agent_plist(["/usr/bin/python3", "-m", "privacy_guard.ui.shell"])
    for arg in ("/usr/bin/python3", "-m", "privacy_guard.ui.shell"):
        assert f"<string>{arg}</string>" in content


# --------------------------------------------------------------------------- #
# applying: the file-based mechanisms, in a temporary home
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_enabling_creates_the_login_item(tmp_path: Path, platform: str) -> None:
    plan = plan_for(platform, tmp_path, ["/usr/bin/python3", "-m", "privacy_guard.ui.shell"])
    assert plan_is_enabled(plan) is False
    assert apply_plan(plan, True) is True
    target = Path(plan.target)
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == plan.content
    assert plan_is_enabled(plan) is True


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_disabling_removes_the_login_item(tmp_path: Path, platform: str) -> None:
    plan = plan_for(platform, tmp_path, ["/usr/bin/python3"])
    apply_plan(plan, True)
    assert apply_plan(plan, False) is False
    assert not Path(plan.target).exists()


def test_disabling_when_absent_is_a_noop(tmp_path: Path) -> None:
    plan = plan_for("linux", tmp_path, ["/usr/bin/python3"])
    assert apply_plan(plan, False) is False


def test_enabling_twice_is_idempotent(tmp_path: Path) -> None:
    plan = plan_for("linux", tmp_path, ["/usr/bin/python3"])
    apply_plan(plan, True)
    apply_plan(plan, True)
    assert Path(plan.target).read_text(encoding="utf-8") == plan.content


def test_enabling_rewrites_a_stale_entry(tmp_path: Path) -> None:
    # The executable path changes when the app is moved or reinstalled; a stale
    # entry would launch nothing, which is the failure mode AM-1 is about.
    old = plan_for("linux", tmp_path, ["/old/path/python3"])
    apply_plan(old, True)
    new = plan_for("linux", tmp_path, ["/new/path/python3"])
    apply_plan(new, True)
    assert "/new/path/python3" in Path(new.target).read_text(encoding="utf-8")
    assert "/old/path/python3" not in Path(new.target).read_text(encoding="utf-8")


def test_an_unsupported_platform_never_claims_success() -> None:
    plan = plan_for("sunos5", _HOME, ["/usr/bin/python3"])
    assert apply_plan(plan, True) is False
    assert plan_is_enabled(plan) is False


def test_a_refused_write_reports_the_real_state(tmp_path: Path) -> None:
    # A read-only (or managed) location must not raise, and must not claim the
    # login item exists: the caller puts the switch back to what is true.
    unwritable = tmp_path / "blocked"
    unwritable.write_text("not a directory", encoding="utf-8")
    plan = plan_for("linux", unwritable, ["/usr/bin/python3"])
    assert apply_plan(plan, True) is False
    assert plan_is_enabled(plan) is False
