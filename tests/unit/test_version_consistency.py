"""One version number, three places (AM-6).

The package, the distribution metadata and the Windows installer each carry the
version independently. A drift there ships an installer labelled with the wrong
version — and the updater compares exactly that string to decide whether a newer
release exists, so a wrong label means users are told to "update" to what they
already run, or never told at all.

Checked on every push, which is earlier and cheaper than at release time.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from privacy_guard import __version__

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def test_the_package_version_looks_like_a_version() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__), __version__


def test_pyproject_matches_the_package() -> None:
    data = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == __version__


def test_the_windows_installer_matches_the_package() -> None:
    iss = (_ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
    match = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', iss)
    assert match is not None, "installer.iss no longer defines MyAppVersion"
    assert match.group(1) == __version__


def test_the_installer_output_name_is_the_one_the_updater_looks_for() -> None:
    # `select_installer_asset` picks an asset whose name ends in .exe and contains
    # "setup"; `parse_sha256sums` then matches it by basename. If the installer
    # were renamed, the update path would silently degrade to "manual only".
    from privacy_guard.update import parse_sha256sums, select_installer_asset

    iss = (_ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
    match = re.search(r"OutputBaseFilename=(.+)", iss)
    assert match is not None
    name = match.group(1).strip().replace("{#MyAppName}", "NexShieldVeil") + ".exe"

    assert select_installer_asset([{"name": name}]) is not None
    assert parse_sha256sums(f"{'a' * 64}  {name}\n", name) == "a" * 64
