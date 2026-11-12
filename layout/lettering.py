"""Fonts, colours and text measuring shared by bubbles, captions and covers."""

import re
from functools import lru_cache
from pathlib import Path
from typing import Optional, Sequence, Tuple

from PIL import ImageDraw, ImageFont

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
# Bundled face (SIL OFL, see assets/fonts) with Hebrew and Latin glyphs, so a Latin name inside
# Hebrew text is drawn instead of empty boxes, and lettering works on servers without Hebrew fonts.
LETTERING_FONT = FONTS_DIR / "Assistant-SemiBold.ttf"

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Comic Sans MS Bold.ttf",
    "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
    "comicbd.ttf",
    "comic.ttf",
    "DejaVuSans-Bold.ttf",
    "Arial.ttf",
]
# Comic Sans has no Hebrew glyphs, so Hebrew text gets its own fonts.
# (path, face index); SF Hebrew is skipped because it lacks commas, question marks and digits.
HEBREW_FONT_CANDIDATES = [
    (str(LETTERING_FONT), 0),
    ("/System/Library/Fonts/Supplemental/Raanana.ttc", 1),
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
    ("DejaVuSans-Bold.ttf", 0),
]
HEBREW_CHARS = re.compile(r"[֐-׿]")
Rect = Tuple[int, int, int, int]  # x, y, width, height
CAPTION_FILL = (243, 227, 181)
INK = (0, 0, 0)
PAPER = (255, 255, 255)


def is_rtl(text: str) -> bool:
    return bool(HEBREW_CHARS.search(text))


def _font(size: int, text: str = "", font_path: Optional[str] = None) -> ImageFont.ImageFont:
    """Lettering font for text.

    Args:
        size: Point size
        text: The text to draw; Hebrew text skips the Latin-only comic faces
        font_path: Font file used for all text when given (falls back to the defaults if unloadable)
    """
    candidates = [(str(font_path), 0)] if font_path else []
    if is_rtl(text):
        candidates += HEBREW_FONT_CANDIDATES
    else:
        candidates += [(name, 0) for name in FONT_CANDIDATES] + [(str(LETTERING_FONT), 0)]
    for name, index in candidates:
        try:
            return ImageFont.truetype(name, size, index=index)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    lines, current = [], ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if current and draw.textlength(trial, font=font) > max_width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    # Keep the greedy line count, but balance all lines so a short word is not stranded.
    words = text.split()

    @lru_cache(None)
    def balanced(start, count):
        if count == 0:
            return (0, ()) if start == len(words) else None
        best = None
        for end in range(start + 1, len(words) - count + 2):
            line = " ".join(words[start:end])
            width = draw.textlength(line, font=font)
            if width > max_width:
                break
            rest = balanced(end, count - 1)
            if rest is not None:
                candidate = ((max_width - width) ** 2 + rest[0], (line,) + rest[1])
                if best is None or candidate[0] < best[0]:
                    best = candidate
        return best

    if len(lines) > 1:
        result = balanced(0, len(lines))
        if result is not None:
            lines = result[1]
    return "\n".join(lines)


def _hits(a: Rect, b: Rect, gap: int) -> bool:
    return a[0] < b[0] + b[2] + gap and b[0] < a[0] + a[2] + gap and a[1] < b[1] + b[3] + gap and b[1] < a[1] + a[3] + gap


def overlap_area(a: Rect, b: Rect) -> int:
    width = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    height = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return max(0, width) * max(0, height)


def polygon_hits_rect(points: Sequence[Tuple[float, float]], rect: Rect, gap: float = 0) -> bool:
    """Whether a convex polygon (a bubble tail) comes within gap of a rectangle (separating axes)."""
    x0, y0, x1, y1 = rect[0] - gap, rect[1] - gap, rect[0] + rect[2] + gap, rect[1] + rect[3] + gap
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    edges = zip(points, list(points[1:]) + list(points[:1]))
    for nx, ny in [(1, 0), (0, 1)] + [(ay - by, bx - ax) for (ax, ay), (bx, by) in edges]:
        a = [x * nx + y * ny for x, y in points]
        b = [x * nx + y * ny for x, y in corners]
        if max(a) < min(b) or max(b) < min(a):
            return False
    return True
