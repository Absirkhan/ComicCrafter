"""A seam: a thin flat full-width line where the image model stacked a second strip over the scene.

find_seam keeps the cover's contract (a strip across the top; the row below it). cut_seam, for panels, also takes
a strip across the bottom, and leaves a seam in the middle alone: a stacked strip is a band of at most STRIP of the
height; cutting more would crop the panel to a sliver when it is fitted back to its size, and a flat line deeper in
the picture is more likely a floor or table edge (a mid-height seam is for the revision or a fresh draw,
book_comic.revise). The audit marks a cut draw ("seam_cut").
"""
from typing import List, Optional, Tuple

from PIL import Image, ImageOps

STRIP = 0.25
THIN = 0.02  # a seam is at most this share of the height; thicker flat bands are sky, floor or a wall


def _runs(image: Image.Image) -> Tuple[List[Tuple[int, int]], int]:
    """(start, end) of every thin flat full-width run with textured art on both sides, and the height."""
    import numpy as np
    flat = np.asarray(image.convert("RGB"), dtype=np.float32).std(axis=1).max(axis=1) < 20
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
    """The (start, end) rows of a seam within STRIP of the top or the bottom edge, else None."""
    runs, h = _runs(image)
    return next(((start, end) for start, end in runs if end <= h * STRIP or start >= h * (1 - STRIP)), None)


def cut_seam(art: Image.Image, size: Tuple[int, int]) -> Optional[Image.Image]:
    """The art with the strip beyond a top or bottom seam cut off and fitted back to size, or None when there is no such seam."""
    band = seam_band(art)
    if band is None:
        return None
    start, end = band
    if end <= art.height * STRIP:
        return ImageOps.fit(art.crop((0, end, art.width, art.height)), size, Image.Resampling.LANCZOS, centering=(0.5, 0.0))
    return ImageOps.fit(art.crop((0, 0, art.width, start)), size, Image.Resampling.LANCZOS, centering=(0.5, 1.0))
