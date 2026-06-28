"""Unit tests for the pure update version logic (no network)."""

from __future__ import annotations

import pytest

from privacy_guard.update.version import is_newer, parse_version

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.2.3", (1, 2, 3)),
        ("v1.2.3", (1, 2, 3)),
        ("  v0.1.0 ", (0, 1, 0)),
        ("2.0.0-rc1", (2, 0, 0)),
        ("v10.20.30+build.5", (10, 20, 30)),
    ],
)
def test_parse_version(text: str, expected: tuple[int, int, int]) -> None:
    assert parse_version(text) == expected


@pytest.mark.parametrize("bad", ["", "abc", "v1", "1.2", "version-two"])
def test_parse_version_rejects_garbage(bad: str) -> None:
    with pytest.raises(ValueError, match="unparseable"):
        parse_version(bad)


@pytest.mark.parametrize(
    ("remote", "local", "newer"),
    [
        ("0.1.1", "0.1.0", True),
        ("v1.0.0", "0.9.9", True),
        ("0.1.0", "0.1.0", False),
        ("0.1.0", "0.1.1", False),
        ("1.2.0", "1.1.9", True),
        ("garbage", "0.1.0", False),  # fail-safe: never nag on unparseable remote
    ],
)
def test_is_newer(remote: str, local: str, newer: bool) -> None:
    assert is_newer(remote, local) is newer
