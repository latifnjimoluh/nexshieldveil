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
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtWidgets import QApplication

from privacy_guard.ui.fake_controller import FakeController
from privacy_guard.ui.preview import CameraImageProvider
from privacy_guard.ui.qml_app import install_context, view_url
from privacy_guard.ui.state import UiSnapshot
from privacy_guard.ui.theme.theme_controller import ThemeController
from privacy_guard.ui.translator import Translator
from privacy_guard.ui.viewmodels import (
    AboutViewModel,
    CameraViewModel,
    OnboardingViewModel,
    SettingsViewModel,
    StatusViewModel,
    TrayViewModel,
)


@pytest.fixture(scope="session")
def qapp() -> QGuiApplication:
    """A single offscreen QApplication for the whole session.

    QApplication (not QGuiApplication): the overlay presenter tests instantiate
    QWidget windows, and QML is happy with either.
    """
    app = QApplication.instance() or QApplication([])
    return app  # session-scoped; Qt cleans up at interpreter exit


class QmlHarness:
    """Builds a QML engine wired to fakes, and loads view files headlessly."""

    def __init__(self, snapshot: UiSnapshot | None = None, *, dark: bool = True) -> None:
        self.controller = FakeController(snapshot)
        self.translator = Translator("fr")
        self.theme = ThemeController(dark=dark)
        self.status = StatusViewModel(self.controller, self.translator)
        self.settings = SettingsViewModel(self.controller, self.translator)
        self.onboarding = OnboardingViewModel(self.controller, self.translator)
        self.about = AboutViewModel(self.translator)
        self.tray = TrayViewModel(self.controller, self.translator)
        self.provider = CameraImageProvider()
        self.camera = CameraViewModel(self.controller, self.translator, self.provider)
        self.engine = QQmlEngine()
        self.engine.addImportPath(str(view_url("").toLocalFile()))
        self.engine.addImageProvider(CameraImageProvider.PROVIDER_ID, self.provider)
        install_context(
            self.engine.rootContext(),
            theme=self.theme,
            translator=self.translator,
            status=self.status,
            settings=self.settings,
            onboarding=self.onboarding,
            about=self.about,
            tray=self.tray,
            camera=self.camera,
        )
        self._kept: list[object] = []

    def load(self, view_name: str):
        """Instantiate a view file; fail loudly on any QML error."""
        component = QQmlComponent(self.engine, view_url(view_name))
        obj = component.create()
        assert obj is not None, f"{view_name} failed to load:\n" + "\n".join(
            e.toString() for e in component.errors()
        )
        # Keep the C++ object alive for the test (QML would otherwise JS-GC it).
        QQmlEngine.setObjectOwnership(obj, QQmlEngine.ObjectOwnership.CppOwnership)
        self._kept.extend((component, obj))
        return obj


@pytest.fixture
def qml(qapp):
    """Factory: ``qml()`` -> a fresh QmlHarness (optionally with a starting snapshot)."""

    def _make(snapshot: UiSnapshot | None = None, *, dark: bool = True) -> QmlHarness:
        return QmlHarness(snapshot, dark=dark)

    return _make


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
