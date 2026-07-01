"""Screen-capture interface for the freeze-frame masking path (M-FP2).

The blur/pixelate strategies need on-screen pixels to transform. This module
defines the *contract* only — a pure, headless-testable interface plus the
scriptable fake every higher layer tests against. The real Qt adapter lives in
:mod:`privacy_guard.overlay.qt_grabber`.

Privacy rules (P2/P3, docs/ROADMAP_FLOU_PIXELISATION.md): a screen frame is
*more* sensitive than a camera frame — it contains the very content the product
protects. A grab happens once per masking engagement (never a continuous
stream), the frame lives in RAM only, and callers must drop every reference to
it when the mask lifts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

Image = NDArray[np.uint8]

# A capture with less pixel spread than this is a flat frame (locked screen,
# DRM-protected content, or a failing driver): nothing to blur, so the caller
# falls back to the opaque veil (P4). Real desktop content — even a mostly
# empty document — has text/window chrome and lands far above this.
_BLANK_STD_THRESHOLD = 2.0


def _validate_image(image: Image) -> None:
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8 or image.size == 0:
        msg = f"Expected a non-empty (H, W, 3) uint8 image, got shape {image.shape} {image.dtype}"
        raise ValueError(msg)


def looks_blank(image: Image, max_std: float = _BLANK_STD_THRESHOLD) -> bool:
    """Whether a capture is (near-)uniform, i.e. carries no maskable content."""
    _validate_image(image)
    return float(image.std()) <= max_std


@dataclass(frozen=True)
class ScreenShot:
    """One captured screen: physical pixels + the screen's virtual-desktop geometry.

    ``x``/``y``/``width``/``height`` are the *logical* geometry Qt uses to place
    the overlay window on that screen; ``image`` is in physical pixels, so its
    shape may differ from ``width``/``height`` under DPI scaling.
    """

    image: Image
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        """Reject anything that is not a non-empty (H, W, 3) uint8 array."""
        _validate_image(self.image)


class ScreenGrabber(ABC):
    """Captures every screen of the virtual desktop, once per call."""

    @abstractmethod
    def grab_all(self) -> list[ScreenShot]:
        """One :class:`ScreenShot` per screen, or ``[]`` if the capture failed.

        An empty list is the *only* failure signal (P4): implementations must
        never raise for environmental reasons (no screens, OS refusal, ...).
        """


def _default_shot() -> ScreenShot:
    # A deterministic gradient: clearly non-blank, no randomness in tests.
    ramp_y = np.arange(48, dtype=np.uint16)[:, None]
    ramp_x = np.arange(64, dtype=np.uint16)[None, :]
    image = np.stack(
        [
            (ramp_y * 4 % 256).repeat(64, axis=1),
            (ramp_x * 3 % 256).repeat(48, axis=0),
            ((ramp_y + ramp_x) * 2 % 256),
        ],
        axis=2,
    ).astype(np.uint8)
    return ScreenShot(image=image, x=0, y=0, width=64, height=48)


@dataclass
class FakeScreenGrabber(ScreenGrabber):
    """Scriptable in-memory grabber: the test double for every capture consumer.

    ``fail=True`` simulates an OS-level capture failure (returns ``[]``);
    ``shots`` overrides the captured screens; ``calls`` counts grab attempts so
    tests can assert the one-grab-per-engagement rule (P3).
    """

    shots: list[ScreenShot] = field(default_factory=lambda: [_default_shot()])
    fail: bool = False
    calls: int = 0

    def grab_all(self) -> list[ScreenShot]:
        """Return the scripted shots, or ``[]`` when scripted to fail."""
        self.calls += 1
        return [] if self.fail else list(self.shots)
