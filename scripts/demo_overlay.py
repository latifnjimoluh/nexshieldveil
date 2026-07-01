"""Démo manuelle M-FP4 : voile -> capture -> flou/pixelisation -> levée.

Vérification visuelle sur une vraie machine (hors CI) :

    python scripts/demo_overlay.py                 # blur, 5 s
    python scripts/demo_overlay.py --strategy pixelate --seconds 8
    python scripts/demo_overlay.py --strategy veil

À vérifier à la main :
- chaque écran est couvert (multi-moniteur), y compris sous DPI 100 %/150 % ;
- le voile opaque apparaît IMMÉDIATEMENT, puis l'image floutée/pixelisée de
  l'écran fond dessus (~120 ms) ; le panneau cadenas reste lisible par-dessus ;
- la fenêtre est click-through (on ne peut pas cliquer l'overlay) ;
- à la levée, tout disparaît et rien n'est écrit sur disque.

La capture reste en RAM et est libérée à la levée (P2) ; une seule capture par
engagement (P3) ; tout échec retombe sur le voile opaque (P4).
"""

from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from privacy_guard.config import MaskingConfig
from privacy_guard.masking import make_mask_strategy
from privacy_guard.overlay import (
    FreezeFrameCompositor,
    QtMaskPresenter,
    QtScreenGrabber,
    QtTransformExecutor,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", choices=["blur", "pixelate", "veil"], default="blur")
    parser.add_argument("--seconds", type=float, default=5.0, help="durée du masquage")
    parser.add_argument("--fade-ms", type=int, default=120, help="0 = sans animation")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    strategy = None
    if args.strategy != "veil":
        strategy = make_mask_strategy(MaskingConfig(strategy=args.strategy))

    compositor = FreezeFrameCompositor(
        grabber=QtScreenGrabber(),
        strategy=strategy,
        presenter=QtMaskPresenter(fade_ms=args.fade_ms),
        executor=QtTransformExecutor(),
    )

    print(f"Masquage '{args.strategy}' pendant {args.seconds:.1f} s...")
    compositor.engage()

    def lift() -> None:
        compositor.disengage()
        print("Masque levé.")
        QTimer.singleShot(400, app.quit)

    QTimer.singleShot(int(args.seconds * 1000), lift)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
