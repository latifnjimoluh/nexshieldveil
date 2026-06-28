"""Gaze-decision diagnostic (no veil, screen stays visible).

Why this exists: on real hardware the MediaPipe + solvePnP head-pose does NOT line up
with the synthetic yaw/pitch used in the headless tests, so "looking at the screen"
can be misclassified. This tool prints the *actual* numbers the pipeline sees for the
largest face each frame, then a summary, so we can recalibrate honestly.

It opens NO overlay/veil: the screen stays fully visible the whole time. Just look at
the camera (and optionally hold a photo up) for the duration, then read the summary.

    python scripts/diagnose_gaze.py            # ~12 s, then auto-summary
    python scripts/diagnose_gaze.py --seconds 20

No frame is written to disk or sent anywhere.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

import numpy as np

from privacy_guard.capture import WebcamFrameSource
from privacy_guard.config import AppConfig, load_config
from privacy_guard.geometry import ScreenModel, gaze_points_at_screen, gaze_vector
from privacy_guard.geometry.gaze import (
    angle_between,
    nearest_point_in_rect,
    ray_plane_z_intersection,
)
from privacy_guard.vision import MediaPipeFaceDetector

DEFAULT_MODEL = "models/face_landmarker.task"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Diagnose real gaze decision (no veil).")
    p.add_argument("-c", "--config")
    p.add_argument("--device", type=int, default=None)
    p.add_argument("--seconds", type=float, default=12.0)
    args = p.parse_args(argv)

    config = load_config(args.config) if args.config else AppConfig()
    model_path = config.detection.model_path or DEFAULT_MODEL
    if not Path(model_path).is_file():
        print(f"[ERREUR] Modèle introuvable : {model_path}", file=sys.stderr)
        return 1

    device = args.device if args.device is not None else config.camera.device_index
    source = WebcamFrameSource(device)
    if not source.is_available:
        print(f"[ERREUR] Webcam indisponible (device {device}).", file=sys.stderr)
        return 1
    detector = MediaPipeFaceDetector(
        model_path=model_path,
        max_faces=config.detection.max_faces,
        min_confidence=config.detection.min_detection_confidence,
    )
    screen = ScreenModel(
        width_mm=config.geometry.screen_width_mm,
        height_mm=config.geometry.screen_height_mm,
        camera_above_mm=config.geometry.camera_above_screen_mm,
    )
    tol = config.geometry.gaze_tolerance_deg
    bounds = screen.bounds()

    print(f"Diagnostic ~{args.seconds:.0f}s. Regarde la camera bien en face.")
    print(
        f"Ecran (mm): x[{bounds[0]:.0f},{bounds[1]:.0f}] y[{bounds[2]:.0f},{bounds[3]:.0f}]  "
        f"tolerance={tol:.0f} deg\n"
    )

    yaws: list[float] = []
    pitches: list[float] = []
    looking_count = 0
    frames = 0
    start = time.monotonic()

    try:
        while time.monotonic() - start < args.seconds:
            frame = source.read()
            if frame is None:
                break
            obs_list = detector.detect(frame)
            frames += 1
            if not obs_list:
                print("  (aucun visage)            ", end="\r", flush=True)
                continue
            # Largest face = the one most likely the tester.
            obs = max(obs_list, key=lambda o: o.size)
            g = gaze_vector(obs.yaw_deg, obs.pitch_deg)
            hit = ray_plane_z_intersection(obs.position_mm, g)
            if hit is None:
                in_rect, ang = False, 999.0
            else:
                tx, ty = nearest_point_in_rect(float(hit[0]), float(hit[1]), bounds)
                in_rect = bool(
                    bounds[0] <= hit[0] <= bounds[1] and bounds[2] <= hit[1] <= bounds[3]
                )
                target = np.array([tx, ty, 0.0], dtype=np.float64)
                ang = angle_between(g, target - obs.position_mm)
            # Authoritative decision (matches the live pipeline exactly).
            looking = gaze_points_at_screen(obs.position_mm, g, screen, tol)
            if looking:
                looking_count += 1
            yaws.append(obs.yaw_deg)
            pitches.append(obs.pitch_deg)
            hx = f"{hit[0]:6.0f},{hit[1]:6.0f}" if hit is not None else "  none "
            print(
                f"  n={len(obs_list)} yaw={obs.yaw_deg:+6.1f} pitch={obs.pitch_deg:+6.1f} "
                f"pos=[{obs.position_mm[0]:5.0f},{obs.position_mm[1]:5.0f},{obs.position_mm[2]:5.0f}] "
                f"hit=({hx}) inRect={in_rect!s:5} ang={ang:5.1f} "
                f"-> {'REGARDE' if looking else 'non    '}   ",
                end="\r",
                flush=True,
            )
    except KeyboardInterrupt:
        pass
    finally:
        source.close()
        detector.close()

    print("\n\n===== RESUME =====")
    print(f"Frames                 : {frames}")
    if yaws:
        print(f"Visage vu sur          : {len(yaws)} frames")
        print(f"% frames 'REGARDE'     : {100 * looking_count / max(len(yaws), 1):.0f}%")
        print(
            f"yaw   median/min/max   : {statistics.median(yaws):+.1f} / {min(yaws):+.1f} / {max(yaws):+.1f}"
        )
        print(
            f"pitch median/min/max   : {statistics.median(pitches):+.1f} / {min(pitches):+.1f} / {max(pitches):+.1f}"
        )
        print("\nLecture : en regardant la camera, yaw et pitch devraient etre proches de 0")
        print("et '% REGARDE' eleve. Si yaw/pitch sont grands ou '% REGARDE' bas, la pose")
        print("solvePnP est biaisee -> on recalibre (signe/seuil/tolerance).")
    else:
        print("Aucun visage detecte. Verifie l'eclairage / la webcam / le device.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
