"""Comic craft rules shared by the script writer and the image prompts.

Rules that can be measured are checked in code: shot variety by the writer (shots_problem), text
painted into the art by art_check.inspect_art, reading order and gutters by the lettering and layout.
The rest (180-degree rule, action lines, contrast, colour mood) are prompt rules.
"""

import re

from typing import Dict, List, Optional, Sequence

COMIC_SHOTS = ("Extreme long shot", "Wide shot", "Medium shot", "Close-up")
ESTABLISHING_SHOTS = ("Extreme long shot", "Wide shot")

# Writer rules, quoted in the chapter prompt
COMIC_SHOT_RULE = (
    "Camera: vary the distance and angle instead of drawing every panel from the same height and distance. "
    f"Use {', '.join(repr(s) for s in COMIC_SHOTS)}: an extreme long or wide shot to establish the place and mood, "
    "a medium shot for action and interaction, a close-up for strong emotion, a facial expression or a small "
    "important detail. Every page uses at least two different shots."
)
COMIC_BUBBLE_RULE = (
    'Bubble type: give every dialogue line exactly one "bubble": "speech" for words said out loud in a normal '
    'voice (the default); "thought" for inner thoughts or feelings nobody around hears; "shout" for shouting, '
    'alarm, bursting anger or a sudden loud noise; "whisper" for speaking quietly, telling a secret, or a weak, '
    'exhausted voice; "broadcast" for a voice from a device (phone, radio, TV, speaker) or a robot; "fear" for '
    'paralysing fear, deep shock or a cold, menacing tone; "song" for singing or humming. Most lines are '
    '"speech"; use the others only when the line calls for them.'
)

# Image rule for every drawing of a person (panels, sheets, covers): the genre never changes a human body
ANATOMY_RULE = (
    "Human anatomy: every person is an ordinary human, whatever the genre: exactly two arms and two hands, each "
    "hand with five fingers on its own arm, two legs, one head. Count each person's hands before finishing; never "
    "add a third arm or hand, even when they hold or operate several things at once. Gadgets, armour or tools are "
    "worn on or held by a normal limb and never replace or add one. "
    "This describes the whole person, not what must be visible: respect the requested crop and never add "
    "occluded hands, limbs or a head just to show the complete body. "
)

# Image rules for every story panel. Never mention "title" or "caption text" here: naming lettering
# makes the image model paint its own.
PANEL_RULES = (
    "Comic craft rules. "
    "Camera: draw exactly the shot named at the start of the scene (extreme long, wide, medium or close-up). "
    "180-degree rule: within a continuous action in the same location, keep the camera on the same side of the action and keep "
    "direction of travel, unless the scene specifies a turn or a new location. "
    "Action lines: use motion cues appropriate to the selected medium along the stated direction of movement. "
    "In ink comics these may be action lines; do not impose drawn streaks on clay or paper-cutout art. "
    "No motion cues for still moments. "
    "Contrast and focus: use the selected medium to make the main action and foreground distinct from the background. "
    "The selected art style controls rendering: do not add ink outlines, hatching or flat shading to a clay, "
    "paper-cutout or painterly style. "
    "Colour mood: use lighting and value relationships within the selected style's palette. A monochrome style "
    "stays monochrome; do not add colours just to signal an emotion. "
    "Consistency: each character's hairstyle, outfit and accessories are identical in every panel, recognisable from "
    "any angle or distance. Keep costume construction fixed; an established handheld accessory may be held, "
    "worn or put down when the approved scene explicitly changes its position. "
)
NO_TEXT_RULE = (
    "Wordless picture: every surface that could carry writing is plain. Walls, posters, murals, graffiti, billboards "
    "and plaques are plain paint, texture or simple pictures. Neon signs, shop signs, screens and holograms are abstract "
    "glowing shapes, stripes, arrows or simple icons; instrument faces use geometric ticks and pointers only; maps, pages, "
    "labels and documents show plain colour fields and lines. Speech and captions are added later by the letterer, so the "
    "picture carries no lettering of its own. Absolutely no writing anywhere in the image: never letters, words, numbers or "
    "letter-like glyphs, and no speech bubbles, caption boxes or empty white placeholder rectangles."
)
# Every story panel: the model drifts the hero into tactical or military gear the sheet does not have
OUTFIT_LOCK = (
    "Outfit lock: every character wears exactly the outfit described above and shown on the character sheet, the same "
    "garments, colours and footwear in every panel, with bare hands and a plain civilian look. Handwear and gear appear "
    "only when named: no tactical, armoured or fingerless gloves, body armour, plate carriers, tactical vests, holsters, "
    "utility belts, harnesses or military uniforms unless the character's description, a listed prop or the scene names them. "
)
# Fingerless tactical gloves were the most common design defect (6 of the last 30 rejections, 4 of 4 comics): a
# ban alone did not hold, so every hero gets a positive "bare hands" unless the look, a prop or the scene names
# handwear (a Power Gauntlet prop, "gloved hand").
_HANDWEAR = re.compile(r"\b(?:gloves?|gloved|gauntlets?|mittens?|mitts?)\b", re.I)


