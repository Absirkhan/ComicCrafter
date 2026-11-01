"""Draw comic bubbles (speech, thought, shout, ...) with tails, and narration captions."""

import math
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw

from layout import bubble_shapes as shapes
from layout.bubble_planner import BubblePlan
from layout.captions import draw_caption, place_caption  # noqa: F401  (draw_caption re-exported)
from layout.lettering import (  # noqa: F401  (re-exported for existing callers)
    CAPTION_FILL, FONT_CANDIDATES, HEBREW_CHARS, HEBREW_FONT_CANDIDATES, INK, PAPER, Rect, _font, _hits, _wrap,
    is_rtl,
)
from utils import get_logger

logger = get_logger(__name__)

_ellipse_edge = shapes.ellipse_edge


def _tail(cx: float, cy: float, rx: float, ry: float, target: Tuple[float, float], max_len: float) -> List[Tuple[float, float]]:
    """Triangle from inside the ellipse toward the speaker, stopping short of them."""
    ex, ey, angle = _ellipse_edge(cx, cy, rx, ry, *target)
    dx, dy = target[0] - ex, target[1] - ey
    dist = math.hypot(dx, dy) or 1.0
    length = min(dist * 0.7, max_len)
    tip = (ex + dx / dist * length, ey + dy / dist * length)

    half = 0.22  # radians either side of the edge point for the tail base
    base = [
        (cx + rx * 0.8 * math.cos(angle + s * half), cy + ry * 0.8 * math.sin(angle + s * half))
        for s in (-1, 1)
    ]
    return [base[0], tip, base[1]]


def _shrink(points: List[Tuple[float, float]], amount: float) -> List[Tuple[float, float]]:
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    out = []
    for x, y in points:
        d = math.hypot(x - cx, y - cy) or 1.0
        out.append((x - (x - cx) / d * amount, y - (y - cy) / d * amount))
    return out


def head_box(speaker: Tuple[float, float], size: Tuple[int, int]) -> Rect:
    """Rough rectangle around a speaker's head, from their mouth position."""
    w, h = size
    sx, sy = speaker[0] * w, speaker[1] * h
    return (int(sx - 0.07 * w), int(sy - 0.16 * h), int(0.14 * w), int(0.26 * h))


