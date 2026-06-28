"""About view-model: version, honest tagline, and the list of limitations."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal

from privacy_guard import __version__
from privacy_guard.ui.translator import Translator

_LIMIT_KEYS = (
    "about.limits.1",
    "about.limits.2",
    "about.limits.3",
    "about.limits.4",
    "about.limits.5",
)


class AboutViewModel(QObject):
    """Read-only surface that states what the product does and does not do."""

    changed = Signal()

    def __init__(self, translator: Translator, parent: QObject | None = None) -> None:
        """Bind to the translator (re-translates on language change)."""
        super().__init__(parent)
        self._tr = translator
        translator.language_changed.connect(self.changed)

    def _get_title(self) -> str:
        return self._tr.tr_key("about.title")

    def _get_version(self) -> str:
        return self._tr.tr_key("about.version", version=__version__)

    def _get_tagline(self) -> str:
        return self._tr.tr_key("about.tagline")

    def _get_local_text(self) -> str:
        return self._tr.tr_key("about.local")

    def _get_license_text(self) -> str:
        return self._tr.tr_key("about.license")

    def _get_limits_title(self) -> str:
        return self._tr.tr_key("about.limits.title")

    def _get_limits(self) -> list[str]:
        return [self._tr.tr_key(key) for key in _LIMIT_KEYS]

    title = Property(str, _get_title, notify=changed)
    version = Property(str, _get_version, notify=changed)
    tagline = Property(str, _get_tagline, notify=changed)
    local_text = Property(str, _get_local_text, notify=changed)
    license_text = Property(str, _get_license_text, notify=changed)
    limits_title = Property(str, _get_limits_title, notify=changed)
    limits = Property("QVariantList", _get_limits, notify=changed)
