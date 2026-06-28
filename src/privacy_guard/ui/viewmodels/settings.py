"""Settings view-model: exposes editable config + computed captions, forwards edits.

Honesty: the masking-style options expose only what the live overlay actually does
(``veil``). ``blur``/``pixelate`` are listed as ``live=False`` with a 'soon' note so
the UI can show them disabled rather than pretend they work.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from privacy_guard.config.models import MaskStrategyName
from privacy_guard.masking import overlay_strategy_is_live
from privacy_guard.ui.controller import AppController
from privacy_guard.ui.state import sensitivity_key
from privacy_guard.ui.translator import Translator

_STRATEGIES: tuple[MaskStrategyName, ...] = ("veil", "blur", "pixelate")


class SettingsViewModel(QObject):
    """Two-way bridge between the settings UI and the controller config."""

    changed = Signal()

    def __init__(
        self, controller: AppController, translator: Translator, parent: QObject | None = None
    ) -> None:
        """Bind to controller config + translator."""
        super().__init__(parent)
        self._c = controller
        self._tr = translator
        controller.config_changed.connect(self.changed)
        translator.language_changed.connect(self.changed)

    # ---- detection ------------------------------------------------------- #
    def _get_sensitivity_deg(self) -> float:
        return self._c.snapshot.sensitivity_deg

    def _get_sensitivity_caption(self) -> str:
        deg = self._c.snapshot.sensitivity_deg
        value = self._tr.tr_key("unit.deg", value=round(deg))
        word = self._tr.tr_key(f"sensitivity.{sensitivity_key(deg)}")
        return f"{value} · {word}"

    def _get_trigger_ms(self) -> int:
        return self._c.snapshot.trigger_ms

    def _get_trigger_caption(self) -> str:
        return self._tr.tr_key("unit.ms", value=self._c.snapshot.trigger_ms)

    def _get_release_ms(self) -> int:
        return self._c.snapshot.release_ms

    def _get_release_caption(self) -> str:
        return self._tr.tr_key("unit.ms", value=self._c.snapshot.release_ms)

    def _get_release_floor(self) -> int:
        # The release slider can never go below the trigger (hysteresis invariant).
        return self._c.snapshot.trigger_ms

    # ---- masking --------------------------------------------------------- #
    def _get_opacity(self) -> float:
        return self._c.snapshot.opacity

    def _get_masking_strategy(self) -> str:
        return self._c.snapshot.masking_strategy

    def _get_masking_options(self) -> list[dict[str, object]]:
        options: list[dict[str, object]] = []
        for name in _STRATEGIES:
            live = overlay_strategy_is_live(name)
            options.append(
                {
                    "id": name,
                    "label": self._tr.tr_key(f"masking.{name}"),
                    "live": live,
                    "note": "" if live else self._tr.tr_key("masking.coming_soon"),
                }
            )
        return options

    # ---- camera / general ----------------------------------------------- #
    def _get_camera_index(self) -> int:
        return self._c.snapshot.camera_index

    def _get_start_at_login(self) -> bool:
        return self._c.snapshot.start_at_login

    def _get_language(self) -> str:
        return self._tr.language

    def _get_languages(self) -> list[dict[str, str]]:
        return [
            {"code": code, "label": self._tr.tr_key(f"language.{code}")}
            for code in self._tr.available_languages()
        ]

    sensitivity_deg = Property(float, _get_sensitivity_deg, notify=changed)
    sensitivity_caption = Property(str, _get_sensitivity_caption, notify=changed)
    trigger_ms = Property(int, _get_trigger_ms, notify=changed)
    trigger_caption = Property(str, _get_trigger_caption, notify=changed)
    release_ms = Property(int, _get_release_ms, notify=changed)
    release_caption = Property(str, _get_release_caption, notify=changed)
    release_floor = Property(int, _get_release_floor, notify=changed)
    opacity = Property(float, _get_opacity, notify=changed)
    masking_strategy = Property(str, _get_masking_strategy, notify=changed)
    masking_options = Property("QVariantList", _get_masking_options, notify=changed)
    camera_index = Property(int, _get_camera_index, notify=changed)
    start_at_login = Property(bool, _get_start_at_login, notify=changed)
    language = Property(str, _get_language, notify=changed)
    languages = Property("QVariantList", _get_languages, notify=changed)

    # ---- edits (forwarded to the controller / translator) --------------- #
    @Slot(float)
    def set_sensitivity_deg(self, deg: float) -> None:
        """Update the gaze tolerance."""
        self._c.set_sensitivity_deg(deg)

    @Slot(int)
    def set_trigger_ms(self, ms: int) -> None:
        """Update the trigger delay (may raise the release delay)."""
        self._c.set_trigger_ms(ms)

    @Slot(int)
    def set_release_ms(self, ms: int) -> None:
        """Update the release delay (clamped to >= trigger)."""
        self._c.set_release_ms(ms)

    @Slot(float)
    def set_opacity(self, opacity: float) -> None:
        """Update the veil opacity."""
        self._c.set_opacity(opacity)

    @Slot(str)
    def set_masking_strategy(self, strategy: str) -> None:
        """Update the masking strategy (UI should only let the user pick live ones)."""
        self._c.set_masking_strategy(strategy)

    @Slot(int)
    def select_camera(self, index: int) -> None:
        """Update the camera device index."""
        self._c.select_camera(index)

    @Slot(bool)
    def set_start_at_login(self, value: bool) -> None:
        """Update the 'start at login' preference."""
        self._c.set_start_at_login(value)

    @Slot(str)
    def set_language(self, code: str) -> None:
        """Switch the UI language (re-translates everything via the translator)."""
        self._tr.language = code
