"""Image-model prompts for character sheets, story panels and covers.

None of the lettering (captions, dialogue, titles) is ever sent to the image model.
"""

from typing import Dict, Optional, Sequence, Tuple

from book_comic.scene_requirements import scene_requirements
from book_comic.comic_rules import ANATOMY_RULE, NO_TEXT_RULE, OUTFIT_LOCK, PANEL_RULES, SINGLE_IMAGE_RULE, bare_hands, cover_scene, crowd_rule, props_rule
from book_comic.framing import detail_framing, framing_block
from book_comic.lettering_space import lettering_space
from book_comic.margins import drawable_style

NO_TEXT = (
    "a single full-bleed illustration filling the whole canvas edge to edge: no text, no letters, no speech bubbles, "
    "no captions, no watermark, no sound-effect lettering, no pseudo-lettering or empty lettering containers"
)

# What each kind of reference image is, for the sentence that introduces them
REFERENCE_ROLES = {
    "photo": "the real person's recognizable facial identity, skin tone and hair, interpreted at the specified age",
    "sheet": "the approved character design: same face, hair, outfit and marks",
    "previous": "the previous panel of this page",
    "panels": "the first page's panels side by side",
    "style": "the comic's front cover, for drawing style, palette, lighting and world only",
}

PANEL_CRAFT = (
    "Use the scene's emotion: show it through the face when visible, otherwise through gesture or posture. "
    "Depict one instant with the focal subject specified by the scene: a face, gesture or important object. "
    "Do not force the face into an object or hand detail shot. Use depth, perspective, lighting and contrast "
    "appropriate to the selected medium rather than imposing realistic 3D volume on flat styles. Keep hands "
    "anatomically plausible; when eyes are visible, direct the gaze toward the action. Avoid duplicate limbs, merged objects and extra "
    "copies of a character. Do not invent scars, moles, jewelry or costume changes that are not described. "
    "No accessories beyond the approved appearance (gloves, jewellery, necklaces, pendants, watches, hats, bags) "
    "unless the scene introduces them. "
    "When the scene names an action that changes an object's state (closes, opens, lifts, folds, unfolds, lights, "
    "switches on or off), draw the instant just after it completes: the object is already in its new state. "
    "A prop or garment the scene calls hidden, tucked away, pocketed, stowed, packed, under clothing or out of "
    "sight is not drawn at all: never in a hand or in view. A prop held, carried or tucked under an arm is "
    "visible: draw it exactly there. "
    f"{OUTFIT_LOCK}{ANATOMY_RULE}"
)


def _props_text(cast: Dict, scene: str) -> str:
    """The props this scene shows: a Power Gauntlet prop waives bare hands only where the scene names it."""
    return " ".join(f"{p.get('name', '')} {p.get('look', '')}" for p in cast.get("props") or []
                    if p.get("name") and p["name"].lower() in scene.lower())


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
        "The earlier pictures of this story establish the environment and latest prop state unless the current scene explicitly changes them; "
        "they do not control camera framing. "
        "The current scene controls pose, expression, shot distance and camera angle; do not copy a prior composition. "
        "Keep recurring companions and objects recognizable by their fixed geometry and construction. "
    )


SPLASH = (
    "Full-page splash illustration: this one image fills the entire tall portrait canvas as one picture. "
    "Give it a wide, establishing, dramatic composition with depth, scale and a strong focal point; "
    "when the scene names a closer shot, keep that shot and stage it dramatically. "
    "Let the scene's own sky, ceiling, ground or water fill the top or bottom fifth of the canvas as open, low-detail "
    "scenery, free of faces, important hands and focal props.\n"
)


