"""Staging the art check treats as advisory, and squashed proportions, which it does not.

A live 20-page comic (2026-11-12) rejected 14 draws; about 10 of the first 12 were good pictures:
- a city map "held in left hand at side, right hand on chest" or "held outward in front of torso rather than pressed
  against chest": the hero holds the map, which is what a reader follows;
- a wide view of the place with the hero cut at the shins or knees ("Frame as a wide shot with the entire body visible
  from head to feet"). The revision of that draw kept the composition and squeezed the body into the same height: an
  adult with short, stubby legs, which passed the check and was printed (page 5 panel 1);
- the hero beside the building she approaches, "walking toward the camera".

Unchanged on purpose: an object that is absent, dropped, put down or held by someone else; a cropped head; a close-up
or medium shot delivered for a wide shot; a movement that reverses the story beat; expression, focal action, another
person near the hero, anatomy and identity. The draw prompt still asks for head to feet (framing.SHOT_FRAMING).
"""

import re
from typing import Dict, Optional, Sequence

from book_comic.check_tolerance import prop_marks_only, scene_marking_only

# scene_mismatch and direction rows: the beat, not the angle. Wording only: the checker's direction text is free text.
DIRECTION_NOTE = (
    " Judge movement and facing by the story beat, never by the exact angle; ORIENTATION lines in the brief are drawing "
    "guidance. A direction is wrong only when it reverses the beat: the hero moves or faces away from the target the "
    "scene says they approach or face, that target is not in the picture, or a stated screen direction (left, right, "
    "up, down) is reversed. It is right when the target is visible, the hero is near it and turned at least partly "
    "toward it (a side or three-quarter view), even when the target is beside or slightly behind the hero, or the hero "
    "walks toward the camera right next to it: never set scene_mismatch, fail a direction requirement or write a "
    "correction for that. When you cannot tell, judge as the brief says."
)
BODY_VALUES = ("feet", "shins", "knees", "thighs", "waist", "chest", "face", "none")
# Two more answers: how far down the hero is visible (a deterministic signal for the wide-shot crop), and squashed
# proportions (its own flag, not bad_anatomy: see best_draw.HARD_DEFECTS).
BODY_NOTE = (
    " Also return body_shown: the lowest part of the main character that is visible inside the picture, exactly one of "
    + ", ".join(BODY_VALUES) + " (none when nobody is drawn). Also return squashed_figure: true when a person's body is "
    "squashed or shortened to fit the frame: legs clearly too short for the torso (legs are about half the height of a "
    "standing person), stubby limbs or a compressed torso, compared with the character sheet and reference photo. A "
    "figure cut by the frame edge, foreshortening, a seated, kneeling or crouching pose, a child's natural proportions "
    "and the proportions the character sheet itself shows are not squashed; false when unsure."
)

_HOLDING = r"(?:holding|gripping|clutching|grasping|carrying|held|gripped|clutched|grasped|carried)"
_HELD = re.compile(rf"\b(?:holds|grips|clutches|grasps|carries|{_HOLDING}|"
                   r"in (?:his|her|their|the|one|both|each|hero's) (?:left |right |own |two )?hands?)\b", re.I)
_HOLD_EXPECTED = re.compile(r"\b(?:h[eo]ld(?:s|ing)?|grip(?:s|ped|ping)?|clutch(?:es|ed|ing)?|grasp(?:s|ed|ing)?|"
                            r"carr(?:y|ies|ied|ying)|press(?:es|ed|ing)?|in (?:\w+ ){0,2}hands?)\b", re.I)
# The checker's own words say the object is not held, not there, another one, or with someone else.
_NOT_HELD = re.compile(
    r"\b(?:not|no|never|none|nobody|without|absent|missing|dropp?(?:s|ed|ing)?|fall(?:s|en|ing)?|fell|l(?:ies|ying|ay)|"
    r"rest(?:s|ing)?|sits|sitting|floating|ground|floor|table|desk|shelf|bench|pocket|bag|belt|another|different|"
    r"someone|somebody|companion|wrong (?:object|item|prop))\b|n't\b"
    r"|\bby\s+(?!hero\b|her\b|his\b|him\b|one\b|both\b|its\b|the (?:edges?|corners?|handle|strap|sides?|top|bottom)\b)", re.I)
# A correction about something else than the grip or the bottom crop.
_OTHER_TOPIC = re.compile(
    r"\b(?:turn\w*|fac(?:e|es|ing)|look\w*|gaz\w*|eyes?|expression|smil\w*|frown\w*|walk\w*|run\w*|remove|add|text|"
    r"letter\w*|seam|border|margins?|close-?up|medium|head (?:is |was )?(?:cut|cropped)|top of the head|"
    r"proportion\w*|short\w*|stubby|squash\w*|compress\w*|scale|shrink|smaller|larger|bigger|taller|two-thirds|half)\b", re.I)
