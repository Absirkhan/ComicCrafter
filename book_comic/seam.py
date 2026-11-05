"""A seam: a thin flat full-width line where the image model stacked a second strip over the scene.

find_seam keeps the cover's contract (a strip across the top; the row below it). cut_seam, for panels, also takes
a strip across the bottom, and leaves a seam in the middle alone: the part left after cropping must keep at least
KEEP of the height, or the cut would crop the panel to a sliver when it is fitted back to its size (a mid-height
seam is for the revision or a fresh draw, book_comic.revise).
"""
from typing import Optional, Tuple

from PIL import Image, ImageOps

KEEP = 0.7


def find_seam(image: Image.Image, search_share: float = 0.45) -> Optional[int]:
    """The row just below a thin, flat, full-width line across the top of the art where the model
    stacked a second strip; None when there is none. Only a run of at most 2% of the height with
    textured art on both sides counts, so a plain sky is not a seam."""
    import numpy as np
    flat = np.asarray(image.convert("RGB"), dtype=np.float32).std(axis=1).max(axis=1) < 20
    h = len(flat)
    thin, gap = max(3, int(h * 0.02)), max(2, h // 300)
    y = gap
    while y < int(h * search_share):
        if not flat[y]:
            y += 1
            continue
        run_end = y
        while run_end < h and flat[run_end]:
            run_end += 1
        if run_end - y <= thin and run_end + gap < h and not flat[y - gap] and not flat[run_end + gap]:
            return run_end
        y = run_end + 1
    return None


def _runs(image: Image.Image):
    """(start, end) of every thin flat full-width run with textured art on both sides."""
    import numpy as np
    flat = np.asarray(image.convert("RGB"), dtype=np.float32).std(axis=1).max(axis=1) < 20
    h = len(flat)
    thin, gap = max(3, int(h * 0.03)), max(2, h // 300)
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


def seam_band(image: Image.Image) -> Optional[Tuple[int, int]]:
    """The (start, end) rows of a seam whose smaller side can be cut off while KEEP of the height remains; else None."""
    runs, h = _runs(image)
    for start, end in runs:
        if end <= h * (1 - KEEP) or start >= h * KEEP:
            return start, end
    return None


def cut_seam(art: Image.Image, size: Tuple[int, int]) -> Optional[Image.Image]:
    """The art with the strip beyond a top or bottom seam cut off and fitted back to size, or None when there is no such seam."""
    band = seam_band(art)
    if band is None:
        return None
    start, end = band
    if end <= art.height * (1 - KEEP):
        return ImageOps.fit(art.crop((0, end, art.width, art.height)), size, Image.Resampling.LANCZOS, centering=(0.5, 0.0))
    return ImageOps.fit(art.crop((0, 0, art.width, start)), size, Image.Resampling.LANCZOS, centering=(0.5, 1.0))
