"""Draw comic bubbles (speech, thought, shout, ...) with tails, and narration captions."""

import math
from typing import Callable, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw

from layout import bubble_shapes as shapes
from layout.bubble_planner import BubblePlan
from layout.captions import caption_corner, draw_caption, place_caption  # noqa: F401  (draw_caption re-exported)
from layout.lettering import (  # noqa: F401  (re-exported for existing callers)
    CAPTION_FILL, FONT_CANDIDATES, HEBREW_CHARS, HEBREW_FONT_CANDIDATES, INK, PAPER, Rect, _font, _hits, _wrap,
    is_rtl, polygon_hits_rect,
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


def _tail_area(kind: str, cx: float, cy: float, rx: float, ry: float, target: Tuple[float, float],
               max_len: float, line_width: int) -> List[Tuple[float, float]]:
    """Convex outline of everything the bubble's tail inks, for keeping it off the caption."""
    if kind == "thought":
        reach = shapes.REACH["thought"]
        return shapes.tail_band(cx, cy, rx * reach, ry * reach, target, 0.8, math.inf, ry * reach * 0.16 + line_width)
    if kind == "broadcast":
        return shapes.tail_band(cx, cy, rx, ry, target, 0.7, max_len, max(6.0, ry * 0.22) + line_width)
    return _tail(cx, cy, rx, ry, target, max_len)


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
    blocked: Optional[Callable[[int, int], bool]] = None,
) -> Tuple[int, int]:
    """Top-left corner for a bubble: free of obstacles, near the desired spot, preferably above the speaker.

    blocked(x0, y0) rules a spot out for another reason (its tail would cross the caption)."""
    w, h = size
    bw, bh = bubble
    gap = max(6, h // 80)
    best, best_score = None, float("inf")
    for y0 in range(5, max(6, h - bh - 5), max(4, h // 40)):
        for x0 in range(5, max(6, w - bw - 5), max(4, w // 60)):
            if any(_hits((x0, y0, bw, bh), o, gap) for o in obstacles) or (blocked and blocked(x0, y0)):
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
    wrap_share: Optional[float] = None,
    type_height: Optional[int] = None,
    tail_clear: Sequence[Rect] = (),
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
        type_height: Panel height the type and lines are sized for (default: the image's own height)
        tail_clear: Boxes no tail may cross (the caption): the bubble goes where its tail misses them,
            and loses the tail when no such spot exists
    """
    kind = shapes.bubble_kind(kind)
    w, h = image.size
    type_h = type_height or h
    draw = ImageDraw.Draw(image)
    font = _font(max(16, int(type_h * 0.05 * shapes.TEXT_SCALE.get(kind, 1))), text, font_path)
    line_width = max(2, type_h // 220) + (1 if kind == "shout" else 0)

    # Wrap to a roughly 3:1 text block so the oval stays round rather than flat
    line_height = draw.textbbox((0, 0), "Ag", font=font)[3]
    balanced = int(math.sqrt(draw.textlength(text, font=font) * line_height * 3))
    wrap_width = int(w * wrap_share) if wrap_share else min(int(w * 0.32), max(balanced, int(w * 0.08)))
    wrapped = _wrap(draw, text, font, wrap_width)
    left, top, right, bottom = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center")
    tw, th = right - left, bottom - top
    rx, ry = tw * 0.72 + 14, th * 0.78 + 12  # ellipse radii that enclose the text block
    reach = shapes.REACH.get(kind, 1.0)
    bw, bh = int(2 * rx * reach), int(2 * ry * reach)

    # An unseen mouth gives no direction: never invent a tail toward a random panel edge.
    target = (speaker[0] * w, speaker[1] * h) if speaker else None
    gap = max(6, h // 80)

    def tail_crosses(x0: int, y0: int) -> bool:
        area = _tail_area(kind, x0 + bw / 2, y0 + bh / 2, rx, ry, target, h * 0.14, line_width)
        return any(polygon_hits_rect(area, box, gap) for box in tail_clear)

    spot = ((w, h), (bw, bh), (center[0] * w, center[1] * h), target, placed)
    try:
        x0, y0 = _choose_position(*spot, tail_crosses if target and tail_clear else None)
    except ValueError:
        if not (target and tail_clear):
            raise
        x0, y0 = _choose_position(*spot)  # the caption keeps its corner; the bubble gives up its tail
        target = None
    placed.append((x0, y0, bw, bh))
    cx, cy = x0 + bw / 2, y0 + bh / 2
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


def _subjects(plan: BubblePlan, size: Tuple[int, int]) -> List[Rect]:
    """Every visible speaker's head and every protected subject: kept clear of all lettering."""
    w, h = size
    return [head_box(s, size) for s in plan.speakers if s] + [
        (int(x * w), int(y * h), int(bw * w), int(bh * h)) for x, y, bw, bh in plan.protected]


def _render_dialogue_once(
    image: Image.Image,
    dialogue: List[str],
    caption: str,
    plan: BubblePlan,
    kinds: Optional[Sequence[str]] = None,
    rtl: Optional[bool] = None,
    font_path: Optional[str] = None,
    reserved: Sequence[Rect] = (),
    wrap_share: Optional[float] = None,
    caption_width: float = 0.46,
    type_height: Optional[int] = None,
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
    heads = _subjects(plan, panel.size)
    placed = list(heads) + list(reserved)

    captions: List[Rect] = []
    if caption:
        # Narration is read first and always sits in a top corner: the reading-first one (top-right for
        # Hebrew), or the other top corner when that covers less of a protected subject.
        captions.append(place_caption(panel, caption, heads, placed, rtl, font_path, width_share=caption_width,
                                      type_height=type_height))
    kinds = list(kinds or []) + ["speech"] * (len(dialogue) - len(kinds or []))
    for text, center, speaker, kind in zip(dialogue, plan.bubbles, plan.speakers, kinds):
        draw_speech_bubble(panel, text, center, speaker, placed, kind, font_path, wrap_share, type_height,
                           captions)

    logger.debug(f"Drew {len(dialogue)} bubbles{' and a caption' if caption else ''}")
    return panel


SHAPES = ((None, 0.46), (0.45, 0.65), (0.62, 0.88), (0.24, 0.34))  # bubble wrap share, caption width share


def render_dialogue(image, dialogue, caption, plan, kinds=None, rtl=None, font_path=None, reserved=(), type_height=None):
    """Try alternative readable text shapes on fresh copies; never shrink or crop artwork.

    The caption is always in a top corner of the image and no bubble or tail touches it (every lettered
    image: strip panels and full-page splashes). Shapes whose caption covers no protected subject come
    first; when no shape manages that, the one whose caption covers least still keeps its top corner.

    type_height sizes the type as for a panel of that height, so a full-page splash letters like a strip panel.
    Wider shapes suit a calm band; the last, narrow shape (same font size, more lines) suits one calm side
    beside a close-up's face (book_comic/lettering_space.py).
    """
    shapes = SHAPES
    if caption:
        direction = any(is_rtl(t) for t in list(dialogue) + [caption]) if rtl is None else rtl
        heads = _subjects(plan, image.size)
        shapes = sorted(SHAPES, key=lambda shape: caption_corner(  # stable: equal cover keeps the order above
            image, caption, heads, direction, font_path, shape[1], type_height)[1])
    for wrap_share, caption_width in shapes:
        try:
            return _render_dialogue_once(image, dialogue, caption, plan, kinds, rtl, font_path,
                                         reserved, wrap_share, caption_width, type_height)
        except ValueError as error:
            if str(error) not in ('comic_lettering_no_space', 'comic_lettering_overflow'):
                raise
    raise ValueError('comic_lettering_no_space')
