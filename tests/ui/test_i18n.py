"""i18n parity + copy-honesty tests (Qt-free: scan the catalogs directly)."""

from __future__ import annotations

import re
import string

import pytest

from privacy_guard.ui.i18n_catalog import (
    AVAILABLE_LANGUAGES,
    catalog_keys,
    load_catalog,
    normalize_language,
)

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# parity: every language defines exactly the same keys
# --------------------------------------------------------------------------- #
def test_languages_have_identical_keys() -> None:
    reference = catalog_keys("fr")
    for lang in AVAILABLE_LANGUAGES:
        keys = catalog_keys(lang)
        missing = reference - keys
        extra = keys - reference
        assert not missing, f"{lang} is missing keys: {sorted(missing)}"
        assert not extra, f"{lang} has extra keys: {sorted(extra)}"


def test_no_value_is_empty() -> None:
    for lang in AVAILABLE_LANGUAGES:
        for key, value in load_catalog(lang).items():
            assert value.strip(), f"{lang}:{key} is empty"


def _placeholders(s: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(s) if name}


def test_placeholders_match_across_languages() -> None:
    # A {count}/{value}/{version} in FR must exist in EN too, or formatting breaks.
    fr = load_catalog("fr")
    en = load_catalog("en")
    for key in fr:
        assert _placeholders(fr[key]) == _placeholders(en[key]), f"placeholder mismatch at {key}"


def test_normalize_language_falls_back() -> None:
    assert normalize_language("en_US") == "en"
    assert normalize_language("fr-FR") == "fr"
    assert normalize_language("de") == "fr"  # unsupported -> default
    assert normalize_language(None) == "fr"


# --------------------------------------------------------------------------- #
# honesty: no over-promise, and the limits are actually surfaced
# --------------------------------------------------------------------------- #
# Affirmative over-promises we must never ship in UI copy. We phrase honest copy to
# avoid even the negated forms ("ne garantit pas") so a simple substring scan is safe.
_BANNED = [
    "invisible",
    "garanti",  # garantit / garantie / garanties
    "100 %",
    "100%",
    "impossible à voir",
    "impossible to see",
    "undetectable",
    "guarantee",
    "completely safe",
    "totalement sûr",
    "protection totale",
    "total protection",
    "fully private",
]


def test_no_overpromising_terms_in_any_catalog() -> None:
    for lang in AVAILABLE_LANGUAGES:
        for key, value in load_catalog(lang).items():
            low = value.lower()
            for term in _BANNED:
                assert term not in low, f"banned term {term!r} in {lang}:{key}: {value!r}"


def test_limits_are_present_in_catalog() -> None:
    # The 'about' and 'onboarding' surfaces must carry the honest limitations.
    required = {
        "about.limits.title",
        "about.limits.1",
        "about.limits.2",
        "about.limits.3",
        "onboarding.limits.title",
        "onboarding.limits.body",
        "about.tagline",
    }
    for lang in AVAILABLE_LANGUAGES:
        keys = catalog_keys(lang)
        assert required <= keys, f"{lang} missing limitation keys: {sorted(required - keys)}"


def test_tagline_admits_a_limit() -> None:
    # The tagline must convey 'reduces, not removes' rather than a promise.
    assert re.search(r"sans le supprimer", load_catalog("fr")["about.tagline"])
    assert re.search(r"does not remove", load_catalog("en")["about.tagline"])
