"""Image-model prompts for character sheets, story panels and covers.

None of the lettering (captions, dialogue, titles) is ever sent to the image model.
"""

from typing import Dict, Sequence

from book_comic.scene_requirements import scene_requirements
from book_comic.comic_rules import ANATOMY_RULE, NO_TEXT_RULE, PANEL_RULES, props_rule

NO_TEXT = (
    "a single full-bleed illustration filling the whole canvas edge to edge: no border, no frame, "
    "no panel lines, no empty lettering containers or placeholder rectangles, no text, no letters, no speech bubbles, "
    "no captions, no watermark, no sound-effect lettering, no pseudo-lettering or empty lettering containers"
)

# What each kind of reference image is, for the sentence that introduces them
REFERENCE_ROLES = {
    "photo": "the real person's recognizable facial identity, skin tone and hair, interpreted at the specified age",
    "sheet": "the approved character design: same face, hair, outfit and marks",
    "previous": "the previous panel of this page",
    "panels": "the first page's panels side by side",
}

PANEL_CRAFT = (
    "Use the scene's emotion: show it through the face when visible, otherwise through gesture or posture. "
    "Depict one instant with the focal subject specified by the scene: a face, gesture or important object. "
    "Do not force the face into an object or hand detail shot. Use depth, perspective, lighting and contrast "
    "appropriate to the selected medium rather than imposing realistic 3D volume on flat styles. Keep hands "
    "anatomically plausible; when eyes are visible, direct the gaze toward the action. Avoid duplicate limbs, merged objects and extra "
    "copies of a character. Do not invent scars, moles, jewelry or costume changes that are not described. "
    f"{ANATOMY_RULE}"
)


def describe_references(roles: Sequence[str]) -> str:
    """One sentence naming each attached reference image in order ("" when there are none)."""
    if not roles:
        return ""
    named = "; ".join(f"reference image {i} is {REFERENCE_ROLES[role]}" for i, role in enumerate(roles, 1))
    return (
        f"Attached references: {named}. "
        "Reference priority: the photo establishes likeness; the character sheet fixes the illustrated face, "
        "age cues, head-to-body proportions, hair, facial hair and exact garment construction. "
        "The specified age group controls depicted age; explicit appearance details override photo hair or accessories. "
        "Use the photo for unspecified details and retain recognizable facial identity within that age group. "
        "Previous panels establish the environment and latest prop state unless the current scene explicitly changes them; "
        "they do not control camera framing. "
        "The current scene controls pose, expression, shot distance and camera angle; do not copy a prior composition. "
        "Keep recurring companions and objects recognizable by their fixed geometry and construction. "
    )


def panel_prompt(cast: Dict, panel: Dict, people: str, roles: Sequence[str] = ()) -> str:
    """Prompt for one story panel.

    Args:
        cast: Character sheet (style, characters, optional props)
        panel: The panel's script (scene, characters)
        people: "name: look; ..." for the characters visible in the panel
        roles: Kinds of the attached reference images, in order (see REFERENCE_ROLES)
    """
    requirements = scene_requirements(panel['scene'], panel.get('requirements', []))
    framing = next((r['expected'] for r in requirements if r['attribute'] == 'framing'), None)
    crop = ""
    if framing in ('hand_detail_only', 'feet_detail_only'):
        crop = ("LIMB-ONLY MACRO DETAIL. " + ("Crop at the wrist or short sleeve cuff; show only the specified hand, cuff and focal objects. " if framing == 'hand_detail_only' else "Crop at the lower legs; show only the specified feet and focal objects. ")
                + "Head, neck, shoulders, torso, waist and all other limbs remain outside the frame. This crop overrides the full-body reference composition.\n")
        people = "Only the specified limb is visible. Preserve its skin, age and relevant clothing details from references; do not draw the whole character."
    previous = ""
    if "previous" in roles:
        previous = (
            "Keep established environment details unless the current scene explicitly changes location, time or lighting. "
            "Keep prop construction fixed while allowing the approved pose or state to change. "
            "Preserve world continuity while changing the pose and framing to match this scene. "
        )
    return (
        f"{crop}Comic book panel. Art style: {cast.get('style', 'detailed comic book art')}.\n"
        f"Scene: {panel['scene']}\n"
        f"Characters (draw exactly as described): {people or 'none'}\n"
        f"{describe_references(roles)}{previous}{PANEL_CRAFT}{PANEL_RULES}{props_rule(cast)}"
        f"{acceptance_prompt(requirements, cast.get('prop_anchors'))}"
        "Leave some natural background around the focal action for readable lettering. "
        "Keep the requested shot distance and all focal action visible. "
        "Use real scenery, never an empty rectangle.\n"
        f"Strictly {NO_TEXT}. {NO_TEXT_RULE}"
    )


