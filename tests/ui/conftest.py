"""Headless Qt test harness for the UI layer.

Everything here runs with ``QT_QPA_PLATFORM=offscreen`` — no display, no camera. If
PySide6 is not installed (e.g. a core-only checkout), the whole ``tests/ui`` tree is
skipped rather than failing collection.
"""

from __future__ import annotations

import os
from collections.abc import Callable

# Must be set before any Qt application object is created.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6", reason="UI tests require the [ui] extra (PySide6)")

from PySide6.QtCore import SignalInstance
from PySide6.QtGui import QGuiApplication


@pytest.fixture(scope="session")
def qapp() -> QGuiApplication:
    """A single offscreen QGuiApplication for the whole session (needed for QML)."""
    app = QGuiApplication.instance() or QGuiApplication([])
    return app  # session-scoped; Qt cleans up at interpreter exit


@pytest.fixture
def record() -> Callable[[SignalInstance], list[tuple]]:
    """Return a factory that wires a signal to a list of its emitted argument tuples.

    Usage::

        emissions = record(vm.label_changed)
        vm.do_something()
        assert len(emissions) == 1
    """

    def _record(signal: SignalInstance) -> list[tuple]:
        events: list[tuple] = []
        signal.connect(lambda *args: events.append(tuple(args)))
        return events

    return _record