def bare_hands(*texts: str) -> str:
    """The bare-hands line, or "" when the look, a prop or the scene names gloves or other handwear."""
    if any(_HANDWEAR.search(t or "") for t in texts):
        return ""
    return "Hands: bare skin on both hands, no gloves, fingerless gloves, mitts, wraps or straps of any kind. "


# Every story panel: the model sometimes splits one panel into two pictures with a seam line
SINGLE_IMAGE_RULE = (
    "One single continuous image: no panel borders, seams, split-screen or dividing lines. The setting runs unbroken "
    "from the top edge to the bottom edge, behind and around the figure, one moment seen by one camera, filling the whole "
    "canvas; never stack two pictures, bands or strips. The art style names how lines, colour and texture are rendered, "
    "never a physical object: the picture is the scene itself, with no drawn paper, canvas, print, page edges, mat, frame "
    "or blank margins."
)
SEAM_CORRECTION = re.compile(r"\b(?:seam|divider|dividing|split[- ]screen|panel (?:line|border)|border line|"
                             r"two (?:panels|pictures|images)|stacked|strip)\b", re.I)

# Every story panel in a place that is normally busy: the image model fills streets and stations with
# passers-by, which the checker rejects as extra humans. COMIC_CAST_RULE (app) already says Hero is the
# only human; this names the busy place as empty, only where the scene implies a crowd.
CROWD_PLACES = re.compile(
    r"\b(?:streets?|city|cities|town|downtown|avenue|alley(?:way)?s?|crosswalk|sidewalk|pavement|plaza|square|"
    r"market(?:place)?s?|bazaar|mall|shops?|stores?|caf[eé]s?|restaurants?|stations?|platforms?|subway|metro|"
    r"underground|tunnels?|train|tram|bus(?:es)?|airport|terminal|stadium|arena|crowds?|crowded|busy|"
    r"school(?:yard)?|hallway|corridor|lobby|harbou?r|port|pier|boardwalk|fair|festival|carnival)\b", re.I)
EMPTY_PLACE_RULE = (
    "Apart from the characters listed, the place is empty of people: no pedestrians, passers-by, background "
    "figures, silhouettes or reflections of people. "
)


def crowd_rule(scene: str) -> str:
    """EMPTY_PLACE_RULE when the scene is set where people usually are, else ""."""
    return EMPTY_PLACE_RULE if CROWD_PLACES.search(scene or "") else ""


def prop_shape(prop):
    """A stated triangular prism must not silently become an ornamental crystal rod."""
    look = prop.get('look', '').lower()
    return 'triangular_prism' if re.search(r'\btriangular\b', look) and re.search(r'\bprism\b', look) else None


def props_rule(cast: Dict) -> str:
    """The story's recurring props (cast["props"]), drawn identically in every panel and on the cover."""
    props = [p for p in cast.get("props") or [] if p.get("name") and p.get("look")]
    if not props:
        return ""
    listed = "; ".join(f"{p['name']}: {p['look']}" for p in props)
    geometry = " ".join(f"{p['name']} is a triangular optical wedge: two triangular end faces joined by three long faces, not a hexagonal crystal rod or pointed obelisk. Bevels do not change its triangular cross-section." for p in props if prop_shape(p))
    return (
        geometry + " Recurring props, drawn exactly as described every time they appear "
        f"(fixed identifying geometry, base colour, material and scale): {listed}. "
        "Allow approved changes of pose, position, opening, glow, lighting or damage while preserving the object's identity. "
        "Each story prop the scene shows appears exactly once, in the state the scene says: held or worn, never both, "
        "and never a second copy of it; a prop the scene calls hidden or put away is not drawn. "
        "Translate base colours into the selected style's palette; use identifying value contrast in monochrome. "
    )


