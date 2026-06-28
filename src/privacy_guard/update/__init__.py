"""Optional self-update support.

The decision logic (:mod:`version`) is pure and headlessly tested. The network code
lives entirely in :mod:`checker`, which is the project's single, quarantined,
documented exception to the "no outbound network" rule — it only fetches release
metadata and (on user action) the installer, and never touches camera/biometric data.
"""

from __future__ import annotations

from privacy_guard.update.checker import (
    UpdateInfo,
    check_for_update,
    download_installer,
    launch_installer,
)
from privacy_guard.update.version import is_newer, parse_version

__all__ = [
    "UpdateInfo",
    "check_for_update",
    "download_installer",
    "is_newer",
    "launch_installer",
    "parse_version",
]
