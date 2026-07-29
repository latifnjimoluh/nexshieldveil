"""Update-channel integrity (AM-4): host allow-list, digest parsing, verification.

No network: the pure rules are tested directly, and the download path is exercised
against a stubbed opener. This is the one code path that puts an executable on the
user's machine, so its guards deserve real tests rather than trust in TLS.
"""

from __future__ import annotations

import hashlib
import io
import os
import stat

import pytest

from privacy_guard.update import checker
from privacy_guard.update.checker import (
    IntegrityError,
    UntrustedSourceError,
    UpdateInfo,
    download_installer,
    installer_download_dir,
    is_trusted_asset_url,
    parse_sha256sums,
    select_checksums_asset,
    select_installer_asset,
)

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# host allow-list
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/latifnjimoluh/nexshieldveil/releases/download/v1/NexShieldVeil-Setup.exe",
        "https://api.github.com/repos/latifnjimoluh/nexshieldveil/releases/latest",
        "https://objects.githubusercontent.com/some/asset",
        "https://release-assets.githubusercontent.com/other/asset",
    ],
)
def test_github_urls_are_trusted(url: str) -> None:
    assert is_trusted_asset_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/asset.exe",  # plaintext
        "https://evil.com/asset.exe",
        "https://evil-github.com/asset.exe",  # lookalike prefix
        "https://github.com.attacker.net/asset.exe",  # lookalike suffix
        "https://githubusercontent.com.evil.net/asset",  # suffix must be a real label
        "https://user:pass@github.com/asset.exe",  # credentials in the authority
        "ftp://github.com/asset.exe",
        "",
        "not a url",
    ],
)
def test_non_github_urls_are_rejected(url: str) -> None:
    assert is_trusted_asset_url(url) is False


def test_download_refuses_an_untrusted_url_before_fetching(tmp_path) -> None:
    digest = hashlib.sha256(b"x").hexdigest()
    with pytest.raises(UntrustedSourceError):
        download_installer("https://evil.com/setup.exe", str(tmp_path / "s.exe"), digest)
    assert not (tmp_path / "s.exe").exists()


def test_redirect_handler_rejects_a_hop_off_github() -> None:
    handler = checker._TrustedRedirectHandler()
    with pytest.raises(UntrustedSourceError):
        handler.redirect_request(None, None, 302, "Found", {}, "https://evil.com/setup.exe")


# --------------------------------------------------------------------------- #
# asset selection + checksum parsing
# --------------------------------------------------------------------------- #
def test_selects_the_setup_executable() -> None:
    assets = [
        {"name": "source.zip"},
        {"name": "NexShieldVeil-Setup.exe"},
        {"name": "other.exe"},
    ]
    picked = select_installer_asset(assets)
    assert picked is not None
    assert picked["name"] == "NexShieldVeil-Setup.exe"


def test_no_setup_executable_yields_none() -> None:
    assert select_installer_asset([{"name": "source.zip"}]) is None


@pytest.mark.parametrize("name", ["SHA256SUMS", "sha256sums.txt", "checksums.txt", "setup.sha256"])
def test_selects_the_checksums_asset(name: str) -> None:
    picked = select_checksums_asset([{"name": "NexShieldVeil-Setup.exe"}, {"name": name}])
    assert picked is not None
    assert picked["name"] == name


def test_no_checksums_asset_yields_none() -> None:
    assert select_checksums_asset([{"name": "NexShieldVeil-Setup.exe"}]) is None


def test_parses_a_standard_sha256sums_file() -> None:
    text = f"3b1f...  ignored.zip\n{'a' * 64}  NexShieldVeil-Setup.exe\n{'b' * 64}  other.exe\n"
    assert parse_sha256sums(text, "NexShieldVeil-Setup.exe") == "a" * 64


def test_parses_binary_mode_and_path_prefixed_entries() -> None:
    text = f"{'C' * 64} *dist/NexShieldVeil-Setup.exe\n"
    # Binary-mode '*', a directory prefix, and upper-case hex all normalise.
    assert parse_sha256sums(text, "NexShieldVeil-Setup.exe") == "c" * 64


