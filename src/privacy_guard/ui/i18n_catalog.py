"""Pure (Qt-free) i18n catalog loading.

Reading bundled JSON only — no writes, no network. Kept Qt-free so the parity and
copy-honesty tests can scan the catalogs without a display.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

AVAILABLE_LANGUAGES: tuple[str, ...] = ("fr", "en")
DEFAULT_LANGUAGE = "fr"

_I18N_DIR = Path(__file__).parent / "i18n"


def normalize_language(lang: str | None) -> str:
    """Map an arbitrary locale tag (e.g. ``'en_US'``) to a supported language code."""
    if not lang:
        return DEFAULT_LANGUAGE
    code = lang.replace("-", "_").split("_", 1)[0].lower()
    return code if code in AVAILABLE_LANGUAGES else DEFAULT_LANGUAGE


@cache
def load_catalog(lang: str) -> dict[str, str]:
    """Load one language catalog as a flat ``key -> string`` mapping."""
    code = normalize_language(lang)
    path = _I18N_DIR / f"{code}.json"
    data: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    return data


def catalog_keys(lang: str) -> set[str]:
    """The set of keys defined for a language (used by the parity test)."""
    return set(load_catalog(lang))


def translate(lang: str, key: str, **kwargs: object) -> str:
    """Look up ``key`` for ``lang`` and ``str.format`` it; fall back to the key itself."""
    template = load_catalog(lang).get(key, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template
