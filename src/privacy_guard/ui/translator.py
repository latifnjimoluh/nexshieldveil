"""A small Qt translator exposed to QML and view-models.

It wraps the pure :mod:`~privacy_guard.ui.i18n_catalog` loader in a ``QObject`` so QML
can call ``Tr.t("some.key")`` and re-render when the language changes at runtime.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from privacy_guard.ui.i18n_catalog import (
    AVAILABLE_LANGUAGES,
    DEFAULT_LANGUAGE,
    normalize_language,
    translate,
)


class Translator(QObject):
    """Runtime-switchable translator. ``language_changed`` re-translates the UI."""

    language_changed = Signal()

    def __init__(self, language: str | None = None, parent: QObject | None = None) -> None:
        """Initialise with a language (normalised; defaults to the system/FR fallback)."""
        super().__init__(parent)
        self._language = normalize_language(language)

    def _get_language(self) -> str:
        return self._language

    def _set_language(self, language: str) -> None:
        code = normalize_language(language)
        if code != self._language:
            self._language = code
            self.language_changed.emit()

    language = Property(str, _get_language, _set_language, notify=language_changed)

    @Slot(str, result=str)
    def t(self, key: str) -> str:
        """Translate a static key (no interpolation) for QML bindings."""
        return translate(self._language, key)

    @Slot(str, int, result=str)
    def tcount(self, key: str, count: int) -> str:
        """Translate a key that interpolates ``{count}`` (e.g. the faces counter)."""
        return translate(self._language, key, count=count)

    @Slot(str, str, result=str)
    def tvalue(self, key: str, value: str) -> str:
        """Translate a key that interpolates ``{value}`` (e.g. units like ``{value}°``)."""
        return translate(self._language, key, value=value)

    def tr_key(self, key: str, **kwargs: object) -> str:
        """Python-side translate with arbitrary kwargs (used by view-models)."""
        return translate(self._language, key, **kwargs)

    @staticmethod
    def available_languages() -> tuple[str, ...]:
        """Supported language codes."""
        return AVAILABLE_LANGUAGES

    @staticmethod
    def default_language() -> str:
        """The fallback language code."""
        return DEFAULT_LANGUAGE
