"""Derive the shipped brand assets from the source logos.

Reads the two hand-made logos under ``assets/branding/source/`` and produces the
files the app and installer actually load:

* ``icon.png``  — the app icon: the mark on an opaque rounded slate tile so it
  stays legible at 16-48px on any background (the bare frosted mark vanishes on
  the light Explorer background). Used for the window / tray / taskbar icon.
* ``icon.ico``  — the same tile at every size Windows asks for (Explorer, the
  taskbar, the .exe resource, and the Setup.exe / installer icon).
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

from PIL import Image, ImageDraw, ImageFilter

_BRANDING = (
    Path(__file__).resolve().parent.parent / "src" / "privacy_guard" / "ui" / "assets" / "branding"
)
_SOURCE = _BRANDING / "source"

# Windows wants several icon sizes; supplying them all keeps the mark crisp from
# the 16px taskbar tray up to the 256px Explorer tile.
_ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
_ICON_CANVAS = 512  # master PNG side length

# Brand colours (from docs/DESIGN_TOKENS.md): the slate the logo sits on, the
# slightly lighter panel, and the single aqua accent.
_SLATE = (0x13, 0x16, 0x1B)
_PANEL = (0x24, 0x2B, 0x36)
_ACCENT = (0x74, 0xC7, 0xD6)

# The mark is deliberately frosted-glass (translucent, low-contrast) — gorgeous at
# hero size, but as a bare OS icon it nearly vanishes at 16-48px on the light
# Explorer background. So the app/installer icon is a *tile*: an opaque rounded
# slate square (visible on any background) with the mark solidified on top.
_ICON_SUPERSAMPLE = 4  # render big, downscale — keeps small sizes crisp
_MARK_FILL = 0.66  # mark size as a fraction of the tile
_ALPHA_BOOST = 2.4  # kills the frosted translucency so the mark reads solid

# Inno Setup wizard images (modern style). Both are BMP with no alpha; Inno scales
# the source down for higher DPI, so we author at the largest documented size.
_WIZARD_LARGE = (497, 314)  # WizardImageFile — welcome/finished side panel
_WIZARD_SMALL = (138, 140)  # WizardSmallImageFile — header on every other page


def _trim_to_content(image: Image.Image) -> Image.Image:
    """Crop away fully-transparent borders so the artwork fills the frame."""
    image = image.convert("RGBA")
    bbox = image.split()[3].getbbox()
    return image.crop(bbox) if bbox else image


def _solidify(mark: Image.Image, boost: float = _ALPHA_BOOST) -> Image.Image:
    """Raise the alpha of visible pixels so the frosted mark reads solid at 16px."""
    r, g, b, a = mark.split()
    a = a.point(lambda v: min(255, int(v * boost)))
    return Image.merge("RGBA", (r, g, b, a))


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255
    )
    return mask


def _icon_tile(source: Image.Image, canvas: int) -> Image.Image:
    """A rounded slate tile with the solidified mark — a legible OS app icon."""
    s = canvas * _ICON_SUPERSAMPLE

    # Vertical panel->slate gradient for a little depth.
    tile = Image.new("RGBA", (s, s))
    for y in range(s):
        t = y / s
        col = tuple(int(_PANEL[i] * (1 - t) + _SLATE[i] * t) for i in range(3))
        tile.paste((*col, 255), [0, y, s, y + 1])

    # Soft aqua halo behind the mark, so the dark upper half of the shield lifts
    # off the dark tile instead of blending into it.
    halo = Image.new("L", (s, s), 0)
    ImageDraw.Draw(halo).ellipse([s * 0.18, s * 0.16, s * 0.82, s * 0.84], fill=70)
    halo = halo.filter(ImageFilter.GaussianBlur(s * 0.08))
    glow = Image.new("RGBA", (s, s), (*_ACCENT, 0))
    glow.putalpha(halo)
    tile = Image.alpha_composite(tile, glow)

    # The solidified mark, centred.
    mark = _solidify(_trim_to_content(source))
    target = int(s * _MARK_FILL)
    scale = target / max(mark.width, mark.height)
    mark = mark.resize((round(mark.width * scale), round(mark.height * scale)), Image.LANCZOS)
    tile.alpha_composite(mark, ((s - mark.width) // 2, (s - mark.height) // 2))

    # A thin accent edge, then clip to rounded corners.
    radius = int(s * 0.22)
    ImageDraw.Draw(tile).rounded_rectangle(
        [2, 2, s - 3, s - 3], radius=radius, outline=(*_ACCENT, 120), width=max(2, s // 64)
    )
    tile.putalpha(
        Image.composite(tile.split()[3], Image.new("L", (s, s), 0), _rounded_mask((s, s), radius))
    )
    return tile.resize((canvas, canvas), Image.LANCZOS)


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

    icon = _icon_tile(icon_src, _ICON_CANVAS)
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
