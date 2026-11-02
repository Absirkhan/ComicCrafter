"""Narration captions and dedication notes: boxed text in a panel corner."""

import math
from typing import List, Optional, Sequence

from PIL import Image, ImageDraw

from layout.lettering import CAPTION_FILL, INK, Rect, _font, _wrap, is_rtl, overlap_area

CORNERS = ("top-left", "top-right", "bottom-left", "bottom-right")
CAPTION_WIDTH = 0.46  # wrap width as a share of the panel; narrower turns two sentences into a tall column
CAPTION_SIZE = 0.045  # font size as a share of the panel height
NOTE_SIZE = 0.035


def text_box(
    draw: ImageDraw.ImageDraw,
    size: tuple,
    text: str,
    font_size: int,
    corner: str,
    font_path: Optional[str] = None,
    dry: bool = False,
    position=None,
    width_share: float = CAPTION_WIDTH,
) -> Rect:
    """Draw (or with dry=True only measure) one boxed text block in a corner; returns its rectangle."""
    w, h = size
    font = _font(font_size, text, font_path)
    pad = max(6, font_size // 3)
    align = "right" if is_rtl(text) else "left"
    wrapped = _wrap(draw, text, font, int(w * width_share))
    left, top, right, bottom = draw.multiline_textbbox((0, 0), wrapped, font=font, align=align)
    bw, bh = right - left + 2 * pad, bottom - top + 2 * pad
    margin = max(8, h // 40)
    x0 = margin if corner.endswith("left") else w - bw - margin
    y0 = margin if corner.startswith("top") else h - bh - margin
    if position is not None:
        x0, y0 = position
    if x0 < 0 or y0 < 0 or x0 + bw > w or y0 + bh > h:
        raise ValueError("comic_lettering_overflow")
    if not dry:
        draw.rectangle([x0, y0, x0 + bw, y0 + bh], fill=CAPTION_FILL, outline=INK, width=max(2, h // 300))
        draw.multiline_text((x0 + pad - left, y0 + pad - top), wrapped, font=font, fill=INK, align=align)
    return x0, y0, bw, bh


def draw_caption(
    image: Image.Image, text: str, corner: str, placed: List[Rect], font_path: Optional[str] = None,
    position=None, width_share: float = CAPTION_WIDTH,
) -> Rect:
    """Draw a rectangular narration caption in a corner; its box is added to placed."""
    h = image.size[1]
    box = text_box(ImageDraw.Draw(image), image.size, text, max(14, int(h * CAPTION_SIZE)), corner, font_path,
                   position=position, width_share=width_share)
    placed.append(box)
    return box


def place_caption(
    image: Image.Image,
    text: str,
    corners: Sequence[str],
    heads: List[Rect],
    placed: List[Rect],
    rtl: bool,
    font_path: Optional[str] = None,
    width_share: float = CAPTION_WIDTH,
) -> str:
    """Draw the caption in whichever of corners covers the least of the speakers' heads.

    Ties keep the earlier corner, so pass the preferred (e.g. vision-model chosen) corner first.
    The caption is read first: in the corner a reader reaches later (top-left in a right-to-left
    comic), a bubble beside it would be read before it, so the band down to its bottom stays clear.

    Returns:
        The corner used
    """
    w, h = image.size
    draw = ImageDraw.Draw(image)
    font_size = max(14, int(h * CAPTION_SIZE))
    corner = min(corners, key=lambda c: sum(
        overlap_area(text_box(draw, image.size, text, font_size, c, font_path, dry=True, width_share=width_share), head) for head in heads
    ))
    candidate = text_box(draw, image.size, text, font_size, corner, font_path, dry=True, width_share=width_share)
    position = None
    if any(overlap_area(candidate, head) for head in heads):
        # Two occupied corners do not mean the entire panel has no space. Search from
        # top to bottom, preserving the reading side and all protected focal subjects.
        bw, bh = (math.ceil(value) for value in candidate[2:])
        margin = max(8, h // 40)
        xs = list(range(margin, max(margin + 1, w - bw - margin + 1), max(4, w // 60)))
        if rtl:
            xs.reverse()
        for y in range(margin, max(margin + 1, h - bh - margin + 1), max(4, h // 40)):
            for x in xs:
                if not any(overlap_area((x, y, bw, bh), head) for head in heads):
                    position = (x, y)
                    break
            if position is not None:
                break
        if position is None:
            raise ValueError("comic_lettering_no_space")
    box = draw_caption(image, text, corner, placed, font_path, position=position, width_share=width_share)
    if position is not None or corner != ("top-right" if rtl else "top-left"):
        placed.append((0, 0, w, box[1] + box[3]))
    return corner


def note_corner(rtl: bool) -> str:
    """Where a dedication note goes: the corner a reader reaches last."""
    return "bottom-left" if rtl else "bottom-right"


def draw_note(image: Image.Image, text: str, rtl: Optional[bool] = None, font_path: Optional[str] = None) -> Image.Image:
    """Return a copy of the panel with a dedication caption in its last-read bottom corner."""
    if not text:
        return image
    panel = image.copy()
    rtl = is_rtl(text) if rtl is None else rtl
    font_size = max(14, int(panel.size[1] * NOTE_SIZE))
    text_box(ImageDraw.Draw(panel), panel.size, text, font_size, note_corner(rtl), font_path)
    return panel
