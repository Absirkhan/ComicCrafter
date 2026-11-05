"""A seam: a thin flat full-width line where the image model stacked a second strip over the scene.

find_seam keeps the cover's contract (a strip across the top; the row below it). cut_seam, for panels, cuts the
same kind of strip: a band of at most STRIP of the height across the top. A flat line anywhere lower is left alone,
because a floor, table or water edge looks the same to a pixel scan and cutting there would publish a panel without
its feet (review 2026-11-05); a seam lower down is for the revision or a fresh draw (book_comic.revise). The audit
marks a cut draw ("seam_cut"), and the vision check sees the cut art.
"""
from typing import List, Optional, Tuple

from PIL import Image, ImageOps

STRIP = 0.15  # a stacked strip is a band across the top; fitting the rest back to size crops at most this share of the width
THIN = 0.02  # a seam is at most this share of the height; thicker flat bands are sky, floor or a wall
SCAN_WIDTH = 512  # row flatness is a coarse property: scanned on a reduced copy, rows mapped back


def _runs(image: Image.Image) -> Tuple[List[Tuple[int, int]], int]:
    """(start, end) of every thin flat full-width run with textured art on both sides, and the height (full-size rows)."""
    import numpy as np
    scale = max(1, image.width // SCAN_WIDTH)
    small = image.convert("RGB").reduce(scale) if scale > 1 else image.convert("RGB")
    flat = np.asarray(small, dtype=np.float32).std(axis=1).max(axis=1) < 20
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
        if run_end - y <= thin and run_end + gap < h and not flat[y - gap] and not flat[run_end + gap]:
            runs.append((y * scale, run_end * scale))
        y = run_end + 1
    return runs, h * scale


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


def cut_seam(art: Image.Image, size: Tuple[int, int]) -> Optional[Image.Image]:
    """The art with the strip above a top seam cut off and fitted back to size, or None when there is no such seam."""
    band = seam_band(art)
    if band is None:
        return None
    cut = ImageOps.fit(art.crop((0, band[1], art.width, art.height)), size, Image.Resampling.LANCZOS, centering=(0.5, 0.0))
    return None if seam_band(cut) is not None else cut  # a second stacked strip: nothing to gain by cutting, the check decides
