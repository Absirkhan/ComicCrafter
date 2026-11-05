"""Best-of-draws fallback: when every bounded draw of a panel was rejected, keep the least-bad one.

Only draws without a hard defect qualify. Readable painted-in writing (letters or words large enough to read,
fake bubbles or captions, a signature), broken anatomy, a different face and a seam (a border or dividing line that
splits the picture: a scene_mismatch whose correction names a seam, divider, border or strip) are what a reader
notices at once, so a draw with any of them is never published. Tiny or illegible pseudo-lettering (text_prominent False), even on a map
or page the hero holds, is kept outright (inspect_art turns it into faint_text). The rest (scene, design,
requirement and prop drift) is ranked: fewest failed check flags first, then fewest failed requirement
checks, then the latest draw (a redraw carries the check's corrections).
"""

import re
from typing import Dict, List, Optional, Sequence, Tuple

from book_comic.rejected_art import CHECK_NAMES, unmet_requirements

# figure_visible: a back cover must show only the setting; a person there has no face check, so it is never kept.
HARD_DEFECTS = ("bad_anatomy", "identity_mismatch", "figure_visible")
# Unasked-for gloves (user decision 2026-11-04): the most common design drift, and a kept draw showed them.
_GLOVES = re.compile(r"\b(?:fingerless|tactical|gloves?|gloved|mitts?)\b", re.I)
BARE_HANDS_MARK = "Hands: bare skin on both hands"


def unasked_gloves(found: Dict, prompt: str) -> bool:
    """The check saw gloves (in a correction or a prop/design observation) on a brief that asked for bare hands."""
    if BARE_HANDS_MARK not in (prompt or "") or not any(found.get(k) for k in ("design_mismatch", "prop_mismatch", "requirement_mismatch")):
        return False
    seen = [*(found.get("corrections") or []), *(str(c.get("observed", "")) for c in found.get("prop_checks") or [] if isinstance(c, dict)),
            *(str(c.get("observed", "")) for c in found.get("requirement_checks") or [] if isinstance(c, dict))]
    return any(isinstance(s, str) and _GLOVES.search(s) for s in seen)


def hard_defect(found: Dict) -> bool:
    """Broken anatomy, a different face, a seam, unasked-for gloves, or writing that is prominent or of unknown prominence."""
    text = bool(found.get("has_text")) and found.get("text_prominent") is not False
    seam = bool(found.get("scene_mismatch")) and bool(found.get("seam"))
    return text or seam or bool(found.get("gloves")) or any(found.get(k) for k in HARD_DEFECTS)


def _rank(found: Dict, requirements: Sequence[Dict]) -> Tuple[int, int]:
    flags = sum(1 for k in CHECK_NAMES if found.get(k))
    return flags, len(unmet_requirements(found, requirements))  # the same unmet-row rule as the check and the reasons


def pick_fallback(rejected: Sequence[Tuple[object, Dict]], requirements: Sequence[Dict] = ()) -> Optional[int]:
    """Index of the least-bad rejected draw without a hard defect, or None when every draw has one."""
    eligible: List[Tuple[Tuple[int, int], int]] = [
        (_rank(found, requirements), i) for i, (_, found) in enumerate(rejected) if not hard_defect(found)
    ]
    # A tie goes to the later draw: each redraw carries the check's corrections, so it is usually closer to the brief
    # (ed88ca80 panel 1 kept draw 1, the closest crop, over draw 2, the better establishing shot).
    return min(eligible, key=lambda ranked: (ranked[0], -ranked[1]))[1] if eligible else None


def fallback_verification(found: Dict) -> Dict:
    """Verification kept on fallback art: only matching prop observations may become canonical anchors."""
    props = [c for c in found.get("prop_checks", []) if c.get("matches") is True]
    return {**found, "prop_checks": props, "fallback": True}
