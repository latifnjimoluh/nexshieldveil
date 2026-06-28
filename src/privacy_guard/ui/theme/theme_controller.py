"""Exposes the design tokens to QML and handles dark/light + reduced-motion.

QML binds to ``Theme.base``, ``Theme.accent``, ``Theme.stateColor(role)``,
``Theme.space("md")``, ``Theme.duration("veil_settle")`` … and re-themes live when
``is_dark`` flips. All values come from :mod:`tokens`, the single source of truth.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from privacy_guard.ui.theme import tokens as T


class ThemeController(QObject):
    """Runtime theme + motion preference, surfaced to QML as properties/slots."""

    theme_changed = Signal()
    reduced_motion_changed = Signal()

    def __init__(
        self, dark: bool = True, reduced_motion: bool = False, parent: QObject | None = None
    ) -> None:
        """Start in the given theme and motion preference (defaults: dark, full motion)."""
        super().__init__(parent)
        self._dark = dark
        self._reduced_motion = reduced_motion

    @property
    def _name(self) -> T.ThemeName:
        return "dark" if self._dark else "light"

    # ---- theme toggle ---------------------------------------------------- #
    def _get_is_dark(self) -> bool:
        return self._dark

    def _set_is_dark(self, value: bool) -> None:
        if value != self._dark:
            self._dark = value
            self.theme_changed.emit()

    def _get_name(self) -> str:
        return self._name

    is_dark = Property(bool, _get_is_dark, _set_is_dark, notify=theme_changed)
    name = Property(str, _get_name, notify=theme_changed)

    # ---- reduced motion -------------------------------------------------- #
    def _get_reduced_motion(self) -> bool:
        return self._reduced_motion

    def _set_reduced_motion(self, value: bool) -> None:
        if value != self._reduced_motion:
            self._reduced_motion = value
            self.reduced_motion_changed.emit()

    reduced_motion = Property(
        bool, _get_reduced_motion, _set_reduced_motion, notify=reduced_motion_changed
    )

    # ---- palette (properties for easy binding) -------------------------- #
    def _base(self) -> str:
        return T.color(self._name, "base")

    def _panel(self) -> str:
        return T.color(self._name, "panel")

    def _line(self) -> str:
        return T.color(self._name, "line")

    def _ink(self) -> str:
        return T.color(self._name, "ink")

    def _ink_soft(self) -> str:
        return T.color(self._name, "inkSoft")

    def _accent(self) -> str:
        return T.color(self._name, "accent")

    base = Property(str, _base, notify=theme_changed)
    panel = Property(str, _panel, notify=theme_changed)
    line = Property(str, _line, notify=theme_changed)
    ink = Property(str, _ink, notify=theme_changed)
    inkSoft = Property(str, _ink_soft, notify=theme_changed)
    accent = Property(str, _accent, notify=theme_changed)

    # ---- fonts ----------------------------------------------------------- #
    def _font_display(self) -> str:
        return T.FONTS["display"]

    def _font_ui(self) -> str:
        return T.FONTS["ui"]

    def _font_mono(self) -> str:
        return T.FONTS["mono"]

    fontDisplay = Property(str, _font_display, constant=True)
    fontUi = Property(str, _font_ui, constant=True)
    fontMono = Property(str, _font_mono, constant=True)

    # ---- token lookups (slots for QML) ---------------------------------- #
    @Slot(str, result=str)
    def stateColor(self, role: str) -> str:
        """Semantic state colour for the current theme."""
        return T.state_color(self._name, role)

    @Slot(str, result=int)
    def space(self, name: str) -> int:
        """Spacing-scale value by name (xxs…xxxl)."""
        return T.SPACING[name]

    @Slot(str, result=int)
    def radius(self, name: str) -> int:
        """Corner-radius value by name (sm/md/lg/pill)."""
        return T.RADII[name]

    @Slot(str, result=int)
    def fontSize(self, name: str) -> int:
        """Type-scale value by name (caption…hero)."""
        return T.TYPE_SCALE[name]

    @Slot(str, result=int)
    def duration(self, name: str) -> int:
        """Motion duration by name, collapsed to a short fade under reduced-motion."""
        if self._reduced_motion:
            return T.REDUCED_MOTION_MS
        return T.MOTION[name]

    @Slot()
    def toggle(self) -> None:
        """Flip between dark and light."""
        self.is_dark = not self._dark