# An extreme long shot needs a huge space: inside a room the camera can only back up to the opposite wall, so the
# hero is never a tiny figure and every draw failed the scale check (ed88ca80 panel 1, "in a modest city
# apartment"). Indoors the establishing shot is a wide shot: the whole room and the whole figure.
_INDOORS = re.compile(r"\b(?:apartment|flat|room|bedroom|living room|kitchen|bathroom|office|classroom|studio|attic|"
                      r"basement|cellar|hallway|corridor|cabin|tent|cockpit|lab|laboratory|workshop|garage|inside|"
                      r"indoors|interior)\b", re.I)
_OUTDOORS = re.compile(r"\b(?:rooftop|roof|skyline|street|streets|city below|valley|mountain|field|forest|beach|sea|"
                       r"desert|harbou?r|bridge|plaza|square|landscape|horizon|sky)\b", re.I)


def establishing_shot(scene: str) -> str:
    """The scene with an indoor "Extreme long shot:" drawn as a "Wide shot:"; anything else unchanged.

    Only the scene's own text decides (the host's appended character direction is ignored); a view through a
    window still counts as indoors, but a scene that is outdoors (a rooftop, a street) keeps its extreme long shot.
    """
    if scene_shot(scene) != "Extreme long shot":
        return scene
    head = re.split(r"\bOne human only\b|\bExpression and body language:", scene, maxsplit=1)[0]
    setting = re.split(r"\b(?:overlooking|looking out|through the window|toward|towards)\b", head, maxsplit=1)[0]
    if not _INDOORS.search(setting) or _OUTDOORS.search(setting):
        return scene
    return "Wide shot:" + scene.strip()[len("Extreme long shot:"):]


def cover_scene(scene: str) -> str:
    """The cover scene without a leading shot ("Extreme long shot: ..."): a cover always uses its own framing.

    The cover prompt asks for the hero from the knees up or full length; a planned extreme long shot (a tiny figure)
    contradicts it, so the vision check failed every draw as a scene mismatch (BOOKS-37, 2026-11-05).
    """
    shot = scene_shot(scene)
    bare = scene.strip()[len(shot) + 1:].strip() if shot else scene
    # "only his hands visible", "a boot at the edge of the frame": the clause goes, the cover shows the hero.
    clauses = [c for c in re.split(r"(?<=[,;])\s+", bare) if not _LIMB_CLAUSE.search(c)]
    return re.sub(r"[,;]\s*(?=[.!?]|$)", "", " ".join(clauses)).strip() if clauses else bare


_LIMB_CLAUSE = re.compile(r"\bonly\b[^.;]{0,40}?\b(?:hands?|fingers?|palms?|fists?|wrists?|arms?|feet|foot|boots?|shoes?|legs?)\b[^.;]{0,40}?"
                          r"\b(?:visible|in frame|in the frame|in shot|in view)\b|\bedge of the (?:frame|panel|image|shot)\b|"
                          r"\bout of (?:frame|shot|view)\b|\boff[- ](?:panel|frame|screen)\b", re.I)


def scene_shot(scene: str) -> Optional[str]:
    """The shot a scene starts with ("Medium shot: ..."), or None."""
    return next((shot for shot in COMIC_SHOTS if scene.strip().startswith(f"{shot}:")), None)


def shots_problem(panels: Sequence[Dict], establishing: bool = True) -> Optional[str]:
    """Why a page's shots break the camera rule, or None when they are fine.

    Args:
        panels: The page's panels, each with a "scene"
        establishing: The page opens a scene, so panel 1 must show the place
    """
    shots: List[Optional[str]] = [scene_shot(p.get("scene", "")) for p in panels]
    if any(shot is None for shot in shots):
        return "scene_without_shot"
    if establishing and shots and shots[0] not in ESTABLISHING_SHOTS:
        return "first_panel_not_establishing"
    if len(shots) > 1 and len(set(shots)) < 2:
        return "shots_not_varied"
    return None