def canvas_shape(size: Optional[Tuple[int, int]]) -> str:
    """The frame's shape, so a full-body figure in a wide strip is not drawn as an upright picture centred on blank
    paper (e35347af panel 1: three draws, each a portrait print in the middle of a 2:1 panel)."""
    if not size or not size[1]:
        return ""
    ratio = size[0] / size[1]
    if ratio >= 1.25:
        return (f"Canvas: a landscape frame about {ratio:.1f} times as wide as it is tall. Compose horizontally: the "
                "setting spreads across the full width to both side edges, with the whole figure standing inside it "
                "(smaller if needed to fit head to feet); never a narrower upright picture in the middle.\n")
    if ratio <= 0.8:
        return (f"Canvas: a portrait frame about {1 / ratio:.1f} times as tall as it is wide. The setting fills the "
                "full height and width to every edge.\n")
    return ""


def panel_prompt(cast: Dict, panel: Dict, people: str, roles: Sequence[str] = (), splash: bool = False,
                 size: Optional[Tuple[int, int]] = None) -> str:
    """Prompt for one story panel, or with splash=True for a full-page splash panel.

    Args:
        cast: Character sheet (style, characters, optional props)
        panel: The panel's script (scene, characters)
        people: "name: look; ..." for the characters visible in the panel
        roles: Kinds of the attached reference images, in order (see REFERENCE_ROLES)
    """
    requirements = scene_requirements(panel['scene'], panel.get('requirements', []))
    crop = framing_block(cast, panel, requirements)
    limb = detail_framing(requirements)
    if limb:
        # A limb-only crop hides the outfit, and the model then invents one for the hand (gloves, straps, another
        # sleeve: e35347af panel 3). Carry the character's look into the crop.
        worn = "sleeve, cuff and hand" if limb == "hand_detail_only" else "trouser legs, socks and footwear"
        people = (f"Only the specified limb is visible. It belongs to this character ({people or 'Hero'}): draw exactly that "
                  f"outfit's {worn} as on the character sheet, same colour and material. Bare skin unless that "
                  "description includes gloves; no gloves, straps, wraps, bracelets, rings or a different sleeve. "
                  "Preserve its skin tone and age from the references; do not draw the whole character.")
    calm_area = SPLASH if splash else lettering_space(panel, requirements)
    kind = "One full-page, full-bleed comic illustration" if splash else "One full-bleed comic illustration"
    previous = ""
    if "previous" in roles:
        previous = (
            "Keep established environment details unless the current scene explicitly changes location, time or lighting. "
            "Keep prop construction fixed while allowing the approved pose or state to change. "
            "Preserve world continuity while changing the pose and framing to match this scene. "
        )
    return (
        f"{crop}{canvas_shape(size)}{calm_area}{kind}. Art style: {drawable_style(cast.get('style')) or 'detailed comic book art'}.\n"
        f"Scene: {panel['scene']}\n"
        f"Characters (draw exactly as described): {people or 'none'}\n"
        f"{bare_hands(people, panel['scene'], _props_text(cast, panel['scene']))}"
        f"{crowd_rule(panel['scene'])}{describe_references(roles)}{previous}{PANEL_CRAFT}{PANEL_RULES}{props_rule(cast)}"
        f"{acceptance_prompt(requirements, cast.get('prop_anchors'))}"
        "Keep the requested shot distance and all focal action visible. "
        f"Use real scenery, never an empty rectangle. {SINGLE_IMAGE_RULE}\n"
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
        f"{bare_hands(character.get('look', ''))}"
        f"Style: {drawable_style(cast.get('style')) or 'detailed comic book art'}. {ANATOMY_RULE}{NO_TEXT_RULE}"
    )


def cover_requirements(scene: str, requirements=()):
    """The cover's checked states without camera framing: the cover prompt sets its own (comic_rules.cover_scene)."""
    return [r for r in scene_requirements(scene, requirements) if r.get('attribute') != 'framing']


