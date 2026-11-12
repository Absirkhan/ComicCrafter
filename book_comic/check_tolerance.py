"""What the art check lets through because a reader would not call it a defect.

Three production rejections (2026-11-12) were the check being stricter than a reader:
- the "H" of a helipad on a hospital roof, seen from far away, failed has_text (BOOKS-44 page 18);
- a door's "closed" state in an extreme long shot was "not visible" on three draws in a row and failed
  requirement_mismatch, so a least-bad draw went to print (BOOKS-44 page 1);
- a notebook "held in hands away from chest" instead of pressed flat against it failed a close-up (BOOKS-45 page 1).

Unchanged on purpose: readable words, labels, signs, logos with letters, watermarks, bubbles, captions and invented
glyph or rune writing still fail has_text; a state that is visibly wrong still fails; anatomy, identity, character
design, facing or gaze direction, margins and seams are judged as before. The image prompts still ask for a
wordless picture (comic_rules.NO_TEXT_RULE): this only stops a redraw over a marking the scene's own object carries.
"""

import re
from typing import Dict

# has_text: one conventional marking that is part of an object in the scene. Clock, watch, compass and gauge numerals
# are already not text (art_check.inspect_art, the dial sentence).
SCENE_MARKING_NOTE = (
    " Also return text_marking: true only when has_text is true and everything you counted as writing is ONE "
    "conventional marking that is part of an object or surface of the scene, as the real thing carries it: the H of a "
    "helipad, the plus or cross of a first-aid box, an arrow, road or parking markings. It is a single letter or symbol, "
    "never a word. Return text_marking false for a readable word or several letters together, a label, sign or door "
    "plate with writing, a speech bubble or caption, a logo with letters, a watermark or signature, invented glyph or "
    "rune writing, and whenever any other writing is in the picture; false when has_text is false."
)
# requirement rows: a state the checker cannot see is not a wrong state.
HIDDEN_NOTE = (
    " Mark not_visible for a requirement you cannot judge because its subject is occluded, cropped out, too small or "
    "too far away at this camera distance, rather than inventing evidence; not_visible is never a failure. When the "
    "subject is clearly drawn and its pose or state is visibly different, report what you see with matches false."
)
# requirement rows and scene_mismatch: the action, the object, who does it and the facing are what a reader follows.
CONTACT_NOTE = (
    " For a contact requirement, matches is false when the contact is absent, or the object or the person is a "
    "different one; the same object held or touched by the same person matches even when the grip, the hand placement "
    "or its exact position differs slightly (a notebook held just in front of the chest instead of pressed flat against it)."
)
HOLD_NOTE = (
    " Judge the focal action as a reader would: it is wrong when the action itself, the object, who does it, or the "
    "facing or gaze direction differs from the brief; a correctly held or used object whose grip, hand placement or "
    "exact position differs slightly is not a scene_mismatch."
)

# The checker's own description contradicts "one marking": a word, a sign, glyph writing, or a quoted string of two
# or more characters ("GENERATOR ROOM"). Then the flag is not trusted and the draw stays rejected.
_WRITING = re.compile(
    r"\b(?:words?|letters|text|writing|lettering|labels?|sign(?:s|age|board)?|plate|captions?|bubbles?|logo|watermark|"
    r"signature|glyphs?|runes?|runic|script|inscription|numbers|digits)\b|['\"“‘][^'\"”’]{2,}['\"”’]", re.I)


def hidden(observed: object) -> bool:
    """The checker could not see the requirement's subject or state ("not_visible", also written "not visible")."""
    return str(observed or "").strip().lower().replace(" ", "_") == "not_visible"


def scene_marking_only(answer: Dict, found: Dict) -> bool:
    """has_text was raised only for one conventional marking on a scene object (the helipad's H), by the checker's own
    text_marking flag, and its text_seen description does not name words, a sign or glyph writing."""
    return (found.get("has_text") is True and answer.get("text_marking") is True
            and not _WRITING.search(found.get("text_seen") or ""))
