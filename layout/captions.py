"""Narration captions and dedication notes: boxed text in a panel corner."""

from typing import List, Optional, Tuple

from PIL import Image, ImageDraw

from layout.lettering import CAPTION_FILL, INK, Rect, _font, _wrap, is_rtl, overlap_area

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
    if x0 < 0 or y0 < 0 or x0 + bw > w or y0 + bh > h:
        raise ValueError("comic_lettering_overflow")
    if not dry:
        draw.rectangle([x0, y0, x0 + bw, y0 + bh], fill=CAPTION_FILL, outline=INK, width=max(2, h // 300))
        draw.multiline_text((x0 + pad - left, y0 + pad - top), wrapped, font=font, fill=INK, align=align)
    return x0, y0, bw, bh


def draw_caption(
    image: Image.Image, text: str, corner: str, placed: List[Rect], font_path: Optional[str] = None,
    width_share: float = CAPTION_WIDTH, type_height: Optional[int] = None,
) -> Rect:
    """Draw a rectangular narration caption in a corner; its box is added to placed.

    type_height: panel height the type is sized for (default: the image's own height)."""
    h = type_height or image.size[1]
    box = text_box(ImageDraw.Draw(image), image.size, text, max(14, int(h * CAPTION_SIZE)), corner, font_path,
                   width_share=width_share)
    placed.append(box)
    return box


def caption_corner(
    image: Image.Image, text: str, heads: List[Rect], rtl: bool, font_path: Optional[str] = None,
    width_share: float = CAPTION_WIDTH, type_height: Optional[int] = None,
) -> Tuple[str, int]:
    """The top corner a caption takes, and the area of the protected subjects in heads it covers there.

    It starts in the corner read first (top-left, or top-right in a right-to-left comic) and takes the
    other top corner only when that one is clear of the subjects, or covers less than half as much.
    """
    draw = ImageDraw.Draw(image)
    font_size = max(14, int((type_height or image.size[1]) * CAPTION_SIZE))

    def covered(corner: str) -> int:
        box = text_box(draw, image.size, text, font_size, corner, font_path, dry=True, width_share=width_share)
        return sum(overlap_area(box, head) for head in heads)

    reading_first, other = ("top-right", "top-left") if rtl else ("top-left", "top-right")
    first, second = covered(reading_first), covered(other)
    return (other, second) if second * 2 < first else (reading_first, first)


def place_caption(
    image: Image.Image,
    text: str,
    heads: List[Rect],
    placed: List[Rect],
    rtl: bool,
    font_path: Optional[str] = None,
    width_share: float = CAPTION_WIDTH,
    type_height: Optional[int] = None,
) -> Rect:
    """Draw the caption in a top corner of the image (caption_corner), always: it never floats lower.

    In the corner a reader reaches later, a bubble beside the caption would be read before it, so the
    band down to its bottom stays clear.

    type_height sizes the type as for a panel of that height (default: the image's own height).

    Returns:
        The caption's rectangle (also added to placed)
    """
    corner, _ = caption_corner(image, text, heads, rtl, font_path, width_share, type_height)
    box = draw_caption(image, text, corner, placed, font_path, width_share=width_share, type_height=type_height)
    if corner != ("top-right" if rtl else "top-left"):
        placed.append((0, 0, image.size[0], box[1] + box[3]))
    return box


def note_corner(rtl: bool) -> str:
    """Where a dedication note goes: the corner a reader reaches last."""
    return "bottom-left" if rtl else "bottom-right"


def draw_note(image: Image.Image, text: str, rtl: Optional[bool] = None, font_path: Optional[str] = None,
              type_height: Optional[int] = None) -> Image.Image:
    """Return a copy of the panel with a dedication caption in its last-read bottom corner."""
    if not text:
        return image
    panel = image.copy()
    rtl = is_rtl(text) if rtl is None else rtl
    font_size = max(14, int((type_height or panel.size[1]) * NOTE_SIZE))
    text_box(ImageDraw.Draw(panel), panel.size, text, font_size, note_corner(rtl), font_path)
    return panel
