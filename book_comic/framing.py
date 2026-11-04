"""Hard camera-framing and facing rules for panel prompts.

The image model tends to ignore the shot named at the start of a scene (a "Medium shot" drawn
full-body, a hand detail drawn with the torso) and to turn the hero away from what the scene says
they face. This module turns the scene's shot label into explicit crop limits and, when the scene
states it, the hero's facing direction. Nothing is invented: no label, no crop; no stated target,
no orientation line.
"""

import re
from typing import Dict, List, Optional, Sequence, Tuple

from book_comic.comic_rules import SINGLE_IMAGE_RULE, scene_shot
from book_comic.scene_requirements import scene_requirements

SHOT_FRAMING = {
    "Extreme long shot": (
        "EXTREME LONG SHOT: establish the environment. The camera is far away: every person is a tiny full figure "
        "about one-tenth of the image height, standing in the middle distance or background, never in the "
        "foreground; buildings, landscape or sky fill most of the canvas. Do not copy the full-body scale of the "
        "photo or character sheet. Faces need not be readable at this distance."
    ),
    "Wide shot": (
        "WIDE SHOT: the whole body is visible from the top of the head to the feet, with clear space around the "
        "figure on every side and the setting readable; the figure fills at most about two-thirds of the image "
        "height. Do not crop off the head or the feet: both shoes and the ground they stand on are drawn above the "
        "bottom edge, with a strip of floor or ground visible below them."
    ),
    "Medium shot": (
        "MEDIUM SHOT: crop at the waist. Show the character from the top of the head down to the waist only; "
        "hips, legs and feet are outside the frame. Do not draw a full-body figure: this crop overrides the "
        "full-body composition of the photo or character sheet."
    ),
    "Close-up": (
        "CLOSE-UP: the camera is very near the scene's focal subject, which fills most of the frame. When that "
        "subject is a face, show the head and shoulders only, cropped at the upper chest; waist, legs and feet "
        "are outside the frame."
    ),
}
HAND_DETAIL = (
    "LIMB-ONLY MACRO DETAIL. Crop at the wrist or short sleeve cuff; show only the specified hand, cuff and focal "
    "objects. Head, neck, shoulders, chest, torso, waist and all other limbs remain outside the frame; a second "
    "hand appears only when the scene names both hands. This crop overrides the full-body reference composition. "
    "Camera: above the hand, looking down at the surface or object it touches, so that surface fills the background; "
    "the forearm enters from a frame edge and the character's body is behind the camera, never behind the hand."
)
FEET_DETAIL = (
    "LIMB-ONLY MACRO DETAIL. Crop at the lower legs; show only the specified feet and focal objects. Head, neck, "
    "shoulders, torso, waist and all other limbs remain outside the frame. This crop overrides the full-body "
    "reference composition. Camera: low and close to the ground, so the ground fills the background."
)

_TARGET = (r"(?P<t>(?:the|a|an|his|her|their|its|[A-Z][\w'’-]*)\b[^,.;:!?]{0,80}?)"
           r"(?=\s*(?:[,.;:!?]|$|\s(?:while|as|and then|then|with|where|which|who|until|so that)\b))")
_STAND = (r"(?:stands?|standing|stood|kneels?|kneeling|knelt|waits?|waiting|pauses?|pausing|halts?|halting|"
          r"stops?|stopping|sits?|sitting|crouch(?:es)?|crouching|lingers?|lingering)")
_MOVE = (r"(?:walks?|walking|runs?|running|heads?|heading|steps?|stepping|strides?|striding|moves?|moving|"
         r"creeps?|creeping|hurries|hurrying|marches|marching|climbs?|climbing|crawls?|crawling|rides?|riding|"
         r"swims?|swimming|wades?|wading|rushes|rushing|edges?|edging|sprints?|sprinting)")
_ADVERB = r"(?:(?:slowly|quickly|cautiously|carefully|straight|forward|still|alone|frozen|silently|back)\s+)?"
# (kind, pattern) in priority order: "away" phrases first so "turned away from" is never read as "turned".
ORIENTATION_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("away", rf"\b(?:{_MOVE}|backs?|backing|turns?|turning|turned|faces|facing|looks?|looking)\s+{_ADVERB}away\s+from\s+{_TARGET}"),
    ("away", rf"\bwith\s+(?:his|her|their|\w+'s)\s+back\s+(?:turned\s+)?to(?:wards?)?\s+{_TARGET}"),
    ("face", rf"\b(?:faces|facing|faced)\s+(?:toward|towards|to\s+)?{_TARGET}"),
    ("face", rf"\b(?:turns?|turning|turned)\s+(?:to\s+face|toward|towards)\s+{_TARGET}"),
    ("face", rf"\b{_STAND}\s+{_ADVERB}(?:before|in\s+front\s+of)\s+{_TARGET}"),
    ("look", rf"\b(?:looks?|looking|gazes?|gazing|stares?|staring|peers?|peering|glances?|glancing|squints?|squinting)"
             rf"\s+(?:(?:up|down|out|back|over)\s+)?(?:at|toward|towards|into)\s+{_TARGET}"),
    ("move", rf"\b{_MOVE}\s+{_ADVERB}(?:toward|towards|into|up\s+to)\s+{_TARGET}"),
    ("move", rf"\b(?:approaches|approaching|approached|nears|nearing)\s+{_TARGET}"),
)
VIEWER = re.compile(r"^(?:the\s+)?(?:viewer|camera|reader)s?$", re.I)
FROM_BEHIND = re.compile(r"\b(?:seen|shown|viewed|drawn)\s+from\s+behind\b|\bback\s+(?:is\s+)?(?:turned\s+)?to(?:wards?)?\s+the\s+(?:viewer|camera|reader)\b", re.I)
_TRIM = re.compile(r"\s+(?:and|but|or)\s+(?:then\s+)?(?:he|she|they|it|\w+s)\b.*$")


