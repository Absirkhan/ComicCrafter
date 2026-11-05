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
from typing import Dict, Optional, Sequence

from PIL import Image

from book_comic.lettering_space import useful_corrections

REVISE_MARK = "REVISE the last attached image"
REFERENCE_PX = 1536  # the editing model needs the picture, not print resolution: a JPEG this size, not a multi-MB PNG
# What to ask for, per failed check, said positively (describe the wanted result, not the defect).
_FIXES = {
    "has_text": "every surface becomes plain: no letters, words, numbers or glyphs anywhere, no bubbles or caption boxes",
    "bad_anatomy": "each person has exactly two arms and two hands with five fingers, every limb attached to its own body",
    "gloves": "both hands are bare skin, without gloves, wraps or straps",
    "seam": "one continuous picture: the dividing line is gone and the scene runs unbroken across it",
    "identity_mismatch": "the face, age, hair and proportions match the reference photo and character sheet",
    "design_mismatch": "the outfit and prop construction match the character sheet exactly",
}
_CHARACTER_FIXES = ("identity_mismatch", "design_mismatch")


def data_url(image: Image.Image) -> str:
    """A JPEG data URL of the draw at reference size, as the image client takes references."""
    small = image.convert("RGB").copy()
    small.thumbnail((REFERENCE_PX, REFERENCE_PX))
    buffer = BytesIO()
    small.save(buffer, format="JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def failed_requirements(found: Dict, requirements: Sequence[Dict] = ()) -> list:
    """The requirement rows the check saw unmet, without framing rows (observed only, never enforced)."""
    out = []
    for i, c in enumerate(c for c in found.get("requirement_checks") or [] if isinstance(c, dict)):
        index = c.get("index") if type(c.get("index")) is int else i  # the model's own index when the list is raw
        requirement = requirements[index] if 0 <= index < len(requirements) else None
        if requirement is None or c.get("matches") is True or c.get("soft") or requirement.get("attribute") == "framing":
            continue
        out.append({"required": requirement, "observed": str(c.get("observed", ""))[:120]})
    return out


def _wrong_props(found: Dict, anchors: Optional[Dict]) -> list:
    return [{"prop": c.get("name"), "observed": str(c.get("observed", ""))[:120], "canonical": (anchors or {}).get(c.get("name"))}
            for c in found.get("prop_checks") or [] if isinstance(c, dict) and c.get("visible") and c.get("matches") is not True][:4]


def revision_prompt(brief: str, found: Dict, extra: Sequence[str] = (), requirements: Sequence[Dict] = (), anchors: Optional[Dict] = None) -> str:
    """The edit instruction for draw 2: keep the rejected draw, change only what the check found.

    brief: the original generation prompt (its rules still apply; the scene is already staged)
    found: the check's answer for the rejected draw
    extra: further short requests (the framing block), already positive
    requirements / anchors: the brief's required states and canonical prop designs, for the evidence of what was wrong
    """
    wanted = [text for key, text in _FIXES.items() if found.get(key)]
    failed, props = failed_requirements(found, requirements)[:6], _wrong_props(found, anchors)
    if failed or props or found.get("prop_shape_mismatch"):
        wanted.append("the required states and prop designs are exactly as listed: " + json.dumps({"states": failed, "props": props}, ensure_ascii=False))
    wanted += [w for w in extra if w]
    corrections = useful_corrections(found.get("corrections"))
    if corrections:
        wanted.append("apply these reviewer corrections: " + "; ".join(corrections))
    if not wanted:
        wanted.append("the picture matches the brief's planned shot, action and expression")
    # Keep only what was not the defect: a wrong shot, action or facing means the staging is redone; a wrong face or
    # outfit means the character is redrawn to the references; a seam alone keeps everything.
    character = any(found.get(k) for k in _CHARACTER_FIXES)
    staging = bool(found.get("requirement_mismatch")) or bool(found.get("scene_mismatch") and not found.get("seam"))
    kept = ["setting", "colours", "art style"] + ([] if staging else ["composition", "camera"]) + ([] if character else ["character"])
    redo = (["re-stage the shot, action and facing exactly as the brief plans them"] if staging else []) + (
        ["redraw the character's face, hair, proportions and outfit as the references show"] if character else [])
    keep = ", ".join(kept) + " exactly as they are" + (", and " + "; ".join(redo) if redo else "")
    return (
        f"{REVISE_MARK}, which is your previous attempt at this picture. Keep its {keep}. "
        "Change only the following, and do not change any other element of the image: " + "; ".join(wanted) + ". "
        "The original brief follows for its rules only; the scene is already staged in the attached attempt. " + brief
    )
