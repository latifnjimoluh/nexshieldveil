"""Derive the shipped brand assets from the source logos.

Reads the two hand-made logos under ``assets/branding/source/`` and produces the
files the app and installer actually load:

* ``icon.png``  — the shield mark, trimmed to its content, centred on a square
  transparent canvas with a small margin (a clean app / tray / window icon).
* ``icon.ico``  — the same mark at every size Windows asks for (Explorer, the
  taskbar, the .exe resource, the Inno installer).
* ``wordmark.png`` — the horizontal lockup (shield + name), trimmed to content,
  for the About and onboarding screens.

Regenerate after changing a source logo::

    python scripts/generate_branding.py

Requires Pillow (already a dev/build dependency via the imaging stack).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

_BRANDING = (
    Path(__file__).resolve().parent.parent / "src" / "privacy_guard" / "ui" / "assets" / "branding"
)
_SOURCE = _BRANDING / "source"

# Windows wants several icon sizes; supplying them all keeps the mark crisp from
# the 16px taskbar tray up to the 256px Explorer tile.
_ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
_ICON_CANVAS = 512  # master PNG side length
_ICON_MARGIN = 0.12  # fraction of the canvas kept clear around the mark


def _trim_to_content(image: Image.Image) -> Image.Image:
    """Crop away fully-transparent borders so the artwork fills the frame."""
    image = image.convert("RGBA")
    bbox = image.split()[3].getbbox()
    return image.crop(bbox) if bbox else image


def _square_icon(source: Image.Image, canvas: int, margin: float) -> Image.Image:
    """Centre the trimmed mark on a square transparent canvas with a margin."""
    mark = _trim_to_content(source)
    inner = int(canvas * (1 - 2 * margin))
    scale = min(inner / mark.width, inner / mark.height)
    mark = mark.resize(
        (max(1, round(mark.width * scale)), max(1, round(mark.height * scale))), Image.LANCZOS
    )
    out = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    out.paste(mark, ((canvas - mark.width) // 2, (canvas - mark.height) // 2), mark)
    return out


def main() -> int:
    icon_src = Image.open(_SOURCE / "icon.png")
    wordmark_src = Image.open(_SOURCE / "wordmark.png")

    icon = _square_icon(icon_src, _ICON_CANVAS, _ICON_MARGIN)
    icon.save(_BRANDING / "icon.png")
    icon.save(_BRANDING / "icon.ico", sizes=_ICO_SIZES)

    wordmark = _trim_to_content(wordmark_src)
    wordmark.save(_BRANDING / "wordmark.png")

    print(f"icon.png     {icon.size}")
    print(f"icon.ico     {[s for s, _ in _ICO_SIZES]}")
    print(f"wordmark.png {wordmark.size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
