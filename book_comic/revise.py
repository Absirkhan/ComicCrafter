"""The second draw revises the rejected first draw instead of re-rolling it.

Google's guidance for this image model family is that multi-turn editing is the recommended way to iterate on an
image, with edit instructions of the form "change X; do not change any other elements of the image", and the
detect-then-correct loops in the literature converge in two or three localized edits where regeneration keeps
rolling new dice. Production 2026-11-05: 16 of 31 rejected panels burned all three re-rolls, most of them over one
defect in an otherwise good draw (gloves, a dividing line, a facing direction). So: draw 1 draws; draw 2 is sent the
rejected draw as its last reference with only the corrections to make; draw 3 re-rolls from scratch when the
revision did not fix it (a fresh base instead of editing a bad one).
"""
import base64
import json
from io import BytesIO
from typing import Dict, Sequence

from PIL import Image

from book_comic.lettering_space import useful_corrections

REVISE_MARK = "REVISE the last attached image"
# What to ask for, per failed check, said positively (describe the wanted result, not the defect).
_FIXES = {
    "has_text": "every surface becomes plain: no letters, words, numbers or glyphs anywhere, no bubbles or caption boxes",
    "bad_anatomy": "each person has exactly two arms and two hands with five fingers, every limb attached to its own body",
    "gloves": "both hands are bare skin, without gloves, wraps or straps",
    "seam": "one continuous picture: the dividing line is gone and the scene runs unbroken across it",
    "identity_mismatch": "the face, age, hair and proportions match the reference photo and character sheet",
    "design_mismatch": "the outfit and prop construction match the character sheet exactly",
    "figure_visible": "nobody is in the picture: the setting alone, every person removed",
}


def data_url(image: Image.Image) -> str:
    """A PNG data URL of the draw, as the image client takes references."""
    buffer = BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def revision_prompt(brief: str, found: Dict, extra: Sequence[str] = ()) -> str:
    """The edit instruction for draw 2: keep the rejected draw, change only what the check found.

    brief: the original generation prompt (its rules still apply; the scene is already staged)
    found: the check's answer for the rejected draw
    extra: further short requests (the framing block, a required state), already positive
    """
    wanted = [text for key, text in _FIXES.items() if found.get(key)]
    failed = [c for c in found.get("requirement_checks") or [] if isinstance(c, dict) and c.get("matches") is not True]
    if failed or found.get("prop_mismatch") or found.get("prop_shape_mismatch"):
        wanted.append("the required states and prop designs are exactly as the brief lists them: " + json.dumps(failed)[:400])
    wanted += [w for w in extra if w]
    corrections = useful_corrections(found.get("corrections"))
    if corrections:
        wanted.append("apply these reviewer corrections: " + "; ".join(corrections))
    if not wanted:
        wanted.append("the picture matches the brief's planned shot, action and expression")
    return (
        f"{REVISE_MARK}, which is your previous attempt at this picture. Keep its composition, camera, character, "
        "setting, colours and art style exactly as they are. Change only the following, and do not change any other "
        "element of the image: " + "; ".join(wanted) + ". "
        "The original brief follows for its rules only; the scene is already staged in the attached attempt. " + brief
    )
