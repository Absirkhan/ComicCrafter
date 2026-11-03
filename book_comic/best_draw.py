"""Best-of-draws fallback: when every bounded draw of a panel was rejected, keep the least-bad one.

Only draws without a hard defect qualify. Readable painted-in writing (letters or words large enough to read,
fake bubbles or captions, a signature), broken anatomy, a different face and a seam (a border or dividing line that
splits the picture: a scene_mismatch whose correction names a seam, divider, border or strip) are what a reader
notices at once, so a draw with any of them is never published. Tiny or illegible pseudo-lettering (text_prominent False), even on a map
or page the hero holds, is soft: still redrawn, but a kept draw may carry it. The rest (scene, design,
requirement and prop drift) is ranked: fewest failed check flags first, then fewest failed requirement
checks, then the earliest draw.
"""

from typing import Dict, List, Optional, Sequence, Tuple

from book_comic.rejected_art import CHECK_NAMES

HARD_DEFECTS = ("bad_anatomy", "identity_mismatch")


def hard_defect(found: Dict) -> bool:
    """Broken anatomy, a different face, a seam, or writing that is prominent or of unknown prominence."""
    text = bool(found.get("has_text")) and found.get("text_prominent") is not False
    seam = bool(found.get("scene_mismatch")) and bool(found.get("seam"))
    return text or seam or any(found.get(k) for k in HARD_DEFECTS)


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
