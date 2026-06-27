"""TOML loading for Privacy Guard configuration.

Reading uses the stdlib ``tomllib`` (Python 3.11+); no network, no auto-download.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from privacy_guard.config.models import AppConfig


def load_config(path: str | Path) -> AppConfig:
    """Load and validate an :class:`AppConfig` from a TOML file.

    Args:
        path: Path to the TOML configuration file.

    Returns:
        A validated :class:`AppConfig`.

    Raises:
        FileNotFoundError: If the file does not exist.
        pydantic.ValidationError: If values are missing/out of bounds/unknown.
    """
    p = Path(path)
    if not p.is_file():
        msg = f"Configuration file not found: {p}"
        raise FileNotFoundError(msg)
    with p.open("rb") as fh:
        data = tomllib.load(fh)
    return AppConfig(**data)
