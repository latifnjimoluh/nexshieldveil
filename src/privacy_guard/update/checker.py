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

**Integrity (AM-4).** This is the one path that puts executable code on the user's
machine, so TLS alone is not enough — TLS authenticates the transport, not the
artefact. Three rules, all enforced here:

1. every URL fetched must live on a GitHub host, **redirects included** (a release
   payload names its own asset URL; an unconstrained one would be a redirect away
   from GitHub);
2. an installer is only ever handed to the caller once its SHA-256 matches the
   ``SHA256SUMS`` published alongside it in the same release. No published digest
   means no automatic install — the user is sent to the release page instead;
3. the download lands in a private, user-only directory created for that purpose,
   not in the shared temporary directory where another local process could swap
   the file between verification and launch.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import ssl
import tempfile
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

from privacy_guard import __version__
from privacy_guard.update.version import is_newer

_REPO = "latifnjimoluh/nexshieldveil"
_LATEST_API = f"https://api.github.com/repos/{_REPO}/releases/latest"
_RELEASES_PAGE = f"https://github.com/{_REPO}/releases/latest"
_HEADERS = {
    "User-Agent": "NexShieldVeil-Updater",
    "Accept": "application/vnd.github+json",
}

# Hosts the updater may talk to. Release assets redirect to GitHub's asset CDN,
# whose exact hostname has changed over time (objects. -> release-assets.), hence
# the suffix rule for that domain rather than a brittle exact list.
_ALLOWED_HOSTS = frozenset({"github.com", "api.github.com"})
_ALLOWED_HOST_SUFFIX = ".githubusercontent.com"

# A published checksum file is small; refuse to slurp anything unreasonable.
_MAX_CHECKSUM_BYTES = 64 * 1024
_CHECKSUM_ASSET_NAMES = frozenset({"sha256sums", "sha256sums.txt", "checksums.txt"})
_SHA256_LINE = re.compile(r"^([0-9a-fA-F]{64})\s+\*?(\S+)$")


class UntrustedSourceError(Exception):
    """A URL outside the allowed GitHub hosts was about to be fetched."""


class IntegrityError(Exception):
    """A downloaded installer did not match its published SHA-256."""


@dataclass(frozen=True)
class UpdateInfo:
    """A newer release than the running version.

    ``installer_url`` is only set when the asset lives on a trusted host, and
    ``installer_sha256`` only when the release publishes a digest for it. A caller
    must treat "installer without digest" as *not installable automatically*.
    """

    version: str
    notes: str
    html_url: str
    installer_url: str | None
    installer_sha256: str | None = None

    @property
    def can_auto_install(self) -> bool:
        """Whether this update can be downloaded *and verified* without the user."""
        return bool(self.installer_url) and bool(self.installer_sha256)


# --------------------------------------------------------------------------- #
# pure helpers (no network; unit-tested)
# --------------------------------------------------------------------------- #
def is_trusted_asset_url(url: str) -> bool:
    """Whether ``url`` is an HTTPS URL on a GitHub host we accept.

    Rejects plain HTTP, credentials embedded in the authority, and any host that
    merely *ends with* a lookalike (``evil-github.com``, ``github.com.attacker.net``).
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return False
    host = (parsed.hostname or "").lower()
    return host in _ALLOWED_HOSTS or host.endswith(_ALLOWED_HOST_SUFFIX)


def select_installer_asset(assets: list[dict]) -> dict | None:
    """Pick the Windows setup executable among a release's assets."""
    for asset in assets:
        name = str(asset.get("name") or "").lower()
        if name.endswith(".exe") and "setup" in name:
            return asset
    return None


def select_checksums_asset(assets: list[dict]) -> dict | None:
    """Pick the published checksum file among a release's assets."""
    for asset in assets:
        name = str(asset.get("name") or "").lower()
        if name in _CHECKSUM_ASSET_NAMES or name.endswith(".sha256"):
            return asset
    return None


def parse_sha256sums(text: str, filename: str) -> str | None:
    """Return the digest recorded for ``filename`` in ``SHA256SUMS`` text.

    Accepts the standard ``sha256sum`` output (``<digest>  <name>``, with the
    binary-mode ``*`` prefix tolerated). Paths are compared on their basename, so
    a file recorded as ``dist/NexShieldVeil-Setup.exe`` still matches.
    """
    wanted = os.path.basename(filename).lower()
    for line in text.splitlines():
        match = _SHA256_LINE.match(line.strip())
        if match and os.path.basename(match.group(2)).lower() == wanted:
            return match.group(1).lower()
    return None


def installer_download_dir() -> str:
    """Create and return a private (user-only) directory for the download.

    ``mkdtemp`` creates the directory with ``0700`` and a random name, so no other
    local user can read it — or swap the installer between the digest check and
    the launch, which is exactly the window a shared temp path would open.
    """
    return tempfile.mkdtemp(prefix="nexshieldveil-update-")


