"""GitHub release update checker — the ONLY network-touching module in the project.

QUARANTINED (privacy boundary). This module talks to GitHub to:
  1. read the latest release metadata (version + notes + installer asset URL), and
  2. download the installer **only on explicit user action**.

It is intentionally isolated from the rest of the app: it imports nothing from the
capture/vision layers, so it can never see a camera frame or any biometric data. No
user data is ever transmitted — the requests are anonymous, read-only HTTPS GETs.

This file is allow-listed in the static privacy guard (tests/privacy/
test_source_hygiene.py); every other source file is still forbidden from touching the
network. See docs/PRIVACY.md.
"""

from __future__ import annotations

import json
import ssl
import urllib.request
from dataclasses import dataclass

from privacy_guard import __version__
from privacy_guard.update.version import is_newer

_REPO = "latifnjimoluh/nexshieldveil"
_LATEST_API = f"https://api.github.com/repos/{_REPO}/releases/latest"
_RELEASES_PAGE = f"https://github.com/{_REPO}/releases/latest"
_HEADERS = {
    "User-Agent": "NexShieldVeil-Updater",
    "Accept": "application/vnd.github+json",
}


@dataclass(frozen=True)
class UpdateInfo:
    """A newer release than the running version."""

    version: str
    notes: str
    html_url: str
    installer_url: str | None


def _fetch_latest(timeout: float) -> dict:
    request = urllib.request.Request(_LATEST_API, headers=_HEADERS)
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:  # nosec B310
        return json.loads(response.read().decode("utf-8"))


def check_for_update(current: str = __version__, timeout: float = 6.0) -> UpdateInfo | None:
    """Return info about a newer release, or ``None`` if up to date / on any failure.

    Never raises: a checker that throws on a flaky network would be worse than useless.
    """
    try:
        data = _fetch_latest(timeout)
    except Exception:  # network/JSON failures must never crash the app
        return None
    tag = str(data.get("tag_name") or "")
    if not tag or not is_newer(tag, current):
        return None
    installer_url: str | None = None
    for asset in data.get("assets") or []:
        name = str(asset.get("name") or "").lower()
        if name.endswith(".exe") and "setup" in name:
            installer_url = asset.get("browser_download_url")
            break
    return UpdateInfo(
        version=tag,
        notes=str(data.get("body") or ""),
        html_url=str(data.get("html_url") or _RELEASES_PAGE),
        installer_url=installer_url,
    )


def download_installer(
    url: str,
    dest_path: str,
    timeout: float = 120.0,
    progress: object = None,
) -> str:
    """Download an installer to ``dest_path``, reporting fractional progress.

    Returns the destination path. ``progress`` (if given) is called with a float in
    [0, 1]. This writes an executable installer to disk — never an image or any
    biometric data.
    """
    request = urllib.request.Request(url, headers={"User-Agent": _HEADERS["User-Agent"]})
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:  # nosec B310
        total = int(response.headers.get("Content-Length") or 0)
        read = 0
        with open(dest_path, "wb") as handle:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                handle.write(chunk)
                read += len(chunk)
                if callable(progress) and total:
                    progress(read / total)
    return dest_path


def launch_installer(path: str) -> None:
    """Start the downloaded installer (the app should quit right after)."""
    import subprocess

    # Launches our own freshly-downloaded installer (no shell, fixed argv).
    subprocess.Popen([path])  # nosec B603
