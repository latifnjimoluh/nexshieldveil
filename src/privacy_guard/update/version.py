"""Pure semantic-version parsing and comparison (no network, fully testable).

Kept deliberately tiny and side-effect free so the update *decision* logic is unit
tested headlessly, separate from the quarantined network code in ``checker``.
"""

from __future__ import annotations

import re

_VERSION_RE = re.compile(r"^\s*v?(\d+)\.(\d+)\.(\d+)")


def parse_version(text: str) -> tuple[int, int, int]:
    """Parse ``"v1.2.3"`` / ``"1.2.3-rc1"`` into ``(1, 2, 3)``.

    Raises:
        ValueError: If no ``major.minor.patch`` prefix is present.
    """
    match = _VERSION_RE.match(text)
    if match is None:
        msg = f"unparseable version: {text!r}"
        raise ValueError(msg)
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def is_newer(remote: str, local: str) -> bool:
    """Whether ``remote`` is a strictly newer version than ``local``.

    Unparseable inputs are treated as "not newer" (fail safe: never nags on garbage).
    """
    try:
        return parse_version(remote) > parse_version(local)
    except ValueError:
        return False
