"""View-models: the testable presentation logic between the controller and QML.

Each view-model is a ``QObject`` that reads the :class:`~privacy_guard.ui.controller.
AppController` snapshot, translates it via the :class:`~privacy_guard.ui.translator.
Translator`, and exposes ready-to-bind properties. They hold no Qt widgets and no
hardware, so they are exercised headlessly with the ``FakeController``.
"""

from __future__ import annotations

from privacy_guard.ui.viewmodels.about import AboutViewModel
from privacy_guard.ui.viewmodels.onboarding import OnboardingViewModel
from privacy_guard.ui.viewmodels.settings import SettingsViewModel
from privacy_guard.ui.viewmodels.status import StatusViewModel
from privacy_guard.ui.viewmodels.tray import TrayViewModel

__all__ = [
    "AboutViewModel",
    "OnboardingViewModel",
    "SettingsViewModel",
    "StatusViewModel",
    "TrayViewModel",
]
