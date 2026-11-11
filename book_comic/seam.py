"""A seam: a thin flat full-width line where the image model stacked a second strip over the scene, and an edge band:
a blank light strip along one edge closed off by a ruled line (an empty caption strip or a page margin).

find_seam keeps the cover's contract (a strip across the top; the row below it). cut_seam, for panels, cuts the
same kind of strip: a band of at most STRIP of the height across the top. A flat line anywhere lower is left alone,
because a floor, table or water edge looks the same to a pixel scan and cutting there would publish a panel without
its feet (review 2026-11-05); a seam lower down is for the revision or a fresh draw (book_comic.revise). The audit
marks a cut draw ("seam_cut"), and the vision check sees the cut art.
"""
from typing import List, Optional, Tuple

from PIL import Image, ImageOps, ImageStat

STRIP = 0.15  # a stacked strip is a band across the top; fitting the rest back to size crops at most this share of the width
THIN = 0.02  # a seam is at most this share of the height; thicker flat bands are sky, floor or a wall
MIN_ROWS = 3  # and at least this many rows: a 1–2 px flat line is a drawn horizon or ledge


def _runs(image: Image.Image) -> Tuple[List[Tuple[int, int]], int]:
    """(start, end) of every thin flat full-width run with textured art on both sides, and the height.

    Row flatness is the per-channel std across the row, computed in blocks of rows so a print-size image never
    becomes one float32 copy of itself. A run shorter than MIN_ROWS is a drawn line, not a seam."""
    import numpy as np
    rgb = image.convert("RGB")
    pixels = np.asarray(rgb)
    flat = np.concatenate([pixels[y:y + 256].astype(np.float32).std(axis=1).max(axis=1) < 20 for y in range(0, pixels.shape[0], 256)])
    h = len(flat)
    thin, gap = max(3, int(h * THIN)), max(2, h // 300)
    y, runs = gap, []
    while y < h - gap:
        if not flat[y]:
            y += 1
            continue
        run_end = y
        while run_end < h and flat[run_end]:
            run_end += 1
        if MIN_ROWS <= run_end - y <= thin and run_end + gap < h and not flat[y - gap] and not flat[run_end + gap]:
            runs.append((y, run_end))
        y = run_end + 1
    return runs, h


def find_seam(image: Image.Image, search_share: float = 0.45) -> Optional[int]:
    """The row just below a thin, flat, full-width line across the top of the art where the model stacked a second
    strip; None when there is none. Only a run of at most THIN of the height with textured art on both sides counts,
    so a plain sky is not a seam."""
    runs, h = _runs(image)
    return next((end for start, end in runs if start < int(h * search_share)), None)


def seam_band(image: Image.Image) -> Optional[Tuple[int, int]]:
    """The (start, end) rows of a seam within STRIP of the top edge, else None."""
    runs, h = _runs(image)
    return next(((start, end) for start, end in runs if end <= h * STRIP), None)


# An edge band (2026-11-10 review, pages 8 and 12): an empty caption strip or page margin the model drew along one
# edge, closed off by a ruled border line. Light, plain and at most STRIP deep; the dark line after it is what tells
# it from a plain sky or floor, which have no ruled line, so those are never cut.
BAND_FLAT = 7.0      # luminance spread of a blank line (a little paper grain)
BAND_TONE = 165.0    # a blank band is light (white, cream, light grey)
BAND_SAME = 18.0     # every line of the band has about the edge line's tone
INK_DARK = 70.0      # a border line is at least this much darker than the band
INK_TONE = 110.0     # and dark in itself: ink, not mid-tone scenery smoothed flat by the quarter-size scan
INK_FLAT = 10.0      # and as plain as the band (scenery rows, even smoothed, vary more)
BAND_MIN = 0.01      # a band thinner than this share of the side is a drawn edge, not a strip


def _line(gray: Image.Image, axis: str, i: int) -> Tuple[float, float]:
    box = (i, 0, i + 1, gray.height) if axis == "x" else (0, i, gray.width, i + 1)
    stat = ImageStat.Stat(gray.crop(box))
    return stat.mean[0], stat.stddev[0]


def _edge_band(gray: Image.Image, axis: str, from_end: bool) -> int:
    """Lines to cut from one edge: a blank light band plus the ruled dark line closing it off, or 0."""
    length = gray.width if axis == "x" else gray.height
    order = list(range(length - 1, -1, -1) if from_end else range(length))
    tone, band = None, 0
    for i in order[: int(length * STRIP) + 1]:
        mean, spread = _line(gray, axis, i)
        if spread > BAND_FLAT or mean < BAND_TONE or (tone is not None and abs(mean - tone) > BAND_SAME):
            break
        tone, band = tone if tone is not None else mean, band + 1
    if tone is None or band < max(1, int(length * BAND_MIN)) or band > length * STRIP:
        return 0
    ink = 0
    for i in order[band: band + max(1, int(length * THIN))]:
        mean, spread = _line(gray, axis, i)
        if spread > INK_FLAT or mean > INK_TONE or tone - mean < INK_DARK:
            break
        ink += 1
    return band + ink if ink else 0


LEAD = 0.06   # a caption box may sit this far below the top edge, with a sliver of sky above it (2026-11-11 splash)
EDGE_JUMP = 40.0  # the box's top and bottom edges are hard: the tone jumps at least this much across each


def _detached_top_band(gray: Image.Image) -> int:
    """Rows to cut from the top for a blank light box that starts just below the edge, or 0.

    Top only: what is cut is at most STRIP of sky, so a pale flat cloud band, if ever taken for a box, costs nothing.
    A box has hard edges on both sides; a pale sky fades into the clouds around it."""
    h = gray.height
    lines = [_line(gray, "y", i) for i in range(int(h * STRIP) + 1)]
    for start in range(1, int(h * LEAD) + 1):
        mean, spread = lines[start]
        above = max(abs(mean - lines[start - 1][0]), abs(mean - lines[max(0, start - 2)][0]))
        if spread > BAND_FLAT or mean < BAND_TONE or above < EDGE_JUMP:
            continue
        end = start
        while end < len(lines) and lines[end][1] <= BAND_FLAT and abs(lines[end][0] - mean) <= BAND_SAME:
            end += 1
        if end - start < max(2, int(h * 0.03)) or end + 1 >= len(lines):
            continue
        tone = sum(m for m, _ in lines[start:end]) / (end - start)
        # The quarter-size scan blurs an edge over about one row, so the row past it counts too.
        if max(abs(lines[end][0] - tone), abs(lines[end + 1][0] - tone)) >= EDGE_JUMP:
            return end
    return 0


def edge_band_box(art: Image.Image) -> Optional[Tuple[int, int, int, int]]:
    """The picture's box (left, top, right, bottom) without blank ruled bands along its edges, or None when there are none."""
    gray = art.convert("L").resize((max(1, art.width // 4), max(1, art.height // 4)))
    cut = [_edge_band(gray, "x", False), _edge_band(gray, "y", False), _edge_band(gray, "x", True), _edge_band(gray, "y", True)]
    cut[1] = cut[1] or _detached_top_band(gray)
    if not any(cut):
        return None
    sx, sy = art.width / gray.width, art.height / gray.height
    left, top, right, bottom = cut[0] * sx, cut[1] * sy, art.width - cut[2] * sx, art.height - cut[3] * sy
    return round(left), round(top), round(right), round(bottom)


def cut_seam(art: Image.Image, size: Tuple[int, int]) -> Optional[Image.Image]:
    """The art with a stacked top strip or blank ruled edge bands cut off and fitted back to size, or None when
    there is nothing to cut. The vision check still judges the cut art."""
    box = edge_band_box(art)
    if box is not None:
        art = art.crop(box)
    band = seam_band(art)
    if band is None and box is None:
        return None
    if band is not None:
        art = art.crop((0, band[1], art.width, art.height))
    cut = ImageOps.fit(art, size, Image.Resampling.LANCZOS, centering=(0.5, 0.0))
    return None if seam_band(cut) is not None else cut  # a second stacked strip: nothing to gain by cutting, the check decides
