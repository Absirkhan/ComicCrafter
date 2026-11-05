"""A seam: a thin flat full-width line near the top where the image model stacked a second strip over the scene."""
from typing import Optional

from PIL import Image


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
