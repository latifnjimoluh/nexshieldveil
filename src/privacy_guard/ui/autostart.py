"""Start at login, actually registered with the OS (AM-1).

The "Démarrer à la session" switch used to be a lie: the value travelled from the
settings window to ``QSettings`` and back on restart, but **nothing ever registered
anything with the operating system** — no registry value, no ``.desktop`` file, no
LaunchAgent, and no ``[Registry]`` section in the installer either. A user ticked
the box, rebooted, and believed they were protected while the app had never
started. For a privacy tool that is the worst class of defect: a protection the
interface claims and the machine does not provide.

Shape of this module: **planning is pure, applying is a thin adapter.**
:func:`plan_for` decides *what* should be written (which file or registry value,
with which content) from plain inputs — platform string, home directory, argv — so
the rules for all three operating systems are unit-tested headlessly, on any
machine. Only :func:`apply_plan`/:func:`plan_is_enabled` touch the system.

Privacy: this is the one module besides the updater that writes outside
``QSettings``. It writes a launcher entry — a path and a flag, never an image,
never anything about what the camera saw — and it is mechanically forbidden from
importing any camera, vision or network code
(``tests/privacy/test_source_hygiene.py``).
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from xml.sax.saxutils import escape

logger = logging.getLogger(__name__)

APP_NAME = "NexShieldVeil"
LAUNCH_AGENT_LABEL = "com.nexshieldveil.autostart"
_DESKTOP_FILE = "nexshieldveil.desktop"
# Module run for a source checkout: the QML shell, NOT `privacy_guard.ui`
# (which is the legacy Qt Widgets window).
_SHELL_MODULE = "privacy_guard.ui.shell"
_REGISTRY_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


class AutostartKind(Enum):
    """How this platform registers a login item."""

    REGISTRY = "registry"  # Windows: HKCU\...\CurrentVersion\Run
    DESKTOP_ENTRY = "desktop_entry"  # Linux/XDG: ~/.config/autostart/*.desktop
    LAUNCH_AGENT = "launch_agent"  # macOS: ~/Library/LaunchAgents/*.plist
    UNSUPPORTED = "unsupported"  # anything else: the UI must say so, not pretend


@dataclass(frozen=True)
class AutostartPlan:
    """What registering this app at login means on one platform.

    Attributes:
        kind: Which mechanism applies.
        target: Path of the file to write, or the registry value name.
        content: File content to write (empty for the registry, which stores a
            command line in :attr:`command` instead).
        command: The command line that will be launched.
    """

    kind: AutostartKind
    target: str
    content: str
    command: str

    @property
    def supported(self) -> bool:
        """Whether this platform has a mechanism we know how to use."""
        return self.kind is not AutostartKind.UNSUPPORTED


# --------------------------------------------------------------------------- #
# pure planning
# --------------------------------------------------------------------------- #
def autostart_argv(executable: str, frozen: bool) -> list[str]:
    """The argv that launches the app.

    A frozen build is its own executable; a source checkout needs the interpreter
    plus the QML shell module.
    """
    return [executable] if frozen else [executable, "-m", _SHELL_MODULE]


def quote_command(argv: list[str]) -> str:
    """Join argv into a command line, quoting the arguments that need it."""
    return " ".join(f'"{arg}"' if (" " in arg or '"' in arg) else arg for arg in argv)


def desktop_entry(command: str) -> str:
    """XDG autostart entry content for ``command``."""
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        "Comment=Bouclier anti regard indiscret\n"
        f"Exec={command}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def launch_agent_plist(argv: list[str]) -> str:
    """Return the macOS LaunchAgent plist content for ``argv``."""
    arguments = "\n".join(f"        <string>{escape(arg)}</string>" for arg in argv)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "    <key>Label</key>\n"
        f"    <string>{LAUNCH_AGENT_LABEL}</string>\n"
        "    <key>ProgramArguments</key>\n"
        "    <array>\n"
        f"{arguments}\n"
        "    </array>\n"
        "    <key>RunAtLoad</key>\n"
        "    <true/>\n"
        "</dict>\n"
        "</plist>\n"
    )


def plan_for(
    platform: str,
    home: Path,
    argv: list[str],
    config_home: str | None = None,
) -> AutostartPlan:
    """Decide what registering at login means, without touching anything.

    Args:
        platform: A ``sys.platform`` value (``win32``, ``darwin``, ``linux``…).
        home: The user's home directory.
        argv: The command to launch (see :func:`autostart_argv`).
        config_home: ``XDG_CONFIG_HOME`` when set (Linux only).

    Returns:
        The plan; :attr:`AutostartPlan.supported` is ``False`` on platforms we
        have no mechanism for — the caller must surface that rather than
        silently pretend the setting took effect.
    """
    command = quote_command(argv)
    if platform == "win32":
        return AutostartPlan(AutostartKind.REGISTRY, APP_NAME, "", command)
    if platform == "darwin":
        target = home / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
        return AutostartPlan(
            AutostartKind.LAUNCH_AGENT, str(target), launch_agent_plist(argv), command
        )
    if platform.startswith("linux") or platform.startswith("freebsd"):
        base = Path(config_home) if config_home else home / ".config"
        target = base / "autostart" / _DESKTOP_FILE
        return AutostartPlan(
            AutostartKind.DESKTOP_ENTRY, str(target), desktop_entry(command), command
        )
    return AutostartPlan(AutostartKind.UNSUPPORTED, "", "", command)


def current_plan() -> AutostartPlan:
    """The plan for the running interpreter and user."""
    argv = autostart_argv(sys.executable, bool(getattr(sys, "frozen", False)))
    return plan_for(sys.platform, Path.home(), argv, os.environ.get("XDG_CONFIG_HOME"))


# --------------------------------------------------------------------------- #
# applying (side effects; the file-based kinds are exercised in tmp_path)
# --------------------------------------------------------------------------- #
def plan_is_enabled(plan: AutostartPlan) -> bool:
    """Whether the login item described by ``plan`` currently exists.

    Reads the *system*, never a remembered preference: if the user removed the
    entry by hand, the checkbox must show it as off.
    """
    if plan.kind is AutostartKind.REGISTRY:
        return _registry_value() is not None
    if plan.kind is AutostartKind.UNSUPPORTED:
        return False
    return Path(plan.target).is_file()


def apply_plan(plan: AutostartPlan, enabled: bool) -> bool:
    """Create or remove the login item; return the state that actually resulted.

    Never raises: a locked-down or managed session may refuse the write, and the
    caller's job is then to show the truth (the box goes back to off), not to
    crash — nor to keep claiming a protection that is not there.
    """
    if not plan.supported:
        logger.warning("No autostart mechanism for this platform; setting has no effect.")
        return False
    try:
        if plan.kind is AutostartKind.REGISTRY:
            _apply_registry(plan, enabled)
        else:
            _apply_file(plan, enabled)
    except OSError as exc:
        logger.warning("Could not %s autostart: %s", "enable" if enabled else "disable", exc)
    return plan_is_enabled(plan)


def _apply_file(plan: AutostartPlan, enabled: bool) -> None:
    target = Path(plan.target)
    if not enabled:
        target.unlink(missing_ok=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    # Rewritten every time on purpose: the executable path changes when the user
    # moves or reinstalls the app, and a stale entry would launch nothing.
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(plan.content)


# The two Windows adapters below sit inside `sys.platform == "win32"` blocks so
# type-checking them is skipped on other platforms (winreg is Windows-only in
# typeshed) and still enforced by the Windows leg of the CI matrix.
def _registry_value() -> str | None:  # pragma: no cover - Windows-only
    """Read our value under the Run key, or ``None`` if absent."""
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REGISTRY_RUN_KEY) as key:
                value, _kind = winreg.QueryValueEx(key, APP_NAME)
                return str(value)
        except OSError:
            return None
    return None


def _apply_registry(plan: AutostartPlan, enabled: bool) -> None:  # pragma: no cover - Windows-only
    if sys.platform == "win32":
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REGISTRY_RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, plan.command)
            else:
                # Already absent: the requested state is the current one.
                with contextlib.suppress(FileNotFoundError):
                    winreg.DeleteValue(key, APP_NAME)


# --------------------------------------------------------------------------- #
# façade used by the shell
# --------------------------------------------------------------------------- #
def is_enabled() -> bool:
    """Whether this app is currently registered to start at login."""
    return plan_is_enabled(current_plan())


def set_enabled(enabled: bool) -> bool:
    """Register/unregister at login; return the state that actually resulted."""
    return apply_plan(current_plan(), enabled)


def is_supported() -> bool:
    """Whether this platform has an autostart mechanism we implement."""
    return current_plan().supported
