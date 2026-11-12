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

A live 20-page comic (2026-11-12) added three more, on a city map the hero holds: "pseudo-lettering in legend boxes",
"pseudo-lettering lines on map" and "contains pseudo-lettering 'PPI2' in a yellow zone" failed good pictures. Marks on
a map, page, book, document or screen the hero holds or uses are how such a prop is drawn, unless they form a legible
real word. Grip, wide-shot crop and direction of movement are in book_comic.staging_tolerance.
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
    "or its exact position differs slightly (a notebook held just in front of the chest instead of pressed flat against it). "
    "How it is held is advisory: the grip, one hand or two, which hand, and where it is held (against the chest or held "
    "out, at the side or raised) all match. An object that is absent, dropped or put down when it should be held, or "
    "held by someone else, does not match."
)
HOLD_NOTE = (
    " Judge the focal action as a reader would: it is wrong when the action itself, the object, who does it, or the "
    "facing or gaze direction differs from the brief; a correctly held or used object whose grip, hand placement or "
    "exact position differs slightly is not a scene_mismatch. The grip, one hand or two, which hand, and where the "
    "object is held (against the chest or held out, at the side or raised) are advisory: never a scene_mismatch and "
    "never a correction while the same person holds or uses the same object. An object that is absent, dropped or put "
    "down when the scene says it is held, or held by someone else, is still wrong."
)
# has_text: marks on a prop the hero holds or uses. A second flag, so the scene-marking rule above stays as strict as it was.
PROP_MARKS_NOTE = (
    " Also return text_on_prop: true only when has_text is true and everything you counted as writing is small marks on "
    "a map, chart, page, book, document or screen that the hero holds or uses: legend boxes, pseudo-lettering lines, "
    "tiny glyph-like marks or a few stray letter-like shapes that form no real word. A drawn map or page looks like "
    "that; such marks are never text_prominent. Return text_on_prop false when any of it is a legible real word of "
    "three or more letters in any script, and whenever any writing is on a wall, poster, sign, shopfront, graffiti, "
    "bubble or caption, or anywhere else off that prop; false when has_text is false."
)
# requirement and prop rows: the same marks are not a changed prop.
MARKS_ROW_NOTE = (
    " Tiny marks, legend boxes, pseudo-lettering lines or stray letter-like shapes on a map, chart, page, book, document "
    "or screen the hero holds or uses are never a reason for matches false on a requirement or a prop, unless they form "
    "a legible real word of three or more letters; a map without its colour fields and lines is still a different design."
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


# Marks on a held prop. The checker's description contradicts "only marks on the hero's prop" when it names another
# surface, real writing, or quotes a clean word of three or more letters ('EXIT'; 'PPI2' is not one).
_OFF_PROP = re.compile(
    r"\b(?:walls?|posters?|murals?|graffiti|billboards?|plaques?|sign(?:s|age|board|post)?|shop\w*|store\w*|doors?|plate|"
    r"banners?|bubbles?|captions?|logo|watermark|signature|runes?|runic|inscription|carved|title|headline|words?|"
    r"readable|legible|reads|spell(?:s|ing)?|says)\b", re.I)
_QUOTED = re.compile(r"['\"“‘]([^'\"”’]{2,})['\"”’]")
_HELD_SURFACE = re.compile(r"\b(?:maps?|charts?|diagrams?|pages?|books?|notebooks?|documents?|screens?|tablets?|legends?)\b", re.I)
_MARKS_FIRST = re.compile(r"^\W*(?:(?:contains|shows|has|with|there (?:is|are)|tiny|small|faint|some|a few|illegible)\s+)*"
                          r"(?:pseudo[- ]?(?:lettering|letters|text|writing|script)|letter-like|glyph-like|scribbles?|squiggles?)\b", re.I)
_CHANGED = re.compile(r"\b(?:without|missing|lacks?|lacking|instead|rather|different|wrong|not|no|but|blank|plain|empty|"
                      r"sheet|paper|white|cream)\b", re.I)


def _real_word(text: str) -> bool:
    return any(len(token) >= 3 and token.isalpha() for quoted in _QUOTED.findall(text) for token in quoted.split())


def prop_marks_only(answer: Dict, found: Dict) -> bool:
    """has_text was raised only for marks on a map, page or screen the hero holds or uses, by the checker's own
    text_on_prop flag, and its text_seen description names no wall, sign or poster and quotes no real word."""
    seen = found.get("text_seen") or ""
    return (found.get("has_text") is True and answer.get("text_on_prop") is True
            and not _OFF_PROP.search(seen) and not _real_word(seen))


def marks_only_row(observed: object, subject: object = "") -> bool:
    """A design or prop row whose whole observation is such marks on a held prop ("pseudo-lettering lines on map"):
    not a changed prop. An observation that names any other difference (a plain cream sheet) keeps the verdict."""
    text = str(observed or "")
    return bool(_MARKS_FIRST.search(text) and _HELD_SURFACE.search(f"{subject or ''} {text}")
                and not _OFF_PROP.search(text) and not _CHANGED.search(text) and not _real_word(text))
