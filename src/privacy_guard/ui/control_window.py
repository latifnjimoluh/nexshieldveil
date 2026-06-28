"""PySide6 control window: live preview + status + controls (optional, degradable).

This is the user-facing desktop app. It runs the capture -> vision -> geometry ->
tracking -> policy -> overlay flow on a QTimer (a real Qt event loop, addressing the
deferred CONC-1 runtime-concurrency item), shows a styled camera preview with the
decision state, and drives the veil overlay.

Honest scope: it reduces shoulder-surfing risk; it cannot change how light leaves the
screen (see docs/LIMITATIONS.md). All processing is local; no frame is written to disk
or sent anywhere by this code (third-party libraries may have their own telemetry —
see docs/PRIVACY.md).

Requires the [vision, ui] extras and a local MediaPipe model. The heavy Qt code needs
a display and is excluded from coverage; the pure helpers live in ui.status.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from privacy_guard.config import AppConfig, load_config
from privacy_guard.resources import default_model_path
from privacy_guard.ui.status import face_tag, sensitivity_descriptor, status_badge

try:  # pragma: no cover - import guard
    import cv2
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QAction, QBrush, QColor, QFont, QImage, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMenu,
        QPushButton,
        QSlider,
        QSystemTrayIcon,
        QVBoxLayout,
        QWidget,
    )

    _UI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _UI_AVAILABLE = False

_STYLESHEET = """
QMainWindow, QWidget { background: #16181d; color: #e8e8ea; }
QLabel#preview { background: #0c0d10; border: 1px solid #2a2d34; border-radius: 10px; }
QLabel#badge { font-size: 15px; font-weight: 700; padding: 6px 14px;
               border-radius: 14px; color: #fff; }
QLabel#meta { color: #9aa0a6; font-size: 12px; }
QLabel#disclaimer { color: #6b7077; font-size: 11px; }
QPushButton { background: #2563eb; color: white; border: none; padding: 8px 18px;
              border-radius: 8px; font-weight: 600; }
QPushButton:hover { background: #1d4ed8; }
QPushButton#stop { background: #3a3d44; }
QPushButton#stop:hover { background: #4a4e57; }
QCheckBox { color: #c8ccd2; }
QSlider::groove:horizontal { height: 6px; background: #2a2d34; border-radius: 3px; }
QSlider::handle:horizontal { background: #2563eb; width: 16px; margin: -6px 0; border-radius: 8px; }
"""


if _UI_AVAILABLE:  # pragma: no cover - requires a display
    from privacy_guard.capture import WebcamFrameSource
    from privacy_guard.geometry import (
        ScreenModel,
        gaze_points_at_screen,
        gaze_vector,
        select_primary_user,
    )
    from privacy_guard.overlay import QtOverlayRenderer
    from privacy_guard.policy import DecisionStateMachine, PolicyState
    from privacy_guard.tracking import ExponentialSmoother
    from privacy_guard.ui.updater_ui import (
        SettingsDialog,
        UpdateCheckThread,
        auto_check_enabled,
        shield_icon,
    )
    from privacy_guard.vision import MediaPipeFaceDetector

    class ControlWindow(QMainWindow):
        """Main control window for NexShieldVeil."""

        def __init__(self, config: AppConfig, model_path: str, device: int) -> None:
            """Build the control window (camera starts only when the user clicks Start)."""
            super().__init__()
            self._config = config
            self._model_path = model_path
            self._device = device
            self._solo = False
            self._tolerance = config.geometry.gaze_tolerance_deg

            self._source: WebcamFrameSource | None = None
            self._detector: MediaPipeFaceDetector | None = None
            self._overlay: QtOverlayRenderer | None = None
            self._screen = ScreenModel(
                width_mm=config.geometry.screen_width_mm,
                height_mm=config.geometry.screen_height_mm,
                camera_above_mm=config.geometry.camera_above_screen_mm,
            )
            self._smoother = ExponentialSmoother(config.tracking.smoothing_alpha)
            self._policy = DecisionStateMachine.from_config(config.policy)

            self._timer = QTimer(self)
            self._timer.timeout.connect(self._on_tick)

            self._update_info = None
            self._check_thread: UpdateCheckThread | None = None
            self._tray: QSystemTrayIcon | None = None

            self.setWindowTitle("NexShieldVeil")
            self.setWindowIcon(shield_icon())
            self.resize(760, 700)
            self.setStyleSheet(_STYLESHEET)
            self._build_ui()
            self._setup_tray()
            if auto_check_enabled():
                self._start_update_check(silent=True)

        # ---- UI construction -------------------------------------------------
        def _build_ui(self) -> None:
            central = QWidget()
            root = QVBoxLayout(central)
            root.setContentsMargins(18, 16, 18, 14)
            root.setSpacing(12)

            top = QHBoxLayout()
            self._badge = QLabel("ARRÊTÉ")
            self._badge.setObjectName("badge")
            self._badge.setStyleSheet("background:#3a3d44;")
            self._meta = QLabel("Visages : 0")
            self._meta.setObjectName("meta")
            self._settings_btn = QPushButton("Paramètres")
            self._settings_btn.setObjectName("stop")
            self._settings_btn.clicked.connect(self._open_settings)
            top.addWidget(self._badge)
            top.addStretch(1)
            top.addWidget(self._meta)
            top.addWidget(self._settings_btn)
            root.addLayout(top)

            self._preview = QLabel("Appuie sur « Démarrer » pour activer la caméra.")
            self._preview.setObjectName("preview")
            self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._preview.setMinimumHeight(420)
            root.addWidget(self._preview, 1)

            ctrl = QHBoxLayout()
            self._start_btn = QPushButton("Démarrer")
            self._start_btn.clicked.connect(self._toggle)
            ctrl.addWidget(self._start_btn)

            self._solo_box = QCheckBox("Mode test solo")
            self._solo_box.setToolTip(
                "Désactive l'exemption de l'utilisateur principal : ton propre regard "
                "déclenche le voile (pratique pour tester seul)."
            )
            self._solo_box.toggled.connect(self._set_solo)
            ctrl.addWidget(self._solo_box)
            ctrl.addStretch(1)

            sens_tip = (
                "À quel point un autre visage doit viser ton écran pour être considéré "
                "comme « en train de regarder ».\n\n"
                "→ Vers la DROITE = plus méfiant : le voile se déclenche même si la "
                "personne regarde un peu de biais.\n"
                "→ Vers la GAUCHE = plus tolérant : le voile ne se déclenche que si on "
                "fixe vraiment ton écran de face.\n\n"
                "Défaut 18° (équilibré) : volontairement large, car l'estimation du "
                "regard par webcam a déjà quelques degrés d'erreur."
            )
            sens_title = QLabel("Sensibilité du déclenchement")
            sens_title.setToolTip(sens_tip)
            ctrl.addWidget(sens_title)
            self._sens = QSlider(Qt.Orientation.Horizontal)
            self._sens.setMinimum(5)
            self._sens.setMaximum(40)
            self._sens.setValue(int(self._tolerance))
            self._sens.setFixedWidth(160)
            self._sens.setToolTip(sens_tip)
            self._sens.valueChanged.connect(self._set_tolerance)
            ctrl.addWidget(self._sens)
            self._sens_lbl = QLabel()
            self._sens_lbl.setObjectName("meta")
            ctrl.addWidget(self._sens_lbl)
            root.addLayout(ctrl)

            self._sens_hint = QLabel()
            self._sens_hint.setObjectName("meta")
            self._sens_hint.setWordWrap(True)
            root.addWidget(self._sens_hint)
            self._set_tolerance(int(self._tolerance))  # initialise the labels

            disclaimer = QLabel(
                "Réduit le risque de regard indiscret — ne garantit pas la confidentialité. "
                "Traitement 100% local."
            )
            disclaimer.setObjectName("disclaimer")
            disclaimer.setWordWrap(True)
            root.addWidget(disclaimer)

            self.setCentralWidget(central)

        # ---- controls --------------------------------------------------------
        def _set_solo(self, value: bool) -> None:
            self._solo = value

        def _set_tolerance(self, value: int) -> None:
            self._tolerance = float(value)
            descriptor = sensitivity_descriptor(self._tolerance)
            self._sens_lbl.setText(f"{value}° · {descriptor}")
            self._sens_hint.setText(
                "← se masque seulement si on te fixe de face    |    "
                "se masque même si on regarde de biais →"
            )

        def _toggle(self) -> None:
            if self._timer.isActive():
                self._stop()
            else:
                self._start()

        def _start(self) -> None:
            if not Path(self._model_path).is_file():
                self._set_badge(f"Modèle introuvable : {self._model_path}", "#e23b3b")
                return
            try:
                self._source = WebcamFrameSource(self._device)
                if not self._source.is_available:
                    self._set_badge(f"Webcam indisponible (device {self._device})", "#e23b3b")
                    self._source = None
                    return
                self._detector = MediaPipeFaceDetector(
                    model_path=self._model_path,
                    max_faces=self._config.detection.max_faces,
                    min_confidence=self._config.detection.min_detection_confidence,
                )
                self._overlay = QtOverlayRenderer(opacity=self._config.masking.opacity)
            except RuntimeError as exc:
                self._set_badge(f"Erreur : {exc}", "#e23b3b")
                return
            self._smoother = ExponentialSmoother(self._config.tracking.smoothing_alpha)
            self._policy = DecisionStateMachine.from_config(self._config.policy)
            self._start_btn.setText("Arrêter")
            self._start_btn.setObjectName("stop")
            self._start_btn.setStyleSheet("")  # re-evaluate object-name style
            self._timer.start(40)

        def _stop(self) -> None:
            self._timer.stop()
            if self._overlay is not None:
                self._overlay.set_masked(False)
                self._overlay.close()
                self._overlay = None
            if self._detector is not None:
                self._detector.close()
                self._detector = None
            if self._source is not None:
                self._source.close()
                self._source = None
            self._start_btn.setText("Démarrer")
            self._start_btn.setObjectName("")
            self._set_badge("ARRÊTÉ", "#3a3d44")
            self._preview.setText("Caméra arrêtée.")

        # ---- per-frame processing -------------------------------------------
        def _on_tick(self) -> None:
            if self._source is None or self._detector is None or self._overlay is None:
                return
            frame = self._source.read()
            if frame is None:
                self._set_badge("Flux caméra terminé", "#e23b3b")
                self._stop()
                return

            observations = self._detector.detect(frame)
            looking = [
                obs.gaze_estimable
                and gaze_points_at_screen(
                    obs.position_mm,
                    gaze_vector(obs.yaw_deg, obs.pitch_deg),
                    self._screen,
                    self._tolerance,
                )
                for obs in observations
            ]
            primary_index: int | None = None
            if observations and not self._solo:
                primary_index = select_primary_user(
                    [o.to_candidate() for o in observations],
                    centrality_weight=self._config.primary_user.centrality_weight,
                    size_weight=self._config.primary_user.size_weight,
                )
            observer_raw = any(hit for i, hit in enumerate(looking) if i != primary_index)
            confidence = float(self._smoother.update(1.0 if observer_raw else 0.0))
            state = self._policy.update(confidence >= 0.5, frame.timestamp_ms)
            self._overlay.set_masked(self._policy.is_masked)

            self._render_preview(frame.image, observations, looking, primary_index)
            self._update_status(state, self._policy.is_masked, len(observations))

        def _update_status(self, state: PolicyState, masked: bool, n_faces: int) -> None:
            badge = status_badge(state, masked)
            self._set_badge(badge.label, badge.color)
            self._meta.setText(f"Visages : {n_faces}")

        def _set_badge(self, text: str, color: str) -> None:
            self._badge.setText(text)
            self._badge.setStyleSheet(f"background:{color};")

        def _render_preview(self, image, observations, looking, primary_index) -> None:  # noqa: ANN001
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()

            painter = QPainter(qimg)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            label_px = max(14, int(h * 0.033))
            font = QFont()
            font.setPixelSize(label_px)
            font.setBold(True)
            painter.setFont(font)

            for i, obs in enumerate(observations):
                tag = face_tag(is_primary=(i == primary_index), is_looking=looking[i])
                col = QColor(tag.color)
                side = max(math.sqrt(max(obs.size, 1e-4)), 0.12)
                bw, bh = side * w * 1.1, side * h * 1.4
                cx, cy = obs.center_x * w, obs.center_y * h
                x, y = cx - bw / 2, cy - bh / 2
                painter.setPen(QPen(col, max(2, int(h * 0.006))))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(x, y, bw, bh, 12, 12)
                # Tag badge above the box.
                tw = painter.fontMetrics().horizontalAdvance(tag.label) + 16
                th = label_px + 10
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(col))
                painter.drawRoundedRect(x, max(0, y - th - 4), tw, th, 8, 8)
                painter.setPen(QPen(QColor("#ffffff")))
                painter.drawText(int(x + 8), int(max(0, y - th - 4) + label_px + 2), tag.label)
            painter.end()

            pix = QPixmap.fromImage(qimg).scaled(
                self._preview.width(),
                self._preview.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview.setPixmap(pix)

        # ---- tray + updates --------------------------------------------------
        def _setup_tray(self) -> None:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return
            self._tray = QSystemTrayIcon(shield_icon(), self)
            self._tray.setToolTip("NexShieldVeil")
            menu = QMenu()
            act_open = QAction("Ouvrir", self)
            act_open.triggered.connect(self._show_window)
            act_settings = QAction("Paramètres…", self)
            act_settings.triggered.connect(self._open_settings)
            act_quit = QAction("Quitter", self)
            act_quit.triggered.connect(QApplication.quit)
            menu.addAction(act_open)
            menu.addAction(act_settings)
            menu.addSeparator()
            menu.addAction(act_quit)
            self._tray.setContextMenu(menu)
            self._tray.activated.connect(self._on_tray_activated)
            self._tray.show()

        def _on_tray_activated(self, reason: object) -> None:
            if reason == QSystemTrayIcon.ActivationReason.Trigger:
                self._show_window()

        def _show_window(self) -> None:
            self.showNormal()
            self.raise_()
            self.activateWindow()

        def _open_settings(self) -> None:
            dialog = SettingsDialog(self)
            if self._update_info is not None:
                dialog.present_update(self._update_info)
            dialog.exec()

        def _start_update_check(self, *, silent: bool) -> None:
            self._check_thread = UpdateCheckThread(self)
            self._check_thread.found.connect(
                lambda info: self._on_update_found(info, silent=silent)
            )
            self._check_thread.start()

        def _on_update_found(self, info: object, *, silent: bool) -> None:
            self._update_info = info
            if info is None:
                return
            version = getattr(info, "version", "?")
            self._settings_btn.setText("Paramètres ●")
            if self._tray is not None:
                self._tray.showMessage(
                    "NexShieldVeil",
                    f"Mise à jour {version} disponible. Ouvre les Paramètres pour l'installer.",
                    shield_icon(),
                    10000,
                )

        def closeEvent(self, event: object) -> None:
            """Release camera/detector/overlay when the window closes (Qt override)."""
            self._stop()
            if self._tray is not None:
                self._tray.hide()
            super().closeEvent(event)  # type: ignore[arg-type]


def main(argv: list[str] | None = None) -> int:
    """Launch the NexShieldVeil desktop control window."""
    parser = argparse.ArgumentParser(description="NexShieldVeil — desktop control window.")
    parser.add_argument("-c", "--config", help="Optional TOML config file.")
    parser.add_argument("--device", type=int, default=None, help="Webcam device index.")
    args = parser.parse_args(argv)

    if not _UI_AVAILABLE:  # pragma: no cover - exercised only without the extras
        print(
            'PySide6/OpenCV manquants. Installe les extras :  pip install -e ".[vision,ui]"',
            file=sys.stderr,
        )
        return 1

    config = load_config(args.config) if args.config else AppConfig()
    model_path = config.detection.model_path or default_model_path()
    device = args.device if args.device is not None else config.camera.device_index

    app = QApplication.instance() or QApplication(sys.argv)
    window = ControlWindow(config, model_path, device)
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
