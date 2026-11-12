"""The comic's front cover: one portrait hero shot the size of a page, lettered afterwards.

The image model sometimes stacks a second strip of the scene over the top (a seam), paints in
writing, or puts the head where the title goes. Seams and title placement are repaired locally;
explicit art defects get at most one more image call, and failed inspection blocks publication.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Sequence

from PIL import Image, ImageOps

from book_comic.best_draw import pick_fallback, unasked_gloves
from book_comic.comic_rules import cover_scene
from book_comic.margins import trim_margins
from book_comic.seam import find_seam
from book_comic.art_check import ArtCheckError, inspect_art, request_art, require_checked
from book_comic.cover_lettering import CoverFonts, letter_cover
from book_comic.image_prompts import cover_prompt, cover_requirements
from book_comic.rejected_art import report as report_rejected
from book_comic.revise import data_url, revision_prompt
from book_comic.render import image_url
from generation.openrouter_image_client import OpenRouterImageClient, closest_aspect_ratio
from generation.vision_client import VisionClient

logger = logging.getLogger(__name__)

# The one-line title and the starring line end near 14% of the height; a head starting above 20%
# would crowd them (measured on real covers: 0.16 crowds, 0.19-0.24 leaves clear space).
HEAD_TOP_MIN = 0.2
# A head above 8.5% of the height prints in the printers' top margin (12.7 mm inside the trim): BookPod's B5 cuts
# 7.8 mm of the 256.8 mm art above the trim (20.8 mm, 8.1%), Lulu's comic 3.2 mm of 266.7 mm (6.1%). Such a draw is
# drawn again while draws remain; it is never a reason to lose the cover (the last such draw is kept).
HEAD_SAFE_MIN = 0.085
HEADROOM_FIX = ("the camera is pulled back a little so the main character sits lower in the frame, with a clear stretch "
                "of the setting (its sky, ceiling or upper wall), at least one eighth of the canvas height, above the top of the hair or hat")
# Three draws, then the least-bad one without a hard defect (as for panels): with two draws and no fallback, a cover
# lost the whole preview (2 of 6 test pages on 2026-11-04, a duplicate prop or a seam).
ATTEMPTS = 3


def _skipped(audit, draw: int, reason: str) -> None:
    """A cover draw thrown away before the vision check is recorded, so a failed cover shows why it had fewer checks."""
    if audit is not None:
        audit.append({"accepted": False, "kind": "cover", "draw": draw, "skipped": reason, "requirements": [], "checks": {}})


def panel_strip(arts: Sequence[Image.Image], height: int = 512, gap: int = 16) -> Optional[Image.Image]:
    """Panels side by side in reading order, so the cover sees every prop and companion. None if empty."""
    if not arts:
        return None
    scaled = [a.convert("RGB").resize((max(1, round(a.width * height / a.height)), height)) for a in arts]
    strip = Image.new("RGB", (sum(a.width for a in scaled) + gap * (len(scaled) - 1), height), "white")
    x = 0
    for art in scaled:
        strip.paste(art, (x, 0))
        x += art.width + gap
    return strip


def render_cover(
    cast: Dict,
    cover: Dict,
    size: tuple,
    path: Path,
    images: OpenRouterImageClient,
    vision: VisionClient,
    panels: Sequence[Image.Image] = (),
    references: Sequence[str] = (),
    reference_roles: Sequence[str] = (),
    fonts: Optional[CoverFonts] = None,
    dpi: Optional[int] = None,
    requirements=(), prop_anchors=None, audit=None, on_reject=None, art_path: Optional[Path] = None,
) -> Path:
    """Draw and letter the cover; at most ATTEMPTS image calls.

    Remove a seam locally, then accept only inspected art with matching identity, designs and scene.
    Unchecked or persistently rejected art raises. A high head moves lettering instead of causing a redraw;
    only a head in the printers' top margin (HEAD_SAFE_MIN) is drawn again, and never fails the cover.

    Args:
        cast: Character sheet (style, characters, optional props)
        cover: {"scene", "title", optional "starring", "footer", "title_font"}
        size: Cover size in pixels (normally the page size)
        path: Where the lettered cover PNG is saved
        images: Image client
        vision: Vision client for the text and head check
        panels: The first page's unlettered panels, sent as one reference strip
        references: Other reference URLs (photo, character sheet), described by reference_roles
        reference_roles: Kind of each reference (see image_prompts.REFERENCE_ROLES)
        fonts: Cover faces (cover["title_font"] still overrides the title face)
        dpi: DPI tag for the saved PNG
        on_reject: Optional hook that sees each inspected, rejected draw (see art_check.draw_checked)
        art_path: Where to also save the chosen art unlettered (the back cover's style reference)
    """
    # A cover keeps its own framing: the prompt strips the scene's shot and limb-only clauses (image_prompts.cover_prompt);
    # the check uses the same scene and the same requirements, without framing.
    requirements = cover_requirements(cover_scene(cover.get("scene", "")), requirements)
    references, roles = list(references), list(reference_roles)
    strip = panel_strip(panels)
    if strip is not None:
        references.append(image_url(strip))
        roles.append("panels")
    prompt = cover_prompt({**cast, "prop_anchors": prop_anchors or {}}, {**cover, "requirements": requirements}, roles)

    rejected = []
    for draw in range(1, ATTEMPTS + 1):
        # Draw 2 revises a rejected draw 1 (book_comic.revise); a skipped draw (margins, seam) leaves nothing to revise.
        revised = draw == 2 and bool(rejected)
        if revised:
            headroom = (HEADROOM_FIX,) if rejected[-1][2].get("head_in_margin") else ()
            art = request_art(images, revision_prompt(prompt, rejected[-1][1], headroom, requirements, prop_anchors), [*references, data_url(rejected[-1][0])], closest_aspect_ratio(*size))
        else:
            art = request_art(images, prompt, references, closest_aspect_ratio(*size))
        trimmed, margins = trim_margins(art, size[0] / size[1])
        if margins == "redraw" and draw < ATTEMPTS:
            _skipped(audit, draw, "margins")
            continue
        art = ImageOps.fit(trimmed if margins == "trimmed" else art, size)
        seam = find_seam(art)
        if seam is not None:
            art = ImageOps.fit(art.crop((0, seam, art.width, art.height)), size, centering=(0.5, 0.0))
            if find_seam(art) is not None:
                _skipped(audit, draw, "seam")
                continue
        found = inspect_art(art, vision, references=references, context=prompt, requirements=requirements,
                            props=cast.get("props", []), anchors=prop_anchors)
        if unasked_gloves(found, prompt):
            found = {**found, "gloves": True}
        report = {"accepted": None, "requirements": requirements, "checks": found, "kind": "cover", **({"revised": True} if revised else {})}
        if audit is not None:
            audit.append(report)
        try:
            clean = require_checked(found, require_head=True)
        except ArtCheckError:
            report_rejected(on_reject, draw, art, found, True, prompt, requirements)
            raise
        in_margin = clean and found["head_top"] < HEAD_SAFE_MIN
        report["accepted"] = clean and not in_margin
        if clean and not in_margin:
            head = found["head_top"]
            break  # a high head is handled by local title placement, without another image call
        if in_margin:  # sound art whose head would print in the top margin: not a vision rejection, so not reported as one
            report["head_in_margin"] = True
        else:
            report_rejected(on_reject, draw, art, found, False, prompt, requirements)
        rejected.append((art, found, report))
    else:
        best = pick_fallback([(a, f) for a, f, _ in rejected], requirements)
        if best is None:
            raise ArtCheckError("comic_cover_rejected")
        art, found, report = rejected[best]
        report["fallback"] = True
        head = found["head_top"]
        logger.warning(f"Cover: every draw was rejected; keeping the least-bad one (draw {best + 1})")

    dpi_tag = {"dpi": (dpi, dpi)} if dpi else {}
    if art_path is not None:
        art.save(art_path, format="PNG")
    # Move the title instead of drawing again when the accepted head is in the title block.
    letter_cover(art, cover, fonts, title_at_bottom=head < HEAD_TOP_MIN).save(path, format="PNG", optimize=True, **dpi_tag)
    logger.info(f"Saved cover {path}")
    return path
