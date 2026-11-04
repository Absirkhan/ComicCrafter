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

# Never describe the calm area as a region with its own geometry ("one side, two-fifths of the width", "the
# scenery beside the figure"): the image model then draws blank side strips with seams (live check
# 2026-11-03), as it stacked a strip on covers asked for an empty top. Only a simple background is asked for.
FULL_BLEED = ("It is part of the one continuous scene, with the same light and perspective, never a blank or "
              "separate strip, inset, seam or box.")
# Wide and extreme long shots: never name the upper third or a band (production 2026-11-03: wide shots asked
# for "simple scenery across the upper third" drew a framed box or a dividing line across the top on every draw).
BAND = (
    "CALM AREA: above the figure, the same setting simply carries on up to the top edge as open, low-detail "
    "scenery (sky, ceiling, treetops or building tops), with faces, important hands and focal props lower down."
)
SIDE = (
    "CALM AREA: keep the requested crop; the head may reach into the upper third of the frame, so never "
    "lower, shrink or re-crop the figure to make room. Compose by the rule of thirds with the figure slightly "
    "off-centre, and keep the background simple and low-detail (open sky, a plain wall or soft shadow), with "
    "fine detail only on the focal subject."
)
CORNER = (
    "CALM AREA: let one corner show simple, low-detail surface or background from the same setting, with no "
    "hand, foot or focal object there."
)
ANY = (
    "CALM AREA: let part of the setting (above or beside the subject) be simple, low-detail scenery, free of "
    "faces, important hands and focal props."
)
SHOT_SPACE = {"Extreme long shot": BAND, "Wide shot": BAND, "Medium shot": SIDE, "Close-up": SIDE}

# For the checker: lettering space is the lettering step's job, never a reason to reject the art.
CHECK_NOTE = (
    " CALM AREA lines in the brief are soft guidance for a later lettering step: never set scene_mismatch "
    "and never write a correction about head height, the upper third, lowering or shrinking a figure for lettering "
    "clearance, or empty space for text. Shot fractions are approximate: a wide-shot figure filling up to about "
    "three-quarters of the height with the head and feet visible is still a wide shot; an extreme long shot is "
    "right while the surroundings dominate and the figure is a small full figure up to about one-third of the image "
    "height, and wrong only when the figure is taller than that or cropped. Facing direction alone is never a reason "
    "to fail an extreme long shot."
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