def _choose_position(
    size: Tuple[int, int],
    bubble: Tuple[int, int],
    desired: Tuple[float, float],
    speaker: Optional[Tuple[float, float]],
    obstacles: List[Rect],
) -> Tuple[int, int]:
    """Top-left corner for a bubble: free of obstacles, near the desired spot, preferably above the speaker."""
    w, h = size
    bw, bh = bubble
    gap = max(6, h // 80)
    best, best_score = None, float("inf")
    for y0 in range(5, max(6, h - bh - 5), max(4, h // 40)):
        for x0 in range(5, max(6, w - bw - 5), max(4, w // 60)):
            if any(_hits((x0, y0, bw, bh), o, gap) for o in obstacles):
                continue
            cx, cy = x0 + bw / 2, y0 + bh / 2
            score = math.hypot(cx - desired[0], cy - desired[1])
            if speaker:
                score += 0.5 * math.hypot(cx - speaker[0], cy - speaker[1])
                score += 0.3 * h if cy > speaker[1] else 0  # bubbles read best above the speaker
            if score < best_score:
                best, best_score = (x0, y0), score
    if best is None or bw > w - 10 or bh > h - 10:
        raise ValueError("comic_lettering_no_space")
    return best


def draw_speech_bubble(
    image: Image.Image,
    text: str,
    center: Tuple[float, float],
    speaker: Optional[Tuple[float, float]],
    placed: List[Tuple[int, int, int, int]],
    kind: str = "speech",
    font_path: Optional[str] = None,
) -> None:
    """Draw a bubble of the given kind near center with a tail toward the speaker.

    Args:
        image: Panel image, drawn on in place
        text: Dialogue text
        center: Desired bubble center, normalized 0-1
        speaker: Speaker's mouth, normalized 0-1 (None draws no tail)
        placed: Areas to keep clear (heads, caption, earlier bubbles); updated in place
        kind: One of bubble_shapes.BUBBLE_KINDS; anything else is drawn as "speech"
        font_path: Lettering font file (defaults to the bundled/system fonts)
    """
    kind = shapes.bubble_kind(kind)
    w, h = image.size
    draw = ImageDraw.Draw(image)
    font = _font(max(16, int(h * 0.05 * shapes.TEXT_SCALE.get(kind, 1))), text, font_path)
    line_width = max(2, h // 220) + (1 if kind == "shout" else 0)

    # Wrap to a roughly 3:1 text block so the oval stays round rather than flat
    line_height = draw.textbbox((0, 0), "Ag", font=font)[3]
    balanced = int(math.sqrt(draw.textlength(text, font=font) * line_height * 3))
    wrapped = _wrap(draw, text, font, min(int(w * 0.32), max(balanced, int(w * 0.08))))
    left, top, right, bottom = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center")
    tw, th = right - left, bottom - top
    rx, ry = tw * 0.72 + 14, th * 0.78 + 12  # ellipse radii that enclose the text block
    reach = shapes.REACH.get(kind, 1.0)
    bw, bh = int(2 * rx * reach), int(2 * ry * reach)

    x0, y0 = _choose_position(
        (w, h),
        (bw, bh),
        (center[0] * w, center[1] * h),
        (speaker[0] * w, speaker[1] * h) if speaker else None,
        placed,
    )
    placed.append((x0, y0, bw, bh))
    cx, cy = x0 + bw / 2, y0 + bh / 2
    # An unseen mouth gives no direction: never invent a tail toward a random panel edge.
    target = (speaker[0] * w, speaker[1] * h) if speaker else None
    tail = None
    if target is not None:
        if kind == "thought":
            shapes.thought_tail(draw, cx, cy, rx * reach, ry * reach, target, line_width)
        elif kind == "broadcast":
            shapes.lightning_tail(draw, cx, cy, rx, ry, target, h * 0.14, line_width)
        else:
            tail = _tail(cx, cy, rx, ry, target, max_len=h * 0.14)
            draw.polygon(tail, fill=INK)
            draw.polygon(_shrink(tail, line_width * 1.6), fill=PAPER)

    if kind == "speech":
        box = [cx - rx, cy - ry, cx + rx, cy + ry]
        draw.ellipse([box[0] - line_width, box[1] - line_width, box[2] + line_width, box[3] + line_width], fill=INK)
        if tail is not None:
            draw.polygon(_shrink(tail, line_width * 1.6), fill=PAPER)
        draw.ellipse(box, fill=PAPER)
    else:
        shapes.draw_outline(draw, kind, shapes.outline(kind, cx, cy, rx, ry), line_width)
    if kind == "song":
        shapes.notes(draw, cx, cy, rx, ry)

    colour = shapes.WHISPER_INK if kind == "whisper" else INK
    origin = (cx - tw / 2 - left, cy - th / 2 - top)
    if kind == "shout":  # bolder: the text drawn twice, a pixel apart
        draw.multiline_text((origin[0] + 1, origin[1]), wrapped, font=font, fill=colour, align="center")
    draw.multiline_text(origin, wrapped, font=font, fill=colour, align="center")


def render_dialogue(
    image: Image.Image,
    dialogue: List[str],
    caption: str,
    plan: BubblePlan,
    kinds: Optional[Sequence[str]] = None,
    rtl: Optional[bool] = None,
    font_path: Optional[str] = None,
    reserved: Sequence[Rect] = (),
) -> Image.Image:
    """Return a copy of the panel with its caption and bubbles drawn.

    Args:
        image: Panel art
        dialogue: Text of each line, in reading order
        caption: Narration caption ("" for none)
        plan: Speaker and bubble positions, and the preferred caption corner
        kinds: Bubble kind per line (default all "speech")
        rtl: Reading direction; None detects it from the text
        font_path: Lettering font file (defaults to the bundled/system fonts)
    """
    panel = image.convert("RGB").copy()
    rtl = any(is_rtl(t) for t in list(dialogue) + [caption]) if rtl is None else rtl
    # Every visible speaker's head is kept clear of all bubbles
    heads: List[Rect] = [head_box(s, panel.size) for s in plan.speakers if s]
    protected = [(int(x * panel.width), int(y * panel.height), int(w * panel.width), int(h * panel.height))
                 for x, y, w, h in plan.protected]
    heads += protected
    placed = list(heads) + list(reserved)

    if caption:
        # Narration is read first, so it starts in the reading-first corner (top-right for Hebrew)
        # and moves only when that corner would cover a speaker's head.
        reading_first = "top-right" if rtl else "top-left"
        other = "top-left" if rtl else "top-right"
        place_caption(panel, caption, (reading_first, other), heads, placed, rtl, font_path)
    kinds = list(kinds or []) + ["speech"] * (len(dialogue) - len(kinds or []))
    for text, center, speaker, kind in zip(dialogue, plan.bubbles, plan.speakers, kinds):
        draw_speech_bubble(panel, text, center, speaker, placed, kind, font_path)

    logger.debug(f"Drew {len(dialogue)} bubbles{' and a caption' if caption else ''}")
    return panel
