"""Derive the shipped brand assets from the source logos.

Reads the two hand-made logos under ``assets/branding/source/`` and produces the
files the app and installer actually load:

* ``icon.png``  — the shield mark, trimmed to its content, centred on a square
  transparent canvas with a small margin (a clean app / tray / window icon).
* ``icon.ico``  — the same mark at every size Windows asks for (Explorer, the
  taskbar, the .exe resource, the Inno installer).
* ``wordmark.png`` — the horizontal lockup (shield + name), trimmed to content,
  for the About and onboarding screens.
* ``wizard_large.bmp`` / ``wizard_small.bmp`` — the Inno Setup installer wizard
  images (welcome side panel + header logo), the mark on the brand slate.

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

# The brand slate (Theme `base`) the logo is designed to sit on — the frosted
# glass mark reads far better on it than on Inno's default blue/white wizard.
_SLATE = (0x13, 0x16, 0x1B)

# Inno Setup wizard images (modern style). Both are BMP with no alpha; Inno scales
# the source down for higher DPI, so we author at the largest documented size.
_WIZARD_LARGE = (497, 314)  # WizardImageFile — welcome/finished side panel
_WIZARD_SMALL = (138, 140)  # WizardSmallImageFile — header on every other page


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


def _wizard_bmp(mark: Image.Image, size: tuple[int, int], fill: float) -> Image.Image:
    """Centre the mark on an opaque slate BMP canvas (no alpha; Inno wants BMP).

    ``fill`` is the fraction of the shorter side the mark should occupy.
    """
    canvas = Image.new("RGBA", size, (*_SLATE, 255))
    art = _trim_to_content(mark)
    target = int(min(size) * fill)
    scale = target / max(art.width, art.height)
    art = art.resize(
        (max(1, round(art.width * scale)), max(1, round(art.height * scale))), Image.LANCZOS
    )
    canvas.paste(art, ((size[0] - art.width) // 2, (size[1] - art.height) // 2), art)
    return canvas.convert("RGB")  # BMP has no alpha channel


def main() -> int:
    icon_src = Image.open(_SOURCE / "icon.png")
    wordmark_src = Image.open(_SOURCE / "wordmark.png")

    icon = _square_icon(icon_src, _ICON_CANVAS, _ICON_MARGIN)
    icon.save(_BRANDING / "icon.png")
    icon.save(_BRANDING / "icon.ico", sizes=_ICO_SIZES)

    wordmark = _trim_to_content(wordmark_src)
    wordmark.save(_BRANDING / "wordmark.png")

    # Installer wizard: the wordmark on the big welcome panel, the shield alone in
    # the compact header (a wide lockup would be unreadable at 138px).
    _wizard_bmp(wordmark_src, _WIZARD_LARGE, fill=0.80).save(_BRANDING / "wizard_large.bmp")
    _wizard_bmp(icon_src, _WIZARD_SMALL, fill=0.85).save(_BRANDING / "wizard_small.bmp")

    print(f"icon.png          {icon.size}")
    print(f"icon.ico          {[s for s, _ in _ICO_SIZES]}")
    print(f"wordmark.png      {wordmark.size}")
    print(f"wizard_large.bmp  {_WIZARD_LARGE}")
    print(f"wizard_small.bmp  {_WIZARD_SMALL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
