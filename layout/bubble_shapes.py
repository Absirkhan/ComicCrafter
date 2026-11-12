"""Outlines and tails for each comic bubble kind (speech, thought, shout, ...)."""

import math
from typing import List, Tuple

from PIL import ImageDraw

from layout.lettering import INK, PAPER

BUBBLE_KINDS = ("speech", "thought", "shout", "whisper", "broadcast", "fear", "song")
# Shouts are larger; whispering uses a dashed outline without sacrificing readability.
TEXT_SCALE = {"shout": 1.15}
# How far the outline reaches past the text ellipse (spikes, scallops, drips), for collision boxes
REACH = {"shout": 1.3, "thought": 1.15, "fear": 1.2, "song": 1.1, "broadcast": 1.05}
WHISPER_INK = INK

Points = List[Tuple[float, float]]


def bubble_kind(kind: str) -> str:
    """The kind to draw: unknown or missing kinds are plain speech."""
    return kind if kind in BUBBLE_KINDS else "speech"


def ellipse_edge(cx: float, cy: float, rx: float, ry: float, tx: float, ty: float) -> Tuple[float, float, float]:
    """Point on the ellipse edge facing (tx, ty), and the angle to it."""
    angle = math.atan2((ty - cy) / ry, (tx - cx) / rx)
    return cx + rx * math.cos(angle), cy + ry * math.sin(angle), angle


def outline(kind: str, cx: float, cy: float, rx: float, ry: float) -> Points:
    """The bubble's outline polygon around the text ellipse."""
    if kind == "broadcast":  # angular: a rectangle with cut corners
        c = min(rx, ry) * 0.35
        return [(cx - rx + c, cy - ry), (cx + rx - c, cy - ry), (cx + rx, cy - ry + c), (cx + rx, cy + ry - c),
                (cx + rx - c, cy + ry), (cx - rx + c, cy + ry), (cx - rx, cy + ry - c), (cx - rx, cy - ry + c)]
    if kind == "shout":  # a jagged burst: a star of short, wide spikes
        spikes = 18
        return [(cx + rx * (1.3 if k % 2 == 0 else 1.02) * math.cos(math.pi * k / spikes),
                 cy + ry * (1.3 if k % 2 == 0 else 1.02) * math.sin(math.pi * k / spikes)) for k in range(2 * spikes)]
    points = []
    steps = 120
    for i in range(steps):
        t = 2 * math.pi * i / steps
        r = 1.0
        if kind == "thought":  # soft cloud scallops
            r = 1.0 + 0.12 * abs(math.sin(5 * t))
        elif kind == "song":  # flowing waves
            r = 1.0 + 0.06 * math.sin(10 * t)
        elif kind == "fear" and math.sin(t) > 0.35:  # dripping icicles along the bottom edge
            r = 1.0 + 0.2 * max(0.0, 1 - abs(((i % 10) - 5) / 2.5))
        points.append((cx + rx * r * math.cos(t), cy + ry * r * math.sin(t)))
    return points


def grow(points: Points, amount: float) -> Points:
    """Push every point away from the centroid, for the outline's ink ring."""
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    out = []
    for x, y in points:
        d = math.hypot(x - cx, y - cy) or 1.0
        out.append((x + (x - cx) / d * amount, y + (y - cy) / d * amount))
    return out


def tail_band(cx, cy, rx, ry, target, share: float, max_len: float, half_width: float) -> Points:
    """The strip a thought or broadcast tail is drawn in: from the ellipse edge toward the target."""
    ex, ey, _ = ellipse_edge(cx, cy, rx, ry, *target)
    dx, dy = target[0] - ex, target[1] - ey
    dist = math.hypot(dx, dy) or 1.0
    length = min(dist * share, max_len)
    ux, uy, px, py = dx / dist, dy / dist, -dy / dist * half_width, dx / dist * half_width
    end = (ex + ux * length, ey + uy * length)
    return [(ex + px, ey + py), (end[0] + px, end[1] + py), (end[0] - px, end[1] - py), (ex - px, ey - py)]


def thought_tail(draw: ImageDraw.ImageDraw, cx, cy, rx, ry, target, line_width: int) -> None:
    """A chain of shrinking circles toward the speaker's head instead of a pointed tail."""
    ex, ey, _ = ellipse_edge(cx, cy, rx, ry, *target)
    for step, size in ((0.3, 0.16), (0.55, 0.11), (0.8, 0.07)):
        x, y = ex + (target[0] - ex) * step, ey + (target[1] - ey) * step
        r = ry * size
        draw.ellipse([x - r - line_width, y - r - line_width, x + r + line_width, y + r + line_width], fill=INK)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=PAPER)


def lightning_tail(draw: ImageDraw.ImageDraw, cx, cy, rx, ry, target, max_len: float, line_width: int) -> None:
    """A sharp zigzag toward the device or speaker, like a radio signal."""
    ex, ey, _ = ellipse_edge(cx, cy, rx, ry, *target)
    dx, dy = target[0] - ex, target[1] - ey
    dist = math.hypot(dx, dy) or 1.0
    length = min(dist * 0.7, max_len)
    ux, uy, px, py = dx / dist, dy / dist, -dy / dist, dx / dist
    side = max(6.0, ry * 0.22)
    path = [(ex, ey)] + [(ex + ux * length * a + px * side * b, ey + uy * length * a + py * side * b)
                         for a, b in ((0.33, 1), (0.5, -1), (0.75, 1), (1.0, 0))]
    draw.line(path, fill=INK, width=line_width * 2, joint="curve")


def draw_outline(draw: ImageDraw.ImageDraw, kind: str, points: Points, line_width: int) -> None:
    """Fill the bubble and ink its edge: dashed for a whisper, solid otherwise."""
    if kind == "whisper":
        draw.polygon(points, fill=PAPER)
        for i in range(0, len(points), 4):
            draw.line([points[i], points[(i + 2) % len(points)]], fill=INK, width=line_width)
        return
    draw.polygon(grow(points, line_width), fill=INK)
    draw.polygon(points, fill=PAPER)


def notes(draw: ImageDraw.ImageDraw, cx, cy, rx, ry) -> None:
    """Two small eighth notes beside a song bubble, drawn as shapes (fonts may lack ♪)."""
    for nx, ny, s in ((cx + rx * 1.05, cy - ry * 0.75, ry * 0.18), (cx - rx * 1.12, cy - ry * 0.45, ry * 0.14)):
        width = max(2, int(s / 3))
        draw.ellipse([nx - s, ny + s * 1.6, nx + s * 0.6, ny + s * 2.6], fill=INK)
        draw.line([(nx + s * 0.55, ny + s * 2.1), (nx + s * 0.55, ny - s * 0.4)], fill=INK, width=width)
        draw.line([(nx + s * 0.55, ny - s * 0.4), (nx + s * 1.4, ny + s * 0.3)], fill=INK, width=width)
