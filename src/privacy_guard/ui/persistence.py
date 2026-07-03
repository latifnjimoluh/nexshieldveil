"""User-settings persistence (M-R2): pure save/restore logic, Qt-free.

The beta feedback was blunt: « on ne peut pas enregistrer mes réglages, ça
redémarre à chaque fois ». This module fixes that by round-tripping the
user-adjustable snapshot fields through a small key/value store.

The *store* is a structural protocol matching ``QSettings`` (``value`` /
``setValue``), so the shell hands in the real ``QSettings`` — the mechanism
this app already uses for the language and onboarding flags, keeping the
"preferences persist via QSettings only" privacy statement true — while tests
use a dict-backed fake. No new file format, no image, no network.

Restoring is deliberately paranoid: values coming back from a registry are
often stringified, may be missing, or may have been edited into junk. Every
value is coerced then fed through the controller's own setter slots, so the
exact same clamping/validation as a UI interaction applies — a corrupt store
can degrade a value to its default, never crash the app (P4).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from privacy_guard.masking import RUNTIME_OVERLAY_STRATEGIES
from privacy_guard.ui.state import UiSnapshot

# Namespaced so these keys never collide with the shell's own ones
# ("language", "onboarding_done").
_PREFIX = "settings/"


class SettingsStore(Protocol):
    """The tiny slice of ``QSettings`` we rely on (dict-backed in tests)."""

    def value(self, key: str) -> object:  # noqa: D102 - QSettings-shaped
        ...

    def setValue(self, key: str, value: object) -> None:  # noqa: D102 - QSettings-shaped
        ...


class SettingsSink(Protocol):
    """The controller slots restoring goes through (so clamping stays in one place)."""

    def set_masking_strategy(self, strategy: str) -> None:  # noqa: D102
        ...

    def set_opacity(self, opacity: float) -> None:  # noqa: D102
        ...

    def set_blur_radius(self, radius: int) -> None:  # noqa: D102
        ...

    def set_pixelate_blocks(self, blocks: int) -> None:  # noqa: D102
        ...

    def set_sensitivity_deg(self, deg: float) -> None:  # noqa: D102
        ...

    def set_trigger_ms(self, ms: int) -> None:  # noqa: D102
        ...

    def set_release_ms(self, ms: int) -> None:  # noqa: D102
        ...

    def set_start_at_login(self, value: bool) -> None:  # noqa: D102
        ...


# --------------------------------------------------------------------------- #
# tolerant coercers: registry values come back stringified; junk yields None
# --------------------------------------------------------------------------- #
def _as_int(value: object) -> int | None:
    if isinstance(value, bool):  # bool is an int subclass; reject it explicitly
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _as_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _as_strategy(value: object) -> str | None:
    text = str(value).strip().lower()
    return text if text in RUNTIME_OVERLAY_STRATEGIES else None


# Field order matters on restore: trigger_ms must land before release_ms, because
# the setters enforce release >= trigger against the *current* values (restoring
# release first would let the default trigger inflate a smaller saved release).
_FIELDS: tuple[tuple[str, Callable[[object], object | None], str], ...] = (
    ("masking_strategy", _as_strategy, "set_masking_strategy"),
    ("opacity", _as_float, "set_opacity"),
    ("blur_radius", _as_int, "set_blur_radius"),
    ("pixelate_blocks", _as_int, "set_pixelate_blocks"),
    ("sensitivity_deg", _as_float, "set_sensitivity_deg"),
    ("trigger_ms", _as_int, "set_trigger_ms"),
    ("release_ms", _as_int, "set_release_ms"),
    ("start_at_login", _as_bool, "set_start_at_login"),
)

PERSISTED_FIELDS: tuple[str, ...] = tuple(name for name, _, _ in _FIELDS)
"""Exactly the settings the UI lets the user change — nothing else is written.

Session state (running, preview, errors, faces…) is deliberately NOT persisted:
the preview must stay opt-in per session, and errors must be re-derived live.
"""


def save_settings(snapshot: UiSnapshot, store: SettingsStore) -> None:
    """Write the user-adjustable fields of ``snapshot`` into ``store``."""
    for name in PERSISTED_FIELDS:
        store.setValue(_PREFIX + name, getattr(snapshot, name))


def restore_settings(sink: SettingsSink, store: SettingsStore) -> None:
    """Feed stored values back through the controller's setters.

    Missing keys are skipped (defaults stand); junk values are dropped by the
    coercers; out-of-range values are clamped by the setters themselves. A
    hand-edited or corrupt store therefore can never crash startup.
    """
    for name, coerce, setter_name in _FIELDS:
        raw = store.value(_PREFIX + name)
        if raw is None:
            continue
        value = coerce(raw)
        if value is None:
            continue
        getattr(sink, setter_name)(value)
