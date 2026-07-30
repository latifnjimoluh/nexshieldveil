"""DonateViewModel tests (Qt-free logic: copy + intents, no network, no browser)."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="UI tests require the [ui] extra (PySide6)")

from privacy_guard.ui.translator import Translator
from privacy_guard.ui.viewmodels.donate import DONATION_URL, DonateViewModel

pytestmark = pytest.mark.unit


def test_exposes_translated_copy() -> None:
    vm = DonateViewModel(Translator("fr"))
    assert vm.property("title") == "Soutenir NexShieldVeil"
    assert vm.property("action_label") == "Faire un don"
    assert vm.property("body")
    assert vm.property("note")


def test_url_is_the_kpay_payment_link() -> None:
    vm = DonateViewModel(Translator("fr"))
    assert vm.property("url") == DONATION_URL
    assert DONATION_URL.startswith("https://kpay.site/pay/link/")


def test_donate_emits_the_payment_link(record) -> None:
    vm = DonateViewModel(Translator("fr"))
    emissions = record(vm.donate_requested)
    vm.donate()
    assert emissions == [(DONATION_URL,)]


def test_open_window_emits_the_intent(record) -> None:
    vm = DonateViewModel(Translator("fr"))
    emissions = record(vm.window_requested)
    vm.open_window()
    assert emissions == [()]


def test_copy_retranslates_on_language_change() -> None:
    tr = Translator("fr")
    vm = DonateViewModel(tr)
    assert vm.property("action_label") == "Faire un don"
    tr.language = "en"
    assert vm.property("action_label") == "Make a donation"
