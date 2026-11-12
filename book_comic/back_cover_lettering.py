"""Back cover lettering: a dark translucent panel in the calm upper half with the tagline and the blurb.

The art is drawn with nobody in it and a calm upper half (image_prompts.back_cover_prompt); the panel keeps
white type readable on any art. Hebrew is set right to left. Type shrinks until the whole text fits the panel.
"""

import math
from typing import Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from book_comic.cover_lettering import SAFE_BOTTOM, SAFE_WIDTH, CoverFonts, _shadowed_text, resolve_font
from layout.lettering import _wrap, is_rtl

PANEL_TOP = 0.2      # the panel starts a fifth of the way down
PANEL_WIDTH = 0.8    # share of the cover width
MAX_HEIGHT = 0.55    # the panel never reaches past three quarters of the height
PANEL_FILL = (12, 14, 22, 175)
TAGLINE_SIZE = 0.052  # share of the width
BLURB_SIZE = 0.03     # share of the width; never below MIN_BLURB_SIZE
MIN_BLURB_SIZE = 0.018


def _measure(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, align: str) -> Tuple[str, int, int]:
    wrapped = _wrap(draw, text, font, max_width)
    style = {"align": align, "spacing": max(4, font.size // 4)}
    if is_rtl(text):
        style["direction"] = "rtl"
    try:
        left, top, right, bottom = draw.multiline_textbbox((0, 0), wrapped, font=font, **style)
    except (KeyError, ValueError):  # Pillow without libraqm cannot set direction; Hebrew is still shaped
        style.pop("direction", None)
        left, top, right, bottom = draw.multiline_textbbox((0, 0), wrapped, font=font, **style)
    return wrapped, right - left, bottom - top


def _fit_blurb(draw, blurb: str, path, width: int, room: int, cover_width: int):
    """The largest blurb face (down to MIN_BLURB_SIZE of the width) whose wrapped text fits in room pixels."""
    size = int(cover_width * BLURB_SIZE)
    floor = max(12, int(cover_width * MIN_BLURB_SIZE))
    while True:
        font = ImageFont.truetype(str(path), size)
        wrapped, _, height = _measure(draw, blurb, font, width, "center")
        if height <= room or size <= floor:
            return font, wrapped, height
        size = max(floor, int(size * 0.92))


def letter_back_cover(image: Image.Image, back: Dict, fonts: Optional[CoverFonts] = None) -> Image.Image:
    """Letter the back cover art.

    Args:
        image: Back cover art (the setting, nobody in it)
        back: {"tagline", "blurb", optional "footer", "title_font" (bundled file name or font path)}
        fonts: Faces to use: the title face for the tagline, the starring face for the blurb, the footer face
    """
    fonts = fonts or CoverFonts()
    page = image.convert("RGBA")
    w, h = page.size
    draw = ImageDraw.Draw(page)
    panel_w = int(w * PANEL_WIDTH)
    pad = max(12, w // 28)
    inner = panel_w - 2 * pad
    tagline, blurb = (back.get("tagline") or "").strip(), (back.get("blurb") or "").strip()
    tag_font = None
    tag_h = 0
    if tagline:
        tag_font = ImageFont.truetype(str(resolve_font(back.get("title_font"), fonts.title)),
                                      max(16, int(w * TAGLINE_SIZE * fonts.title_scale)))
        _, _, tag_h = _measure(draw, tagline, tag_font, inner, "center")
    gap = pad // 2 if tagline and blurb else 0
    room = int(h * MAX_HEIGHT) - 2 * pad - tag_h - gap
    blurb_font, blurb_text, blurb_h = (None, "", 0)
    if blurb:
        blurb_font, blurb_text, blurb_h = _fit_blurb(draw, blurb, fonts.starring, inner, room, w)
    if not tagline and not blurb:
        return page.convert("RGB")
    panel_h = min(int(h * MAX_HEIGHT), 2 * pad + tag_h + gap + blurb_h)
    x0, y0 = (w - panel_w) // 2, int(h * PANEL_TOP)
    shade = Image.new("RGBA", page.size, (0, 0, 0, 0))
    ImageDraw.Draw(shade).rounded_rectangle([x0, y0, x0 + panel_w, y0 + panel_h], radius=max(6, w // 60), fill=PANEL_FILL)
    page.alpha_composite(shade)
    y = y0 + pad
    if tag_font:
        y += _shadowed_text(page, tagline, tag_font, inner, y, blur=max(3, h // 400)) + gap
    if blurb_font:
        style = {"align": "center", "spacing": max(4, blurb_font.size // 4)}
        if is_rtl(blurb):
            style["direction"] = "rtl"
        draw = ImageDraw.Draw(page)
        try:
            left, top, right, _ = draw.multiline_textbbox((0, 0), blurb_text, font=blurb_font, **style)
        except (KeyError, ValueError):
            style.pop("direction", None)
            left, top, right, _ = draw.multiline_textbbox((0, 0), blurb_text, font=blurb_font, **style)
        draw.multiline_text(((w - (right - left)) // 2 - left, y - top), blurb_text, font=blurb_font,
                            fill=(240, 240, 240, 255), **style)
    if back.get("footer"):
        font = ImageFont.truetype(str(fonts.footer), max(14, int(h * 0.022)))
        # Inside the printers' text margin, as the front cover's lettering (cover_lettering.SAFE_BOTTOM).
        _shadowed_text(page, back["footer"], font, int(w * SAFE_WIDTH), h - math.ceil(h * SAFE_BOTTOM), align_bottom=True,
                       blur=max(3, h // 400))
    return page.convert("RGB")