def cover_prompt(cast: Dict, cover: Dict, roles: Sequence[str] = ()) -> str:
    """Prompt for a portrait cover. Never "title" or "text" in the composition lines: naming them makes
    the model paint lettering, and asking for an empty top made it stack a second strip with a seam."""
    hero = (cast.get("characters") or [{}])[0]
    # The cover owns its framing: the scene's planned shot and any limb-only clause go (comic_rules.cover_scene).
    scene = cover_scene(cover.get("scene", ""))
    strip = ""
    if "panels" in roles:
        strip = (
            "Show only the props and companions requested by the cover scene; use the first page's panels as design "
            "references for those elements and the outfit. Do not import every object or copy a panel composition. "
            "The cover stays one single scene. "
        )
    return (
        f"Full-page portrait comic illustration. Art style: {drawable_style(cast.get('style')) or 'detailed comic book art'}. "
        f"Scene: {scene} Main character: {hero.get('name_en', '')}: {hero.get('look', '')} "
        f"{bare_hands(hero.get('look', ''), scene, _props_text(cast, scene))}"
        f"{describe_references(roles)}{strip}"
        "Show the emotion clearly in the eyes and mouth. Build a clear focal hierarchy around the main character's "
        "face, gesture and the story's meaningful prop or clue. Make the silhouette readable at thumbnail size, with "
        "depth, perspective and light appropriate to the selected medium. Suggest the central tension without revealing the "
        "resolution. One single continuous scene fills the whole canvas edge to edge, with no bands, strips, panels, "
        "borders, frames or dividing lines. Show the main character from the knees up or full length, positioned lower "
        "in the frame without forcing a standing pose: follow the scene's action. Aim for the head about one third "
        "of the way down the canvas when that pose permits, with more of the setting "
        "(its sky, ceiling or upper wall) above it, and let the bottom edge fade slightly darker. "
        f"{acceptance_prompt(cover_requirements(scene, cover.get('requirements', [])), cast.get('prop_anchors'))}{props_rule(cast)}{ANATOMY_RULE}{NO_TEXT_RULE}"
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
        if r['attribute'] == 'state' and r['expected'].strip().lower() in ('closed', 'shut'):
            facts.append(f"{r['subject']} is fully shut, not half-open; no interior spread is exposed")
        if r['attribute'] == 'state' and r['expected'].strip().lower() in ('folded', 'folded up', 'folded closed'):
            # "Hero folds the city map": the model drew it spread open on 3 of 3 draws (3cef9bb5 p17 panel 3).
            facts.append(f"{r['subject']} is already folded into a small compact rectangle held in the hand; it is not "
                         "spread, unfolded or partly open, and none of its inside is showing")
    for name, appearance in (anchors or {}).items():
        facts.append(f"{name} has this established construction: {appearance}")
    return (" Required visible facts: " + "; ".join(facts) + ". ") if facts else ""


def back_cover_prompt(cast: Dict, back: Dict, size: Optional[Tuple[int, int]] = None, roles: Sequence[str] = ()) -> str:
    """Prompt for the back cover art: the story's setting with nobody in it. Never "text", "box" or "blurb" in the
    composition: naming them makes the model paint lettering or an empty placeholder (NO_TEXT_RULE)."""
    style_ref = ""
    if "style" in roles:
        style_ref = ("The attached front cover sets the drawing style, palette, line work and lighting; show a different "
                     "view of the same world and never copy its figure, pose or composition. ")
    return (
        f"Full-page portrait comic illustration. Art style: {drawable_style(cast.get('style')) or 'detailed comic book art'}. "
        f"Setting: {back.get('scene', '')} {canvas_shape(size)}{style_ref}"
        "An atmospheric establishing view of this place with nobody in it: no people, characters, faces, silhouettes, "
        "figures in windows or distant passers-by, and no animals with faces. Every street, sidewalk, square, window, balcony, "
        "rooftop and vehicle is empty; a city far away shows only lit windows and outlines. Tell the story's mood through light, weather, "
        "objects and architecture. Keep the upper half calm and low in detail (open sky, mist, deep shadow, a plain wall "
        "or ceiling) and gather the setting's detail in the lower third and along the side edges. "
        "One single continuous scene fills the whole canvas edge to edge, with no bands, strips, panels, borders or frames. "
        f"{SINGLE_IMAGE_RULE} {NO_TEXT_RULE}"
    )
