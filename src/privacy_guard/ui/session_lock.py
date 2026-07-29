"""Suspend watching while the session is locked (AM-14).

M-R1 taught the app to survive suspend/resume, but nothing reacted to the screen
being **locked**: the webcam kept producing frames to analyse when there was
nothing left to protect. That costs CPU and battery — and, worse for a privacy
tool, it leaves the camera indicator lit on a locked machine, which is exactly
the kind of thing that makes a user distrust the app.

Two halves, as usual:

* :class:`SessionSuspender` — the decision, pure and fully tested. Its whole job
  is to restore *exactly* the state the user had chosen: a session that was
  already paused must not come back running because the screen was locked.
* the platform monitors — thin adapters over each OS's lock signal, every one of
  them wrapped so that an unavailable mechanism degrades to "no monitoring"
  rather than breaking startup.

**Honest coverage.** Windows and Linux (logind) are implemented; macOS is not —
its lock notification needs a native API PySide6 does not expose, and shipping a
half-working guess would be worse than saying so. On macOS (and anywhere the
mechanism is missing) watching simply keeps running while locked, exactly as
before.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable

logger = logging.getLogger("privacy_guard.ui")

# Windows: wParam values of WM_WTSSESSION_CHANGE we care about.
_WM_WTSSESSION_CHANGE = 0x02B1
_WTS_SESSION_LOCK = 0x7
_WTS_SESSION_UNLOCK = 0x8
_NOTIFY_FOR_THIS_SESSION = 0


class SessionSuspender:
    """Pauses watching on lock and restores what the user had on unlock.

    Args:
        is_running: Reads whether watching is currently on.
        pause: Stops watching (releases the camera).
        resume: Restarts watching.
    """

    def __init__(
        self,
        is_running: Callable[[], bool],
        pause: Callable[[], None],
        resume: Callable[[], None],
    ) -> None:
        """Start out not suspended."""
        self._is_running = is_running
        self._pause = pause
        self._resume = resume
        self._suspended = False
        self._was_running = False

    @property
    def is_suspended(self) -> bool:
        """Whether watching is currently held down by a session lock."""
        return self._suspended

    def on_locked(self) -> None:
        """The session was locked: stop watching if it was on.

        Idempotent: some platforms emit the lock signal more than once, and a
        second one must not overwrite the memory of what to restore.
        """
        if self._suspended:
            return
        self._suspended = True
        self._was_running = bool(self._is_running())
        if self._was_running:
            logger.info("Session locked: pausing watching until it is unlocked.")
            self._pause()

    def on_unlocked(self) -> None:
        """The session was unlocked: resume only if we are the one who paused."""
        if not self._suspended:
            return
        self._suspended = False
        if self._was_running:
            logger.info("Session unlocked: resuming watching.")
            self._resume()
        self._was_running = False


def install_session_lock_monitor(
    app: object, suspender: SessionSuspender
) -> bool:  # pragma: no cover - OS integration, verified manually
    """Wire the platform's lock/unlock signal to ``suspender``.

    Returns:
        ``True`` if a monitor is active. ``False`` means watching will keep
        running while the session is locked — the caller logs that rather than
        letting the user assume otherwise.
    """
    try:
        if sys.platform == "win32":
            return _install_windows_monitor(app, suspender)
        if sys.platform.startswith("linux"):
            return _install_logind_monitor(suspender)
    except Exception as exc:  # never let session monitoring break startup
        logger.warning("Session-lock monitoring unavailable: %s", exc)
        return False
    logger.info("No session-lock monitoring on this platform; watching stays on when locked.")
    return False


def _install_logind_monitor(
    suspender: SessionSuspender,
) -> bool:  # pragma: no cover - needs a session bus
    """Subscribe to systemd-logind's ``Lock``/``Unlock`` signals over D-Bus."""
    from PySide6.QtDBus import QDBusConnection

    bus = QDBusConnection.systemBus()
    if not bus.isConnected():
        logger.info("No system D-Bus; session-lock monitoring is off.")
        return False

    class _Handler:
        def locked(self) -> None:
            suspender.on_locked()

        def unlocked(self) -> None:
            suspender.on_unlocked()

    handler = _Handler()
    ok_lock = bus.connect(
        "org.freedesktop.login1",
        "",
        "org.freedesktop.login1.Session",
        "Lock",
        handler.locked,
    )
    ok_unlock = bus.connect(
        "org.freedesktop.login1",
        "",
        "org.freedesktop.login1.Session",
        "Unlock",
        handler.unlocked,
    )
    if not (ok_lock and ok_unlock):
        logger.info("logind Lock/Unlock signals unavailable; session-lock monitoring is off.")
        return False
    # The handler must outlive this function or the D-Bus connection calls into
    # a collected object.
    _KEEPALIVE.append(handler)
    logger.info("Session-lock monitoring active (logind).")
    return True


def _install_windows_monitor(
    app: object, suspender: SessionSuspender
) -> bool:  # pragma: no cover - Windows only
    """Register for ``WM_WTSSESSION_CHANGE`` and filter it out of the Qt loop."""
    import ctypes

    from PySide6.QtCore import QAbstractNativeEventFilter
    from PySide6.QtWidgets import QWidget

    # A hidden window gives us an HWND to receive the session notifications on.
    sink = QWidget()
    sink.hide()
    hwnd = int(sink.winId())
    wtsapi = ctypes.windll.wtsapi32  # type: ignore[attr-defined]
    if not wtsapi.WTSRegisterSessionNotification(hwnd, _NOTIFY_FOR_THIS_SESSION):
        logger.info("WTSRegisterSessionNotification refused; session-lock monitoring is off.")
        return False

    class _MSG(ctypes.Structure):
        """The Win32 ``MSG`` struct Qt hands us as an opaque pointer."""

        _fields_ = [
            ("hwnd", ctypes.c_void_p),
            ("message", ctypes.c_uint),
            ("wParam", ctypes.c_void_p),
            ("lParam", ctypes.c_void_p),
            ("time", ctypes.c_uint),
            ("pt_x", ctypes.c_long),
            ("pt_y", ctypes.c_long),
        ]

    class _Filter(QAbstractNativeEventFilter):
        def nativeEventFilter(self, event_type: object, message: object) -> tuple[bool, int]:
            try:
                msg = ctypes.cast(int(message), ctypes.POINTER(_MSG)).contents
                if msg.message == _WM_WTSSESSION_CHANGE:
                    if msg.wParam == _WTS_SESSION_LOCK:
                        suspender.on_locked()
                    elif msg.wParam == _WTS_SESSION_UNLOCK:
                        suspender.on_unlocked()
            except Exception:  # a malformed message must not kill the event loop
                logger.debug("Ignoring an unreadable native event.", exc_info=True)
            return (False, 0)  # never swallow the message

    event_filter = _Filter()
    app.installNativeEventFilter(event_filter)  # type: ignore[attr-defined]
    _KEEPALIVE.extend((sink, event_filter))
    logger.info("Session-lock monitoring active (Windows session notifications).")
    return True


# Objects the OS callbacks reference; they must not be garbage-collected.
_KEEPALIVE: list[object] = []
