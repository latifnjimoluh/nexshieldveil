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
from privacy_guard.ui.state import (
    ABSENCE_LOCK_DEFAULT_MS,
    ABSENCE_LOCK_MS_RANGE,
    SMOOTHING_ALPHA_RANGE,
    reactivity_key,
    sensitivity_key,
)
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

    # ---- walk-away lock (AM-7): a toggle plus its delay ------------------- #
    def _get_absence_lock_enabled(self) -> bool:
        return self._c.snapshot.absence_lock_ms > 0

    def _get_absence_lock_ms(self) -> int:
        # The slider needs a sensible position even while the feature is off.
        return self._c.snapshot.absence_lock_ms or ABSENCE_LOCK_DEFAULT_MS

    def _get_absence_lock_caption(self) -> str:
        return self._tr.tr_key("unit.s", value=round(self._get_absence_lock_ms() / 1000))

    def _get_absence_lock_min_ms(self) -> int:
        return ABSENCE_LOCK_MS_RANGE[0]

    # ---- reactivity (AM-11): the EMA that silently added masking latency --- #
    def _get_smoothing_alpha(self) -> float:
        return self._c.snapshot.smoothing_alpha

    def _get_smoothing_alpha_min(self) -> float:
        return SMOOTHING_ALPHA_RANGE[0]

    def _get_reactivity_caption(self) -> str:
        return self._tr.tr_key(f"reactivity.{reactivity_key(self._c.snapshot.smoothing_alpha)}")

    # ---- masking --------------------------------------------------------- #
    def _get_opacity(self) -> float:
        return self._c.snapshot.opacity

    def _get_masking_strategy(self) -> str:
        return self._c.snapshot.masking_strategy

    def _get_blur_radius(self) -> int:
        return self._c.snapshot.blur_radius

    def _get_blur_radius_caption(self) -> str:
        return self._tr.tr_key("unit.px", value=self._c.snapshot.blur_radius)

    def _get_pixelate_blocks(self) -> int:
        return self._c.snapshot.pixelate_blocks

    def _get_pixelate_blocks_caption(self) -> str:
        return self._tr.tr_key("unit.blocks", value=self._c.snapshot.pixelate_blocks)

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

    # ---- screen geometry (AM-10b): correcting what the OS reported -------- #
    def _get_screen_width_mm(self) -> float:
        return self._c.snapshot.screen_width_mm

    def _get_screen_height_mm(self) -> float:
        return self._c.snapshot.screen_height_mm

    def _get_camera_above_mm(self) -> float:
        return self._c.snapshot.camera_above_mm

    def _get_screen_size_manual(self) -> bool:
        return self._c.snapshot.screen_size_manual

    def _get_screen_size_source(self) -> str:
        # Say where the number came from: "measured" is worth trusting, a manual
        # correction is worth re-checking after a monitor change.
        key = (
            "settings.screen.source.manual"
            if self._get_screen_size_manual()
            else ("settings.screen.source.measured")
        )
        return self._tr.tr_key(key)

    # ---- camera / general ----------------------------------------------- #
    def _get_camera_index(self) -> int:
        return self._c.snapshot.camera_index

    def _get_start_at_login(self) -> bool:
        return self._c.snapshot.start_at_login

    def _get_start_at_login_supported(self) -> bool:
        # A switch that cannot act must not look active (AM-1): on a platform
        # with no autostart mechanism, the view greys it out instead of storing
        # a preference that would never be honoured.
        from privacy_guard.ui.autostart import is_supported

        return is_supported()

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
    absence_lock_enabled = Property(bool, _get_absence_lock_enabled, notify=changed)
    absence_lock_ms = Property(int, _get_absence_lock_ms, notify=changed)
    absence_lock_caption = Property(str, _get_absence_lock_caption, notify=changed)
    absence_lock_min_ms = Property(int, _get_absence_lock_min_ms, notify=changed)
    smoothing_alpha = Property(float, _get_smoothing_alpha, notify=changed)
    smoothing_alpha_min = Property(float, _get_smoothing_alpha_min, notify=changed)
    reactivity_caption = Property(str, _get_reactivity_caption, notify=changed)
    opacity = Property(float, _get_opacity, notify=changed)
    masking_strategy = Property(str, _get_masking_strategy, notify=changed)
    masking_options = Property("QVariantList", _get_masking_options, notify=changed)
    blur_radius = Property(int, _get_blur_radius, notify=changed)
    blur_radius_caption = Property(str, _get_blur_radius_caption, notify=changed)
    pixelate_blocks = Property(int, _get_pixelate_blocks, notify=changed)
    pixelate_blocks_caption = Property(str, _get_pixelate_blocks_caption, notify=changed)
    screen_width_mm = Property(float, _get_screen_width_mm, notify=changed)
    screen_height_mm = Property(float, _get_screen_height_mm, notify=changed)
    camera_above_mm = Property(float, _get_camera_above_mm, notify=changed)
    screen_size_manual = Property(bool, _get_screen_size_manual, notify=changed)
    screen_size_source = Property(str, _get_screen_size_source, notify=changed)
    camera_index = Property(int, _get_camera_index, notify=changed)
    start_at_login = Property(bool, _get_start_at_login, notify=changed)
    start_at_login_supported = Property(bool, _get_start_at_login_supported, notify=changed)
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

    @Slot(bool)
    def set_absence_lock_enabled(self, enabled: bool) -> None:
        """Turn the walk-away lock on (at the current/default delay) or off."""
        if enabled:
            self._c.set_absence_lock_ms(self._get_absence_lock_ms())
        else:
            self._c.set_absence_lock_ms(0)

    @Slot(int)
    def set_absence_lock_ms(self, ms: int) -> None:
        """Change the walk-away delay (ignored while the lock is off)."""
        if self._c.snapshot.absence_lock_ms > 0:
            self._c.set_absence_lock_ms(int(ms))

    @Slot(float)
    def set_smoothing_alpha(self, alpha: float) -> None:
        """Update the smoothing/reactivity trade-off."""
        self._c.set_smoothing_alpha(alpha)

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
    def set_blur_radius(self, radius: int) -> None:
        """Update the blur radius (clamped to the config bounds)."""
        self._c.set_blur_radius(radius)

    @Slot(int)
    def set_pixelate_blocks(self, blocks: int) -> None:
        """Update the pixelation block count (clamped to the config bounds)."""
        self._c.set_pixelate_blocks(blocks)

    @Slot(float)
    def set_screen_width_mm(self, mm: float) -> None:
        """Correct the modelled screen width."""
        self._c.set_screen_width_mm(mm)

    @Slot(float)
    def set_screen_height_mm(self, mm: float) -> None:
        """Correct the modelled screen height."""
        self._c.set_screen_height_mm(mm)

    @Slot(float)
    def set_camera_above_mm(self, mm: float) -> None:
        """Correct how far the camera sits above the screen."""
        self._c.set_camera_above_mm(mm)

    @Slot()
    def reset_screen_size(self) -> None:
        """Forget the correction and let the next start measure the screen again."""
        self._c.reset_screen_size()

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