_GRIP_FIX = re.compile(r"^\W*(?:hold|grip|press|clutch|grasp|keep|bring|raise|lower|carry)\b", re.I)
_NOW_HELD = re.compile(rf"\b(?:instead of|rather than)\s+(?:just\s+|only\s+|merely\s+)?{_HOLDING}\s+(?:it|them)\b", re.I)
_BOTTOM_CROP = re.compile(r"\b(?:feet|foot|boots?|shoes?|toes?|shins?|ankles?|knees?|head[- ]to[- ](?:feet|foot|toe)|"
                          r"(?:entire|whole|full) (?:body|figure)|full[- ](?:body|length)|ground (?:visible )?(?:below|beneath|under))\b", re.I)
_REFRAME = re.compile(r"\b(?:frame (?:as|it|the|this)|reframe|framing|wide shot|long shot|medium shot|close-?up|crop\w*|zoom\w*|"
                      r"pull (?:the camera )?back|head[- ]to[- ](?:feet|foot|toe)|(?:entire|whole|full) (?:body|figure)|"
                      r"full[- ](?:body|length)|cut off)\b", re.I)
WIDE_MARK = "WIDE SHOT:"  # framing.SHOT_FRAMING opens a wide-shot brief with it
WIDE_ENOUGH = ("feet", "shins", "knees")


def still_held(observed: object, expected: object) -> bool:
    """A contact row that asks for a hold, and the checker saw the object held: the grip, the number of hands, which
    hand and where it is held are advisory ("held in left hand at side" for "gripped tightly against the chest")."""
    seen = str(observed or "")
    return bool(_HOLD_EXPECTED.search(str(expected or "")) and _HELD.search(seen) and not _NOT_HELD.search(seen))


def _grip_only(correction: str) -> bool:
    """"Hold the map open with both hands ... instead of holding it out in one hand": it is held, only differently."""
    return bool(_GRIP_FIX.search(correction) and _NOW_HELD.search(correction)
                and not _NOT_HELD.search(correction) and not _OTHER_TOPIC.search(correction))


def _bottom_crop_only(correction: str) -> bool:
    """"Frame as a wide shot with the entire body visible from head to feet": only the feet or the ground are asked for."""
    return bool(_BOTTOM_CROP.search(correction) and not _OTHER_TOPIC.search(correction) and not _HELD.search(correction))


def advisory_staging(answer: Dict, found: Dict, context: str = "") -> bool:
    """scene_mismatch was raised only for a grip, or for a wide shot cut at the shins or knees.

    Every correction must be one of the two (a mismatch without a correction, a seam or any other correction keeps the
    verdict). The crop counts only in a wide-shot brief, with the head inside the picture (head_top above the top edge)
    and the checker's own body_shown at the knees or lower: a cropped head or a close-up still fails."""
    corrections = found.get("corrections") or []
    if found.get("scene_mismatch") is not True or found.get("seam") or not corrections:
        return False
    head = found.get("head_top")
    wide = WIDE_MARK in (context or "") and answer.get("body_shown") in WIDE_ENOUGH and head is not None and head > 0
    return all(_grip_only(c) or (wide and _bottom_crop_only(c)) for c in corrections)


def reader_view(answer: Dict, found: Dict, context: str = "", strict: bool = False) -> Dict:
    """The check's answer as a reader would rule: a scene object's own marking and marks on a held map are not text
    (never on the character sheet, strict), a grip or a knee crop is not a scene mismatch, a squashed figure is a defect."""
    if not strict and scene_marking_only(answer, found):  # the helipad's H
        found = {**found, "has_text": False, "scene_marking": True}
    elif not strict and prop_marks_only(answer, found):  # legend boxes and pseudo-lettering on the hero's map
        found = {**found, "has_text": False, "prop_marking": True}
    if advisory_staging(answer, found, context):
        found = {**found, "scene_mismatch": False, "staging_advisory": True}
    if answer.get("squashed_figure") is True:
        found = {**found, "squashed_figure": True}
    return found


def fresh_redraw(found: Optional[Dict]) -> bool:
    """The next draw starts from scratch instead of revising this one: paper margins, a squashed figure, or a wrong
    crop (a revision keeps the composition and can only squeeze the figure into it). A seam is still revised."""
    found = found or {}
    if found.get("margins_redraw") or found.get("squashed_figure"):
        return True
    corrections: Sequence[str] = found.get("corrections") or []
    return bool(found.get("scene_mismatch")) and not found.get("seam") and any(_REFRAME.search(c) for c in corrections)
