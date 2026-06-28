"""Tests for the Qt Translator's QML-facing slots and language switching."""

from __future__ import annotations

import pytest

from privacy_guard.ui.translator import Translator

pytestmark = pytest.mark.unit


def test_t_returns_translation(qapp) -> None:
    tr = Translator("fr")
    assert tr.t("action.quit") == "Quitter"
    tr.language = "en"
    assert tr.t("action.quit") == "Quit"


def test_t_unknown_key_returns_key(qapp) -> None:
    assert Translator("fr").t("does.not.exist") == "does.not.exist"


def test_tcount_interpolates(qapp) -> None:
    assert Translator("fr").tcount("faces.count", 3) == "Visages vus : 3"


def test_tvalue_interpolates(qapp) -> None:
    assert Translator("en").tvalue("unit.ms", "400") == "400 ms"


def test_language_change_emits_once(qapp, record) -> None:
    tr = Translator("fr")
    events = record(tr.language_changed)
    tr.language = "en"
    tr.language = "en"  # no-op, no extra emit
    assert len(events) == 1


def test_available_and_default(qapp) -> None:
    assert Translator.available_languages() == ("fr", "en")
    assert Translator.default_language() == "fr"
