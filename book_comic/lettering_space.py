"""Where a lettered panel leaves room for its caption and bubbles, per shot, and what the checker may say about it.

The lettering (layout.captions / layout.comic_bubbles) is placed after drawing: a caption starts in a top
corner and otherwise searches the whole panel, and bubbles search the whole panel, both only avoiding the
protected faces, focal hands and props the planner marks. So lettering needs one calm area somewhere, not
a clear upper third. A clear upper third is natural only when the figure is small (extreme long and wide
shots: sky, ceiling or upper wall above it). Asking for it in a medium shot or close-up fought the hard
crop (framing.py): the vision checker rejected correct art "to keep the upper third clear of the head".
"""

import re
from typing import Dict, Optional, Sequence

from book_comic.comic_rules import scene_shot
from book_comic.framing import detail_framing

FULL_BLEED = "This is one full-bleed illustration, never a blank strip, inset, seam or text box."
BAND = (
    "CALM AREA: keep the upper third of the canvas as calm, low-detail natural setting above the figure "
    "(sky, ceiling, treetops or upper wall), with faces, important hands and focal props below it."
)
SIDE = (
    "CALM AREA: keep the requested crop; the head may reach into the upper third of the frame, so never "
    "lower, shrink or re-crop the figure to make room. Instead place the figure slightly off-centre so that one "
    "side of the frame, about one third of its width, is calm, low-detail background (plain wall, sky, haze or "
    "soft shadow) with no face, hand or focal prop in it."
)
CORNER = (
    "CALM AREA: keep one corner of the frame, about one third of its width, as calm plain surface or soft "
    "background with no hand, foot or focal object in it."
)
ANY = (
    "CALM AREA: keep one calm, low-detail area of background (at the top, a side or a corner, about one "
    "third of the frame) free of faces, important hands and focal props."
)
SHOT_SPACE = {"Extreme long shot": BAND, "Wide shot": BAND, "Medium shot": SIDE, "Close-up": SIDE}

# For the checker: lettering space is the lettering step's job, never a reason to reject the art.
CHECK_NOTE = (
    " CALM AREA lines in the brief are soft guidance for a later lettering step: never set scene_mismatch "
    "and never write a correction about head height, the upper third, lowering or shrinking a figure for lettering "
    "clearance, or empty space for text. Shot fractions are approximate: a wide-shot figure filling up to about "
    "three-quarters of the height with the head and feet visible is still a wide shot; an extreme long shot whose "
    "figure is taller than about one-quarter of the image height is still wrong."
)
LETTERING_CORRECTION = re.compile(
    r"\b(?:upper|top) third\b|\blettering (?:clearance|space|area|band)\b|\bclear(?:ance)? for (?:text|lettering|captions?)\b",
    re.I)


def lettering_space(panel: Dict, requirements: Sequence[Dict] = ()) -> str:
    """The panel's CALM AREA line ("" when the panel has no caption or dialogue)."""
    if not (panel.get("caption") or any(d.get("text") for d in panel.get("dialogue", []))):
        return ""
    if detail_framing(requirements):
        line = CORNER
    else:
        line = SHOT_SPACE.get(scene_shot(panel.get("scene", "")) or "", ANY)
    return f"{line} {FULL_BLEED}\n"


def useful_corrections(corrections: Optional[Sequence[str]]) -> list:
    """The checker's corrections without lettering-clearance advice, which would undo the requested crop."""
    return [c for c in corrections or [] if not LETTERING_CORRECTION.search(c)]
