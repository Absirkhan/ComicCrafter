"""Blank paper margins around a drawn picture.

Styles that mention paper ("earthy inks on cream paper") make the image model draw a print lying on paper: the
picture sits in the middle of the canvas with plain strips on two opposite sides (preview e35347af, 2026-11-04,
passed the art check with cream margins). The prompt forbids it (SINGLE_IMAGE_RULE); this measures what was drawn.

A margin is a run of near-uniform rows or columns from an edge. Only margins on two opposite sides count (a
print on paper), so one flat sky or floor along one edge is scenery, never cut.
"""

import re
from typing import Optional, Tuple

from PIL import Image, ImageStat

MIN_SHARE = 0.03      # a margin narrower than this share of the side is ignored
FLAT = 7.0            # luminance standard deviation of a plain line (paper grain is a little noisy)
SAME = 18.0           # a margin line's mean may differ this much from the edge line's mean
ASPECT_TOLERANCE = 0.15
PAPER_TONE = 165.0    # paper is light (cream, white, light grey); dark edges are scenery (a tunnel, night)


def _line(gray: Image.Image, axis: str, i: int) -> Tuple[float, float]:
    box = (i, 0, i + 1, gray.height) if axis == "x" else (0, i, gray.width, i + 1)
    stat = ImageStat.Stat(gray.crop(box))
    return stat.mean[0], stat.stddev[0]


def _run(gray: Image.Image, axis: str, from_end: bool) -> Tuple[int, Optional[float]]:
    """How many plain lines of the same tone run inward from one edge, and that tone."""
    length = gray.width if axis == "x" else gray.height
    order = range(length - 1, -1, -1) if from_end else range(length)
    edge, count = None, 0
    for i in order:
        mean, spread = _line(gray, axis, i)
        if spread > FLAT or (edge is not None and abs(mean - edge) > SAME):
            break
        edge = mean if edge is None else edge
        count += 1
    return count, edge


def find_margins(art: Image.Image) -> Optional[Tuple[int, int, int, int]]:
    """The picture's box (left, top, right, bottom) inside paper margins, or None when there are none."""
    gray = art.convert("L").resize((max(1, art.width // 4), max(1, art.height // 4)))
    scale_x, scale_y = art.width / gray.width, art.height / gray.height
    (left, left_tone), (right, right_tone) = _run(gray, "x", False), _run(gray, "x", True)
    (top, top_tone), (bottom, bottom_tone) = _run(gray, "y", False), _run(gray, "y", True)
    # Paper is one light tone on both sides; a flat sky above and flat ground below, or a dark night, are scenery.
    same = lambda a, b: a is not None and b is not None and abs(a - b) <= SAME and min(a, b) >= PAPER_TONE
    sides = min(left, right) >= MIN_SHARE * gray.width and same(left_tone, right_tone)
    ends = min(top, bottom) >= MIN_SHARE * gray.height and same(top_tone, bottom_tone)
    if not sides and not ends:
        return None
    if left + right >= gray.width or top + bottom >= gray.height:
        return None  # a plain image: nothing to keep
    box = (left if sides else 0, top if ends else 0, gray.width - right if sides else gray.width, gray.height - bottom if ends else gray.height)
    return (round(box[0] * scale_x), round(box[1] * scale_y), round(box[2] * scale_x), round(box[3] * scale_y))


def trim_margins(art: Image.Image, target_aspect: Optional[float]) -> Tuple[Image.Image, Optional[str]]:
    """The art without paper margins, and what happened: None (no margins), "trimmed" (the picture fills the
    panel after a small crop) or "redraw" (the picture's shape is too far from the panel's to fill it without
    cutting the subject: the caller keeps the whole draw and asks for a redraw)."""
    box = find_margins(art)
    if box is None:
        return art, None
    picture = art.crop(box)
    if not target_aspect:
        return picture, "trimmed"
    aspect = picture.width / picture.height
    return picture, ("trimmed" if abs(aspect - target_aspect) / target_aspect <= ASPECT_TOLERANCE else "redraw")


def target_aspect(size=None, aspect_ratio: str = "") -> Optional[float]:
    """The panel's width/height from its pixel size, else from an "W:H" ratio."""
    if size:
        return size[0] / size[1]
    try:
        w, h = (float(v) for v in aspect_ratio.split(":"))
        return w / h
    except ValueError:
        return None


MARGIN_CORRECTION = ("Blank paper margins surround the picture: fill the whole canvas edge to edge with the scene, "
                     "with no paper, mat or empty band around it.")


# "earthy inks on cream paper", "visible off-white paper", "aged paper": the model draws the paper itself, as a
# print lying on it (margins) or as an empty cream backdrop. Stored styles of approved comics still say it.
_PAPER_MEDIUM = re.compile(r"\b(?:on|over|visible)\s+(?:(?:cream|white|off-white|aged|textured|toned|rough|warm)[\s-]+)*paper\b"
                           r"|\baged paper\b", re.I)
PAPER_TEXTURE = "with a subtle paper-grain texture across the whole scene, edge to edge"


def drawable_style(style: str) -> str:
    """The art style with any physical paper medium turned into a texture over the whole scene."""
    return _PAPER_MEDIUM.sub(PAPER_TEXTURE, style or "")