def sheet_prompt(cast: Dict, character: Dict, roles: Sequence[str] = ()) -> str:
    """Prompt for a full-body character reference sheet, drawn before any panel."""
    return (
        "Draw one full-body comic character in a relaxed three-quarter pose on a plain background, no text. "
        f"{describe_references(roles)}"
        "Make a usable production character reference: the entire silhouette and footwear are visible, hands are "
        "separate from the torso, and clothing layers and accessories are easy to identify. Use the selected style's "
        "proportions, including intentional exaggeration, while retaining the specified age cues and likeness. "
        "Use one coherent illustrated medium, clean facial detail and a few crisp clothing and "
        f"hair details. Character: {character.get('name_en', '')}: {character.get('look', '')}. "
        f"Style: {cast.get('style', 'detailed comic book art')}. {ANATOMY_RULE}{NO_TEXT_RULE}"
    )


def cover_prompt(cast: Dict, cover: Dict, roles: Sequence[str] = ()) -> str:
    """Prompt for a portrait cover. Never "title" or "text" in the composition lines: naming them makes
    the model paint lettering, and asking for an empty top made it stack a second strip with a seam."""
    hero = (cast.get("characters") or [{}])[0]
    strip = ""
    if "panels" in roles:
        strip = (
            "Show only the props and companions requested by the cover scene; use the first page's panels as design "
            "references for those elements and the outfit. Do not import every object or copy a panel composition. "
            "The cover stays one single scene. "
        )
    return (
        f"Full-page portrait comic illustration. Art style: {cast.get('style', 'detailed comic book art')}. "
        f"Scene: {cover.get('scene', '')} Main character: {hero.get('name_en', '')}: {hero.get('look', '')} "
        f"{describe_references(roles)}{strip}"
        "Show the emotion clearly in the eyes and mouth. Build a clear focal hierarchy around the main character's "
        "face, gesture and the story's meaningful prop or clue. Make the silhouette readable at thumbnail size, with "
        "depth, perspective and light appropriate to the selected medium. Suggest the central tension without revealing the "
        "resolution. One single continuous scene fills the whole canvas edge to edge, with no bands, strips, panels, "
        "borders, frames or dividing lines. Show the main character from the knees up or full length, positioned lower "
        "in the frame without forcing a standing pose: follow the scene's action. Aim for the head about one third "
        "of the way down the canvas when that pose permits, with more of the setting "
        "(its sky, ceiling or upper wall) above it, and let the bottom edge fade slightly darker. "
        f"{acceptance_prompt(scene_requirements(cover.get('scene', ''), cover.get('requirements', [])), cast.get('prop_anchors'))}{props_rule(cast)}{ANATOMY_RULE}{NO_TEXT_RULE}"
    )


def acceptance_prompt(requirements=(), anchors=None):
    """Visible acceptance facts, shared by drawing and checking; never drawn as writing."""
    facts = [f"{r['subject']} — {r['attribute']}: {r['expected']}" for r in requirements]
    for r in requirements:
        if r['attribute'] == 'hand':
            facts.append(f"Use Hero's anatomical {r['expected']} hand, not the opposite hand. Make the thumb and knuckles legible; screen position alone does not determine handedness")
        if r['attribute'] == 'framing' and r['expected'] == 'hand_detail_only':
            facts.append("Extreme detail crop at the wrist or short sleeve cuff: only the specified hand, cuff and focal objects. The frame cuts off the arm before the elbow. Exclude head, neck, shoulders, torso, waist, legs and the opposite hand")
        if r['attribute'] == 'framing' and r['expected'] == 'feet_detail_only':
            facts.append("Detail crop of the specified feet/lower legs and focal objects only; exclude head, torso, waist and hands")
        if r['attribute'] == 'state' and r['expected'].strip().lower() == 'flat':
            facts.append(f"{r['subject']} lies flush against the supporting surface, including its centre and stem; no tall upright centre")
        if r['attribute'] == 'state' and r['expected'].strip().lower() == 'closed':
            facts.append(f"{r['subject']} is fully shut, not half-open; no interior spread is exposed")
    for name, appearance in (anchors or {}).items():
        facts.append(f"{name} has this established construction: {appearance}")
    return (" Required visible facts: " + "; ".join(facts) + ". ") if facts else ""
