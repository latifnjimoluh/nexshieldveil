"""The UI<->core contract: an observable :class:`AppController` (a ``QObject``).

This is the *only* surface the view-models and QML touch. It exposes the current
:class:`~privacy_guard.ui.state.UiSnapshot` as notifiable Qt properties and accepts
commands as slots. It holds no camera, no pipeline, no heavy work — subclasses supply
those:

* :class:`~privacy_guard.ui.fake_controller.FakeController` drives it by hand (tests).
* :class:`~privacy_guard.ui.core_controller.CoreController` drives it from the real
  pipeline on a ``QTimer`` (the live app).

Keeping the base concrete and fully functional (commands update the snapshot here)
means the entire presentation layer can be tested against the base/fake with no
hardware. Subclasses override the command slots to *also* act on the core, calling
``super()`` to keep the snapshot in sync.
"""

from __future__ import annotations

import dataclasses
import time

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from privacy_guard.ui.state import (
    ABSENCE_LOCK_MS_RANGE,
    BLUR_RADIUS_RANGE,
    PIXELATE_BLOCKS_RANGE,
    SENSITIVITY_DEG_RANGE,
    SMOOTHING_ALPHA_RANGE,
    SNOOZE_MINUTES_RANGE,
    CameraError,
    UiSnapshot,
)


