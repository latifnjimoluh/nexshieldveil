"""Interactive live runner for NexShieldVeil / privacy-guard.

This is a *developer/manual-test* harness (not part of the shipped package). It wires
the real webcam + MediaPipe detector + Qt overlay together and pumps the Qt event
loop each frame so the veil actually paints. It also shows an OpenCV preview window
with the live decision state so you can see detection working.

Honest scope: this reduces shoulder-surfing risk; it cannot change how light leaves
the screen. See docs/LIMITATIONS.md. No frame is ever written to disk or sent anywhere.

Usage (from the repo root, with the [vision,ui] extras installed):

    python scripts/run_live.py                 # normal: your face = primary (exempt)
    python scripts/run_live.py --solo-test     # solo: ANY face looking triggers the veil
    python scripts/run_live.py --device 1       # pick another webcam
    python scripts/run_live.py --no-preview     # hide the OpenCV preview window

Press 'q' in the preview window (or Ctrl+C in the terminal) to quit.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

from privacy_guard.capture import WebcamFrameSource
from privacy_guard.config import AppConfig, load_config
from privacy_guard.geometry import (
    ScreenModel,
    gaze_points_at_screen,
    gaze_vector,
    select_primary_user,
)
from privacy_guard.overlay import QtOverlayRenderer
from privacy_guard.policy import DecisionStateMachine, PolicyState
from privacy_guard.tracking import ExponentialSmoother
from privacy_guard.vision import MediaPipeFaceDetector

DEFAULT_MODEL = "models/face_landmarker.task"

_STATE_COLOR = {
    PolicyState.CLEAR: (0, 200, 0),
    PolicyState.OBSERVER_DETECTED: (0, 180, 255),
    PolicyState.MASKED: (0, 0, 255),
}


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live interactive runner for NexShieldVeil.")
    p.add_argument("-c", "--config", help="Optional TOML config file.")
    p.add_argument("--device", type=int, default=None, help="Webcam device index.")
    p.add_argument(
        "--solo-test",
        action="store_true",
        help="Treat ANY looking face as an observer (no primary-user exemption) so you "
        "can test alone: look at the screen to mask, look away to unmask.",
    )
    p.add_argument("--no-preview", action="store_true", help="Do not open the OpenCV preview.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config) if args.config else AppConfig()

    model_path = config.detection.model_path or DEFAULT_MODEL
    if not Path(model_path).is_file():
        print(f"[ERREUR] Modèle MediaPipe introuvable : {model_path}", file=sys.stderr)
        print("        Place face_landmarker.task dans models/ (voir README).", file=sys.stderr)
        return 1

    device = args.device if args.device is not None else config.camera.device_index

    source = WebcamFrameSource(device)
    if not source.is_available:
        print(f"[ERREUR] Impossible d'ouvrir la webcam (device {device}).", file=sys.stderr)
        return 1
    detector = MediaPipeFaceDetector(
        model_path=model_path,
        max_faces=config.detection.max_faces,
        min_confidence=config.detection.min_detection_confidence,
    )
    renderer = QtOverlayRenderer(opacity=config.masking.opacity)

    screen = ScreenModel(
        width_mm=config.geometry.screen_width_mm,
        height_mm=config.geometry.screen_height_mm,
        camera_above_mm=config.geometry.camera_above_screen_mm,
    )
    tol = config.geometry.gaze_tolerance_deg
    smoother = ExponentialSmoother(config.tracking.smoothing_alpha)
    policy = DecisionStateMachine.from_config(config.policy)

    mode = (
        "SOLO (tout visage qui regarde masque)"
        if args.solo_test
        else "NORMAL (ton visage = principal, exempté)"
    )
    print(f"NexShieldVeil — live.  Mode : {mode}")
    print("Le voile recouvre l'écran quand un observateur regarde. 'q' = quitter.")
    print("Rappel : réduit le risque, ne garantit pas la confidentialité (docs/LIMITATIONS.md).")

    try:
        while True:
            frame = source.read()
            if frame is None:
                break
            observations = detector.detect(frame)

            looking = []
            for obs in observations:
                hit = obs.gaze_estimable and gaze_points_at_screen(
                    obs.position_mm, gaze_vector(obs.yaw_deg, obs.pitch_deg), screen, tol
                )
                looking.append(hit)

            primary_index: int | None = None
            if observations and not args.solo_test:
                primary_index = select_primary_user(
                    [o.to_candidate() for o in observations],
                    centrality_weight=config.primary_user.centrality_weight,
                    size_weight=config.primary_user.size_weight,
                )

            observer_raw = any(hit for i, hit in enumerate(looking) if i != primary_index)
            confidence = float(smoother.update(1.0 if observer_raw else 0.0))
            state = policy.update(confidence >= 0.5, frame.timestamp_ms)
            renderer.set_masked(policy.is_masked)
            renderer._app.processEvents()  # keep the veil painted every frame

            if not args.no_preview:
                img = frame.image.copy()
                h, w = img.shape[:2]
                for i, obs in enumerate(observations):
                    cx, cy = int(obs.center_x * w), int(obs.center_y * h)
                    if i == primary_index:
                        col, tag = (180, 180, 180), "principal"
                    elif looking[i]:
                        col, tag = (0, 0, 255), "REGARDE"
                    else:
                        col, tag = (0, 200, 0), "ne regarde pas"
                    cv2.circle(img, (cx, cy), 28, col, 2)
                    cv2.putText(
                        img,
                        tag,
                        (cx - 40, cy - 36),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        col,
                        1,
                        cv2.LINE_AA,
                    )
                banner = f"{state.name}  |  visages={len(observations)}  |  {'MASQUE' if policy.is_masked else 'clair'}"
                cv2.rectangle(img, (0, 0), (w, 30), (0, 0, 0), -1)
                cv2.putText(
                    img,
                    banner,
                    (8, 21),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    _STATE_COLOR[state],
                    2,
                    cv2.LINE_AA,
                )
                cv2.imshow("NexShieldVeil (live) - 'q' pour quitter", img)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            else:
                time.sleep(0.005)
    except KeyboardInterrupt:
        print("\nArrêt.")
    finally:
        source.close()
        detector.close()
        renderer.close()
        if not args.no_preview:
            cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