# --------------------------------------------------------------------------- #
# network (quarantined)
# --------------------------------------------------------------------------- #
class _TrustedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuses any redirect that leaves the allowed GitHub hosts."""

    def redirect_request(  # urllib fixes this signature; we only inspect `newurl`
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: Mapping[str, str],
        newurl: str,
    ) -> urllib.request.Request | None:
        """Follow the redirect only if it stays on an allowed GitHub host."""
        if not is_trusted_asset_url(newurl):
            msg_text = f"refusing redirect to an untrusted host: {newurl}"
            raise UntrustedSourceError(msg_text)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener() -> urllib.request.OpenerDirector:
    context = ssl.create_default_context()
    return urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=context), _TrustedRedirectHandler()
    )


def _open(url: str, timeout: float, headers: dict[str, str] | None = None):  # noqa: ANN202
    """Open a trusted URL, enforcing the host allow-list before the first byte.

    Raises:
        UntrustedSourceError: If the URL (or a redirect) leaves the GitHub hosts.
    """
    if not is_trusted_asset_url(url):
        msg = f"refusing to fetch an untrusted URL: {url}"
        raise UntrustedSourceError(msg)
    request = urllib.request.Request(url, headers=headers or _HEADERS)
    return _opener().open(request, timeout=timeout)  # nosec B310 - scheme checked above


def _fetch_latest(timeout: float) -> dict:
    with _open(_LATEST_API, timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_expected_digest(assets: list[dict], installer_name: str, timeout: float) -> str | None:
    """Download and parse the release's checksum file, or ``None`` if unusable."""
    checksums = select_checksums_asset(assets)
    if checksums is None:
        return None
    url = str(checksums.get("browser_download_url") or "")
    if not is_trusted_asset_url(url):
        return None
    try:
        with _open(url, timeout, headers={"User-Agent": _HEADERS["User-Agent"]}) as response:
            text = response.read(_MAX_CHECKSUM_BYTES).decode("utf-8", errors="replace")
    except Exception:  # a missing/broken checksum file must not break the check
        return None
    return parse_sha256sums(text, installer_name)


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

    assets = list(data.get("assets") or [])
    installer_url: str | None = None
    digest: str | None = None
    asset = select_installer_asset(assets)
    if asset is not None:
        url = str(asset.get("browser_download_url") or "")
        if is_trusted_asset_url(url):
            installer_url = url
            try:
                digest = _fetch_expected_digest(assets, str(asset.get("name") or ""), timeout)
            except Exception:  # same rule as above: report the update, not a crash
                digest = None

    return UpdateInfo(
        version=tag,
        notes=str(data.get("body") or ""),
        html_url=str(data.get("html_url") or _RELEASES_PAGE),
        installer_url=installer_url,
        installer_sha256=digest,
    )


def download_installer(
    url: str,
    dest_path: str,
    expected_sha256: str,
    timeout: float = 120.0,
    progress: object = None,
) -> str:
    """Download an installer to ``dest_path`` and verify it against ``expected_sha256``.

    The digest is computed while streaming, so the file is never read twice. On any
    mismatch the partial file is deleted before raising: a binary that failed
    verification must not survive on disk where a user could double-click it.

    Args:
        url: Asset URL, which must be on a trusted GitHub host.
        dest_path: Where to write the installer.
        expected_sha256: The digest published with the release (64 hex chars).
        timeout: Per-read socket timeout in seconds.
        progress: Optional callable receiving a float in ``[0, 1]``.

    Returns:
        ``dest_path``.

    Raises:
        UntrustedSourceError: If the URL or a redirect leaves the GitHub hosts.
        IntegrityError: If ``expected_sha256`` is malformed, or the download does
            not match it.
    """
    expected = (expected_sha256 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        msg = "refusing to download an installer without a valid published SHA-256"
        raise IntegrityError(msg)

    digest = hashlib.sha256()
    with _open(url, timeout, headers={"User-Agent": _HEADERS["User-Agent"]}) as response:
        total = int(response.headers.get("Content-Length") or 0)
        read = 0
        with open(dest_path, "wb") as handle:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                handle.write(chunk)
                digest.update(chunk)
                read += len(chunk)
                if callable(progress) and total:
                    progress(read / total)

    actual = digest.hexdigest()
    if actual != expected:
        with contextlib.suppress(OSError):  # best effort; the mismatch is what matters
            os.unlink(dest_path)
        msg = f"installer checksum mismatch: expected {expected}, got {actual}"
        raise IntegrityError(msg)
    return dest_path


def launch_installer(path: str) -> None:
    """Start a **verified** installer (the app should quit right after).

    Only ever call this with a path returned by :func:`download_installer`, which
    is the function that proves the file matches its published digest.
    """
    import subprocess

    # Launches our own freshly-downloaded, checksum-verified installer
    # (no shell, fixed argv).
    subprocess.Popen([path])  # nosec B603
