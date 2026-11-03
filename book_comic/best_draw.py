"""Best-of-draws fallback: when every bounded draw of a panel was rejected, keep the least-bad one.

Only draws without a hard defect qualify. Prominent painted-in writing (readable foreground words, writing on
the hero or a key prop, fake bubbles or captions, a signature), broken anatomy and a different face are what a
reader notices at once, so a draw with any of them is never published. Small background pseudo-lettering
(text_prominent False) is soft: still redrawn, but a kept draw may carry it. The rest (scene, design,
requirement and prop drift) is ranked: fewest failed check flags first, then fewest failed requirement
checks, then the earliest draw.
"""

from typing import Dict, List, Optional, Sequence, Tuple

from book_comic.rejected_art import CHECK_NAMES

HARD_DEFECTS = ("bad_anatomy", "identity_mismatch")


def hard_defect(found: Dict) -> bool:
    """Broken anatomy, a different face, or writing that is prominent or of unknown prominence."""
    text = bool(found.get("has_text")) and found.get("text_prominent") is not False
    return text or any(found.get(k) for k in HARD_DEFECTS)


def _rank(found: Dict) -> Tuple[int, int]:
    flags = sum(1 for k in CHECK_NAMES if found.get(k))
    requirements = sum(1 for c in found.get("requirement_checks", []) if isinstance(c, dict) and c.get("matches") is not True)
    return flags, requirements


def pick_fallback(rejected: Sequence[Tuple[object, Dict]]) -> Optional[int]:
    """Index of the least-bad rejected draw without a hard defect, or None when every draw has one."""
    eligible: List[Tuple[Tuple[int, int], int]] = [
        (_rank(found), i) for i, (_, found) in enumerate(rejected) if not hard_defect(found)
    ]
    return min(eligible)[1] if eligible else None


def fallback_verification(found: Dict) -> Dict:
    """Verification kept on fallback art: only matching prop observations may become canonical anchors."""
    props = [c for c in found.get("prop_checks", []) if c.get("matches") is True]
    return {**found, "prop_checks": props, "fallback": True}