def test_unknown_filename_yields_no_digest() -> None:
    assert parse_sha256sums(f"{'a' * 64}  other.exe\n", "NexShieldVeil-Setup.exe") is None


def test_malformed_lines_are_ignored() -> None:
    text = "garbage\nzz  NexShieldVeil-Setup.exe\n\n"
    assert parse_sha256sums(text, "NexShieldVeil-Setup.exe") is None


# --------------------------------------------------------------------------- #
# download verification
# --------------------------------------------------------------------------- #
_TRUSTED_URL = "https://objects.githubusercontent.com/nexshieldveil/NexShieldVeil-Setup.exe"


class _FakeResponse(io.BytesIO):
    """Minimal stand-in for an HTTP response body."""

    def __init__(self, payload: bytes) -> None:
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


@pytest.fixture
def served(monkeypatch):
    """Serve fixed bytes from the (otherwise networked) opener."""

    def _serve(payload: bytes) -> None:
        monkeypatch.setattr(
            checker, "_open", lambda url, timeout, headers=None: _FakeResponse(payload)
        )

    return _serve


def test_download_writes_the_file_when_the_digest_matches(served, tmp_path) -> None:
    payload = b"installer bytes"
    served(payload)
    dest = tmp_path / "setup.exe"
    path = download_installer(_TRUSTED_URL, str(dest), hashlib.sha256(payload).hexdigest())
    assert path == str(dest)
    assert dest.read_bytes() == payload


def test_download_reports_progress(served, tmp_path) -> None:
    payload = b"z" * (128 * 1024)
    served(payload)
    seen: list[float] = []
    download_installer(
        _TRUSTED_URL,
        str(tmp_path / "setup.exe"),
        hashlib.sha256(payload).hexdigest(),
        progress=seen.append,
    )
    assert seen and seen[-1] == pytest.approx(1.0)
    assert all(0.0 <= value <= 1.0 for value in seen)


def test_a_tampered_download_raises_and_leaves_nothing_on_disk(served, tmp_path) -> None:
    # The whole point of AM-4: a binary that fails verification must not survive
    # where a user could double-click it.
    served(b"tampered installer")
    dest = tmp_path / "setup.exe"
    with pytest.raises(IntegrityError):
        download_installer(_TRUSTED_URL, str(dest), hashlib.sha256(b"the real one").hexdigest())
    assert not dest.exists()


@pytest.mark.parametrize("digest", ["", "   ", "abc", "g" * 64, "a" * 63, None])
def test_download_refuses_a_missing_or_malformed_digest(served, tmp_path, digest) -> None:
    served(b"anything")
    dest = tmp_path / "setup.exe"
    with pytest.raises(IntegrityError):
        download_installer(_TRUSTED_URL, str(dest), digest)
    assert not dest.exists()


def test_digest_comparison_is_case_insensitive(served, tmp_path) -> None:
    payload = b"installer bytes"
    served(payload)
    dest = tmp_path / "setup.exe"
    download_installer(_TRUSTED_URL, str(dest), hashlib.sha256(payload).hexdigest().upper())
    assert dest.read_bytes() == payload


# --------------------------------------------------------------------------- #
# download directory + caller-facing contract
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_download_directory_is_private_to_the_user() -> None:
    path = installer_download_dir()
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
        assert mode == 0o700, f"expected 0700, got {mode:o}"
    finally:
        os.rmdir(path)


def test_download_directories_are_distinct() -> None:
    first, second = installer_download_dir(), installer_download_dir()
    try:
        assert first != second
    finally:
        os.rmdir(first)
        os.rmdir(second)


def test_can_auto_install_requires_both_url_and_digest() -> None:
    both = UpdateInfo("v1", "", "url", "https://github.com/x/setup.exe", "a" * 64)
    assert both.can_auto_install is True
    # An installer without a published digest is NOT installable automatically:
    # the UI must send the user to the release page instead.
    no_digest = UpdateInfo("v1", "", "url", "https://github.com/x/setup.exe", None)
    assert no_digest.can_auto_install is False
    assert UpdateInfo("v1", "", "url", None, "a" * 64).can_auto_install is False