class AppController(QObject):
    """Observable presentation state + commands, decoupled from the core."""

    # Notify signals (one per logically-distinct concern the UI binds to).
    state_changed = Signal()
    camera_active_changed = Signal()
    error_changed = Signal()
    faces_count_changed = Signal()
    engaging_changed = Signal()
    running_changed = Signal()
    config_changed = Signal()
    preview_changed = Signal()
    snooze_changed = Signal()
    # Intent signals the app shell connects (open the settings window, quit, …).
    settings_requested = Signal()
    about_requested = Signal()
    onboarding_finished = Signal()
    quit_requested = Signal()

    def __init__(self, snapshot: UiSnapshot | None = None, parent: QObject | None = None) -> None:
        """Initialise with an optional starting snapshot (defaults to paused)."""
        super().__init__(parent)
        self._snap = snapshot or UiSnapshot()
        # Timed pause (M-R3): fires once to resume watching automatically.
        self._snooze_timer = QTimer(self)
        self._snooze_timer.setSingleShot(True)
        self._snooze_timer.timeout.connect(self._on_snooze_elapsed)

    # ------------------------------------------------------------------ #
    # snapshot plumbing
    # ------------------------------------------------------------------ #
    @property
    def snapshot(self) -> UiSnapshot:
        """The current immutable snapshot (read-only)."""
        return self._snap

    def _apply(self, new: UiSnapshot) -> None:
        """Swap in a new snapshot, emitting only the signals that actually changed."""
        old, self._snap = self._snap, new
        if old.protection_state != new.protection_state:
            self.state_changed.emit()
        if old.camera_active != new.camera_active:
            self.camera_active_changed.emit()
        if old.error_kind != new.error_kind:
            self.error_changed.emit()
        if old.faces_count != new.faces_count:
            self.faces_count_changed.emit()
        if old.engaging != new.engaging:
            self.engaging_changed.emit()
        if old.running != new.running:
            self.running_changed.emit()
        if old.preview_enabled != new.preview_enabled:
            self.preview_changed.emit()
        if old.snoozed_until_ms != new.snoozed_until_ms:
            self.snooze_changed.emit()
        config_fields = (
            "masking_strategy",
            "opacity",
            "blur_radius",
            "pixelate_blocks",
            "sensitivity_deg",
            "trigger_ms",
            "release_ms",
            "absence_lock_ms",
            "smoothing_alpha",
            "camera_index",
            "start_at_login",
        )
        if any(getattr(old, f) != getattr(new, f) for f in config_fields):
            self.config_changed.emit()

    def _update(self, **changes: object) -> None:
        """Apply field changes by producing a new frozen snapshot."""
        self._apply(dataclasses.replace(self._snap, **changes))

    # ------------------------------------------------------------------ #
    # properties (read by QML / view-models)
    # ------------------------------------------------------------------ #
    def _get_protection_state(self) -> str:
        return self._snap.protection_state.value

    def _get_camera_active(self) -> bool:
        return self._snap.camera_active

    def _get_error_kind(self) -> str:
        return self._snap.error_kind.value if self._snap.error_kind is not None else ""

    def _get_faces_count(self) -> int:
        return self._snap.faces_count

    def _get_engaging(self) -> bool:
        return self._snap.engaging

    def _get_running(self) -> bool:
        return self._snap.running

    def _get_masking_strategy(self) -> str:
        return self._snap.masking_strategy

    def _get_opacity(self) -> float:
        return self._snap.opacity

    def _get_blur_radius(self) -> int:
        return self._snap.blur_radius

    def _get_pixelate_blocks(self) -> int:
        return self._snap.pixelate_blocks

    def _get_sensitivity_deg(self) -> float:
        return self._snap.sensitivity_deg

    def _get_trigger_ms(self) -> int:
        return self._snap.trigger_ms

    def _get_release_ms(self) -> int:
        return self._snap.release_ms

    def _get_camera_index(self) -> int:
        return self._snap.camera_index

    def _get_absence_lock_ms(self) -> int:
        return self._snap.absence_lock_ms

    def _get_smoothing_alpha(self) -> float:
        return self._snap.smoothing_alpha

    def _get_start_at_login(self) -> bool:
        return self._snap.start_at_login

    def _get_preview_enabled(self) -> bool:
        return self._snap.preview_enabled

    protection_state = Property(str, _get_protection_state, notify=state_changed)
    camera_active = Property(bool, _get_camera_active, notify=camera_active_changed)
    error_kind = Property(str, _get_error_kind, notify=error_changed)
    faces_count = Property(int, _get_faces_count, notify=faces_count_changed)
    engaging = Property(bool, _get_engaging, notify=engaging_changed)
    running = Property(bool, _get_running, notify=running_changed)
    masking_strategy = Property(str, _get_masking_strategy, notify=config_changed)
    opacity = Property(float, _get_opacity, notify=config_changed)
    blur_radius = Property(int, _get_blur_radius, notify=config_changed)
    pixelate_blocks = Property(int, _get_pixelate_blocks, notify=config_changed)
    sensitivity_deg = Property(float, _get_sensitivity_deg, notify=config_changed)
    trigger_ms = Property(int, _get_trigger_ms, notify=config_changed)
    release_ms = Property(int, _get_release_ms, notify=config_changed)
    camera_index = Property(int, _get_camera_index, notify=config_changed)
    absence_lock_ms = Property(int, _get_absence_lock_ms, notify=config_changed)
    smoothing_alpha = Property(float, _get_smoothing_alpha, notify=config_changed)
    start_at_login = Property(bool, _get_start_at_login, notify=config_changed)
    preview_enabled = Property(bool, _get_preview_enabled, notify=preview_changed)

    # ------------------------------------------------------------------ #
    # commands (slots). Base updates the snapshot; subclasses also act on the core.
    # ------------------------------------------------------------------ #
    @Slot()
    def enable(self) -> None:
        """Start (resume) watching. Clears any pause/snooze; errors re-derive live."""
        self._snooze_timer.stop()
        self._update(running=True, snoozed_until_ms=None)

    @Slot()
    def pause(self) -> None:
        """Pause watching (until further notice) and release the camera.

        An explicit pause always cancels a pending snooze: the user asked for
        'until I say so', not 'for a few minutes'.
        """
        self._snooze_timer.stop()
        self._update(
            running=False,
            camera_active=False,
            error_kind=None,
            preview_enabled=False,
            snoozed_until_ms=None,
        )

    @Slot()
    def toggle(self) -> None:
        """Toggle between watching and paused."""
        if self._snap.running:
            self.pause()
        else:
            self.enable()

    @Slot(int)
    def snooze(self, minutes: int) -> None:
        """Pause temporarily (M-R3): watching resumes by itself after ``minutes``.

        Goes through :meth:`pause` first, so subclasses release the camera and
        lift the overlay exactly as for a manual pause; then the resume timer
        is armed. Snoozing again simply rearms with the new duration.
        """
        lo, hi = SNOOZE_MINUTES_RANGE
        minutes = min(hi, max(lo, int(minutes)))
        self.pause()
        self._update(snoozed_until_ms=time.monotonic() * 1000.0 + minutes * 60_000.0)
        self._snooze_timer.start(minutes * 60_000)

    def _on_snooze_elapsed(self) -> None:
        """Auto-resume at the end of a snooze (no-op if the user acted meanwhile)."""
        if self._snap.snoozed_until_ms is None or self._snap.running:
            return
        self.enable()

    @Slot(str)
    def set_masking_strategy(self, strategy: str) -> None:
        """Set the configured masking strategy (UI only offers the live ones)."""
        self._update(masking_strategy=strategy)

    @Slot(float)
    def set_opacity(self, opacity: float) -> None:
        """Set the veil opacity, clamped to ``[0, 1]``."""
        self._update(opacity=min(1.0, max(0.0, float(opacity))))

    @Slot(int)
    def set_blur_radius(self, radius: int) -> None:
        """Set the blur radius, clamped to the config bounds."""
        lo, hi = BLUR_RADIUS_RANGE
        self._update(blur_radius=min(hi, max(lo, int(radius))))

    @Slot(int)
    def set_pixelate_blocks(self, blocks: int) -> None:
        """Set the pixelation block count, clamped to the config bounds."""
        lo, hi = PIXELATE_BLOCKS_RANGE
        self._update(pixelate_blocks=min(hi, max(lo, int(blocks))))

    @Slot(float)
    def set_sensitivity_deg(self, deg: float) -> None:
        """Set the gaze tolerance in degrees (higher = masks more readily), clamped."""
        lo, hi = SENSITIVITY_DEG_RANGE
        self._update(sensitivity_deg=min(hi, max(lo, float(deg))))

    @Slot(int)
    def set_trigger_ms(self, ms: int) -> None:
        """Set the trigger delay; raises the release delay to keep ``release >= trigger``."""
        ms = max(0, int(ms))
        release = max(self._snap.release_ms, ms)
        self._update(trigger_ms=ms, release_ms=release)

    @Slot(int)
    def set_release_ms(self, ms: int) -> None:
        """Set the release delay, clamped to never fall below the trigger delay."""
        self._update(release_ms=max(int(ms), self._snap.trigger_ms))

    @Slot(int)
    def set_absence_lock_ms(self, ms: int) -> None:
        """Set the walk-away lock delay in ms (0 disables it), clamped to sane bounds.

        Opt-in on purpose: it changes *when* the screen hides, so the user decides.
        """
        ms = int(ms)
        if ms <= 0:
            self._update(absence_lock_ms=0)
            return
        lo, hi = ABSENCE_LOCK_MS_RANGE
        self._update(absence_lock_ms=min(hi, max(lo, ms)))

    @Slot(float)
    def set_smoothing_alpha(self, alpha: float) -> None:
        """Set the EMA smoothing on the observer signal, clamped to ``(0, 1]``.

        Higher = more reactive (1.0 disables smoothing entirely). Lower trades
        latency for fewer spurious triggers — and that latency adds to
        ``trigger_ms``, which is exactly what AM-11 makes visible and adjustable.
        """
        lo, hi = SMOOTHING_ALPHA_RANGE
        self._update(smoothing_alpha=min(hi, max(lo, float(alpha))))

    @Slot(int)
    def select_camera(self, index: int) -> None:
        """Choose which camera device index to use."""
        self._update(camera_index=max(0, int(index)))

    @Slot(bool)
    def set_start_at_login(self, value: bool) -> None:
        """Toggle 'start at login' (the shell persists/applies it)."""
        self._update(start_at_login=bool(value))

    @Slot(bool)
    def set_preview_enabled(self, enabled: bool) -> None:
        """Show/hide the live camera preview. Turning it on also resumes watching."""
        enabled = bool(enabled)
        if enabled and not self._snap.running:
            self._update(running=True, preview_enabled=True)
        else:
            self._update(preview_enabled=enabled)

    @Slot()
    def toggle_preview(self) -> None:
        """Toggle the live camera preview."""
        self.set_preview_enabled(not self._snap.preview_enabled)

    @Slot()
    def open_settings(self) -> None:
        """Ask the shell to open the settings window."""
        self.settings_requested.emit()

    @Slot()
    def open_about(self) -> None:
        """Ask the shell to open the about/limits window."""
        self.about_requested.emit()

    @Slot()
    def finish_onboarding(self) -> None:
        """Signal that first-run onboarding is complete."""
        self.onboarding_finished.emit()

    @Slot()
    def quit(self) -> None:
        """Ask the shell to quit the application."""
        self.quit_requested.emit()

    # ------------------------------------------------------------------ #
    # test/integration hooks for subclasses & fakes
    # ------------------------------------------------------------------ #
    def report_camera_active(self, active: bool) -> None:
        """Subclass hook: the camera started/stopped delivering frames."""
        self._update(camera_active=active)

    def report_error(self, error: CameraError | None) -> None:
        """Subclass hook: a camera/detection error appeared or cleared."""
        self._update(error_kind=error)