def _names(cast: Dict) -> Tuple[List[str], List[str]]:
    """(hero names, other character names): the first cast member, always also called Hero."""
    characters = [c for c in cast.get("characters") or [] if isinstance(c, dict)]
    def names(c):
        return [n for n in (c.get("name_en"), c.get("name")) if isinstance(n, str) and n.strip()]
    hero = ["Hero"] + (names(characters[0]) if characters else [])
    others = [n for c in characters[1:] for n in names(c) if n not in hero]
    return hero, others


def _last(names: Sequence[str], text: str) -> int:
    """End index of the last whole-word occurrence of any name in text, or -1."""
    ends = [m.end() for n in names for m in re.finditer(rf"\b{re.escape(n)}\b", text, re.I)]
    return max(ends, default=-1)


def scene_orientation(scene: str, cast: Optional[Dict] = None) -> List[Tuple[str, str]]:
    """(kind, target) pairs for what the hero faces, looks at, moves toward or away from.

    Conservative: a phrase counts only in a sentence that names the hero before it, with no other
    character named in between, so another character's direction is never given to the hero.
    kind is face, look, move, away, viewer (faces the camera) or back (back to the camera).
    """
    hero, others = _names(cast or {})
    found: List[Tuple[str, str]] = []
    for sentence in re.split(r"(?<=[.!?;])\s+", scene):
        if FROM_BEHIND.search(sentence) and _last(hero, sentence) >= 0:
            found.append(("back", "the viewer"))
        taken = []
        for kind, pattern in ORIENTATION_PATTERNS:
            for match in re.finditer(pattern, sentence):
                if any(s <= match.start() < e for s, e in taken):
                    continue
                before = sentence[:match.start()]
                if _last(hero, before) < 0 or _last(others, before) > _last(hero, before):
                    continue
                target = _TRIM.sub("", match.group("t")).strip()
                target = " ".join(target.split()[:8])
                if not target or any(re.fullmatch(re.escape(n), target, re.I) for n in hero):
                    continue
                taken.append((match.start(), match.end()))
                found_kind = kind
                if VIEWER.match(target):
                    found_kind, target = ("back", "the viewer") if kind == "away" else ("viewer", "the viewer")
                if all(t.lower() != target.lower() for _, t in found):
                    found.append((found_kind, target))
    return found[:2]


def orientation_lines(scene: str, cast: Optional[Dict] = None) -> str:
    """ORIENTATION lines for the hero, one per stated target ("" when the scene states none)."""
    lines = []
    names = _names(cast or {})[0]
    hero = names[1] if len(names) > 1 else names[0]
    for kind, target in scene_orientation(scene, cast):
        depth = (f" If {target} is farther from the viewer than {hero}, show {hero} from behind or in a three-quarter "
                 f"back view; do not turn {hero} around toward the camera.")
        if kind == "face":
            lines.append(f"ORIENTATION: {hero} faces {target}: {hero}'s face, chest and feet point toward {target}, "
                         f"which is in front of {hero}, never behind.{depth}")
        elif kind == "look":
            lines.append(f"ORIENTATION: {hero} looks at {target}: {hero}'s head and eyes are turned toward {target}, "
                         f"which is in front of {hero}, never behind.{depth}")
        elif kind == "move":
            lines.append(f"ORIENTATION: {hero} moves toward {target}: body, face and steps point at {target}, "
                         f"which is ahead of {hero}, never behind.{depth}")
        elif kind == "away":
            lines.append(f"ORIENTATION: {hero} faces away from {target}: {hero}'s back is toward {target}, "
                         f"which is behind {hero}.")
        elif kind == "viewer":
            lines.append(f"ORIENTATION: {hero} faces the viewer: face and chest are turned toward the camera.")
        elif kind == "back":
            lines.append(f"ORIENTATION: {hero}'s back is toward the viewer; the face is hidden or at most in profile.")
    return "".join(line + "\n" for line in lines)


def detail_framing(requirements: Sequence[Dict]) -> Optional[str]:
    """hand_detail_only / feet_detail_only when the scene asks for a limb-only crop."""
    return next((r["expected"] for r in requirements if r.get("attribute") == "framing"
                 and r.get("expected") in ("hand_detail_only", "feet_detail_only")), None)


def shot_framing(scene: str, requirements: Sequence[Dict] = ()) -> str:
    """The hard crop for the scene's shot label (a limb-only detail overrides the label), or ""."""
    detail = detail_framing(requirements)
    if detail == "hand_detail_only":
        return HAND_DETAIL
    if detail == "feet_detail_only":
        return FEET_DETAIL
    return SHOT_FRAMING.get(scene_shot(scene) or "", "")


def framing_block(cast: Dict, panel: Dict, requirements: Optional[Sequence[Dict]] = None) -> str:
    """Framing, orientation and the single-image rule: the opening lines of a panel prompt, repeated on redraw."""
    scene = panel.get("scene", "")
    if requirements is None:
        requirements = scene_requirements(scene, panel.get("requirements", []))
    crop = shot_framing(scene, requirements)
    return (crop + "\n" if crop else "") + orientation_lines(scene, cast) + SINGLE_IMAGE_RULE + "\n"
