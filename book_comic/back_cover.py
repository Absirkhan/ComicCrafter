"""The comic's back cover: the story's setting with nobody in it, lettered with a tagline and a blurb.

It is drawn after the front cover and takes the unlettered front cover art as a style reference. Nobody may appear:
a person there has no face check, so a draw with a figure is redrawn and never kept (best_draw.HARD_DEFECTS).
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Sequence

from PIL import Image, ImageOps

from book_comic.art_check import ArtCheckError, inspect_art, request_art, require_checked
from book_comic.back_cover_lettering import letter_back_cover
from book_comic.best_draw import pick_fallback
from book_comic.cover import find_seam
from book_comic.cover_lettering import CoverFonts
from book_comic.image_prompts import back_cover_prompt
from book_comic.margins import trim_margins
from book_comic.rejected_art import report as report_rejected
from book_comic.render import image_url
from generation.openrouter_image_client import OpenRouterImageClient, closest_aspect_ratio
from generation.vision_client import VisionClient

logger = logging.getLogger(__name__)

ATTEMPTS = 3


def _skipped(audit, draw: int, reason: str) -> None:
    if audit is not None:
        audit.append({"accepted": False, "kind": "back_cover", "draw": draw, "skipped": reason, "requirements": [], "checks": {}})


def render_back_cover(
    cast: Dict,
    back: Dict,
    size: tuple,
    path: Path,
    images: OpenRouterImageClient,
    vision: VisionClient,
    style_art: Optional[Image.Image] = None,
    fonts: Optional[CoverFonts] = None,
    dpi: Optional[int] = None,
    audit=None, on_reject=None,
) -> Path:
    """Draw and letter the back cover; at most ATTEMPTS image calls, then the least-bad draw without a hard defect.

    Args:
        cast: Character sheet (its style is used; no character is drawn)
        back: {"scene" (the setting), "tagline", "blurb", optional "footer", "title_font"}
        size: Cover size in pixels (the page size)
        path: Where the lettered back cover PNG is saved
        style_art: The unlettered front cover art, sent as a style reference
        on_reject: Optional hook that sees each inspected, rejected draw
    """
    references, roles = ([image_url(style_art)], ["style"]) if style_art is not None else ([], [])
    prompt = back_cover_prompt(cast, back, size, roles)
    rejected = []
    art = found = None
    for draw in range(1, ATTEMPTS + 1):
        art = request_art(images, prompt, references, closest_aspect_ratio(*size))
        trimmed, margins = trim_margins(art, size[0] / size[1])
        if margins == "redraw" and draw < ATTEMPTS:
            _skipped(audit, draw, "margins")
            continue
        art = ImageOps.fit(trimmed if margins == "trimmed" else art, size)
        if find_seam(art) is not None:
            _skipped(audit, draw, "seam")
            continue
        found = inspect_art(art, vision, setting=True)
        report = {"accepted": None, "requirements": [], "checks": found, "kind": "back_cover"}
        if audit is not None:
            audit.append(report)
        try:
            clean = require_checked(found)
        except ArtCheckError:
            report_rejected(on_reject, draw, art, found, True, prompt, [])
            raise
        report["accepted"] = clean
        if clean:
            break
        report_rejected(on_reject, draw, art, found, False, prompt, [])
        rejected.append((art, found, report))
    else:
        best = pick_fallback([(a, f) for a, f, _ in rejected])
        if best is None:
            raise ArtCheckError("comic_back_cover_rejected")
        art, found, report = rejected[best]
        report["fallback"] = True
        logger.warning(f"Back cover: every draw was rejected; keeping the least-bad one (draw {best + 1})")

    dpi_tag = {"dpi": (dpi, dpi)} if dpi else {}
    letter_back_cover(art, back, fonts).save(path, format="PNG", optimize=True, **dpi_tag)
    logger.info(f"Saved back cover {path}")
    return path
