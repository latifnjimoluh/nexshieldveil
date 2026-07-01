"""The live application shell: tray (primary surface) + QML windows, wired to the core.

This is display/hardware glue (like the legacy ``control_window``), so it is excluded
from coverage. All presentation logic it relies on lives in the unit-tested
view-models; the shell only constructs objects and connects signals.

Privacy: this module opens no network and writes no image. Preferences persist via
``QSettings`` only. The detection/masking work happens in :class:`CoreController`'s
worker thread, never on the UI thread.
"""

from __future__ import annotations

import argparse
import logging
import sys

from privacy_guard.config import AppConfig, load_config
from privacy_guard.resources import default_model_path

logger = logging.getLogger("privacy_guard.ui")


_VIEWS = (
    "GlassPanel.qml",
    "PrimaryButton.qml",
    "StatusPill.qml",
    "CameraBadge.qml",
    "Veil.qml",
    "StatusView.qml",
    "AboutView.qml",
    "OnboardingView.qml",
    "SettingsView.qml",
    "CameraView.qml",
    "MainView.qml",
)


def _selfcheck() -> int:  # pragma: no cover - exercised via the frozen build smoke test
    """Load every QML view offscreen and exit 0. Validates a (frozen) build's wiring."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    from privacy_guard.ui.fake_controller import FakeController
    from privacy_guard.ui.preview import CameraImageProvider
    from privacy_guard.ui.qml_app import install_context, view_url
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

    QGuiApplication.instance() or QGuiApplication([])
    controller = FakeController()
    translator = Translator("fr")
    theme = ThemeController()
    provider = CameraImageProvider()
    engine = QQmlEngine()
    engine.addImageProvider(CameraImageProvider.PROVIDER_ID, provider)
    install_context(
        engine.rootContext(),
        theme=theme,
        translator=translator,
        status=StatusViewModel(controller, translator),
        settings=SettingsViewModel(controller, translator),
        onboarding=OnboardingViewModel(controller, translator),
        about=AboutViewModel(translator),
        tray=TrayViewModel(controller, translator),
        camera=CameraViewModel(controller, translator, provider),
    )
    for view in _VIEWS:
        component = QQmlComponent(engine, view_url(view))
        obj = component.create()
        if obj is None:
            errors = "; ".join(e.toString() for e in component.errors())
            print(f"SELFCHECK FAIL: {view}: {errors}", file=sys.stderr)
            return 1
    print(f"SELFCHECK OK: {len(_VIEWS)} views loaded.")
    return 0


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - requires a display
    """Launch the QML desktop UI wired to the real core."""
    parser = argparse.ArgumentParser(description="NexShieldVeil — interface QML (MVVM).")
    parser.add_argument("-c", "--config", help="Optional TOML config file.")
    parser.add_argument("--light", action="store_true", help="Start in the light theme.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Self-test: load every QML view and exit (used to validate the build).",
    )
    args = parser.parse_args(argv)

    if args.check:
        return _selfcheck()

    try:
        from PySide6.QtCore import QLocale, QSettings
        from PySide6.QtQuick import QQuickView
        from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
    except ImportError:
        print(
            'PySide6 manquant. Installe les extras :  pip install -e ".[vision,ui]"',
            file=sys.stderr,
        )
        return 1

    from privacy_guard.ui.core_controller import CoreController
    from privacy_guard.ui.fonts import load_bundled_fonts
    from privacy_guard.ui.i18n_catalog import normalize_language
    from privacy_guard.ui.preview import CameraImageProvider
    from privacy_guard.ui.qml_app import install_context, view_url
    from privacy_guard.ui.theme.theme_controller import ThemeController
    from privacy_guard.ui.translator import Translator
    from privacy_guard.ui.updater_ui import shield_icon
    from privacy_guard.ui.viewmodels import (
        AboutViewModel,
        CameraViewModel,
        OnboardingViewModel,
        SettingsViewModel,
        StatusViewModel,
        TrayViewModel,
    )

    logging.basicConfig(level=logging.INFO)
    config = load_config(args.config) if args.config else AppConfig()
    model_path = config.detection.model_path or default_model_path()

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("NexShieldVeil")
    app.setQuitOnLastWindowClosed(False)  # tray app: closing a window must not quit
    load_bundled_fonts()

    settings = QSettings("NexShieldVeil", "NexShieldVeil")
    lang = normalize_language(str(settings.value("language", QLocale().name())))
    translator = Translator(lang)
    theme = ThemeController(dark=not args.light)

    # Reduced motion also disables the overlay's veil->frame crossfade (the
    # masking itself is never animated; only the cosmetic swap after it is).
    controller = CoreController(config, model_path, fade_ms=0 if theme.reduced_motion else 120)
    provider = CameraImageProvider()
    status_vm = StatusViewModel(controller, translator)
    settings_vm = SettingsViewModel(controller, translator)
    onboarding_vm = OnboardingViewModel(controller, translator)
    about_vm = AboutViewModel(translator)
    tray_vm = TrayViewModel(controller, translator)
    camera_vm = CameraViewModel(controller, translator, provider)

    translator.language_changed.connect(lambda: settings.setValue("language", translator.language))
    # Live preview frames (emitted only while the preview is on) -> the camera VM.
    controller.frame_ready.connect(camera_vm.push_frame)

    windows: dict[str, QQuickView] = {}

    def show_window(name: str, view: str, width: int, height: int) -> None:
        if name not in windows:
            v = QQuickView()
            # Only the main window renders the live preview; one engine owns the provider.
            if view == "MainView.qml":
                v.engine().addImageProvider(CameraImageProvider.PROVIDER_ID, provider)
            install_context(
                v.engine().rootContext(),
                theme=theme,
                translator=translator,
                status=status_vm,
                settings=settings_vm,
                onboarding=onboarding_vm,
                about=about_vm,
                tray=tray_vm,
                camera=camera_vm,
            )
            v.setColor(theme.base)
            v.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
            v.setTitle("NexShieldVeil")
            v.resize(width, height)
            v.setSource(view_url(view))
            windows[name] = v
        win = windows[name]
        win.show()
        win.raise_()
        win.requestActivate()

    # ---- tray (primary surface) ----------------------------------------- #
    tray = QSystemTrayIcon(shield_icon(), app)
    menu = QMenu()
    act_toggle = menu.addAction(tray_vm.property("toggle_label"))
    act_toggle.triggered.connect(controller.toggle)
    menu.addSeparator()
    act_status = menu.addAction(translator.tr_key("action.open"))
    act_status.triggered.connect(lambda: show_window("main", "MainView.qml", 480, 460))
    act_settings = menu.addAction(tray_vm.property("settings_label"))
    act_settings.triggered.connect(lambda: show_window("settings", "SettingsView.qml", 600, 660))
    act_about = menu.addAction(tray_vm.property("about_label"))
    act_about.triggered.connect(lambda: show_window("about", "AboutView.qml", 500, 540))
    menu.addSeparator()
    act_quit = menu.addAction(tray_vm.property("quit_label"))
    act_quit.triggered.connect(app.quit)
    tray.setContextMenu(menu)

    def relabel() -> None:
        act_toggle.setText(tray_vm.property("toggle_label"))
        act_status.setText(translator.tr_key("action.open"))
        act_settings.setText(tray_vm.property("settings_label"))
        act_about.setText(tray_vm.property("about_label"))
        act_quit.setText(tray_vm.property("quit_label"))
        tray.setToolTip(tray_vm.property("tooltip"))

    tray_vm.changed.connect(relabel)
    relabel()
    tray.show()

    controller.settings_requested.connect(
        lambda: show_window("settings", "SettingsView.qml", 600, 660)
    )
    controller.about_requested.connect(lambda: show_window("about", "AboutView.qml", 500, 540))
    controller.quit_requested.connect(app.quit)
    app.aboutToQuit.connect(controller.shutdown)

    # Error actions the status surface defers to the shell (a user-initiated click;
    # no network by us — just opens the OS camera settings or the local docs).
    def on_error_action(action: str) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        if action == "open_system_settings":
            target = {
                "win32": "ms-settings:privacy-webcam",
                "darwin": "x-apple.systempreferences:com.apple.preference.security?Privacy_Camera",
            }.get(sys.platform, "")
            if target:
                QDesktopServices.openUrl(QUrl(target))
        elif action == "open_docs":
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(default_model_path())))

    status_vm.action_requested.connect(on_error_action)

    def open_main() -> None:
        show_window("main", "MainView.qml", 480, 460)

    # ---- first run: onboarding (camera opened only after explicit consent) ---- #
    if not settings.value("onboarding_done", False, type=bool):

        def finish_onboarding() -> None:
            settings.setValue("onboarding_done", True)
            if "onboarding" in windows:
                windows["onboarding"].close()
            open_main()  # then surface the main interface (preview stays off)

        controller.onboarding_finished.connect(finish_onboarding)
        show_window("onboarding", "OnboardingView.qml", 560, 540)
    else:
        # Background protection starts; the camera *preview* stays off until requested.
        controller.enable()
        open_main()

    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
