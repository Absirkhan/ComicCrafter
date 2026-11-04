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
    "Absolutely no writing anywhere in the image: no letters, words, captions, labels, signs, speech "
    "bubbles, empty caption boxes or sound-effect lettering. Objects that usually carry writing have plain surfaces, "
    "not garbled glyphs. Walls, posters, murals, graffiti, billboards and plaques are plain paint, texture or simple "
    "pictures with no letters or letter-like marks. Neon signs, shop signs, screens and holograms are abstract glowing "
    "shapes, stripes, arrows or simple icons, never letters, words, numbers or letter-like glyphs. Instrument faces use geometric ticks and pointers only: no cardinal letters, digits or invented glyphs. Do not draw an empty white rectangle as a placeholder for later lettering."
)

# Every story panel: the model drifts the hero into tactical or military gear the sheet does not have
OUTFIT_LOCK = (
    "Outfit lock: every character wears exactly the outfit described above and shown on the character sheet, "
    "unchanged from panel to panel. Do not add tactical or combat gear: no tactical, armoured or fingerless gloves, "
    "no body armour, plate carriers or tactical vests, no holsters, utility belts, harnesses or military uniforms, "
    "unless the character's description, a listed prop or the scene names them. "
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
    "One single continuous image: no panel borders, seams, split-screen or horizontal or vertical dividing "
    "lines across the picture. The setting runs unbroken from the top edge to the bottom edge, behind and "
    "around the figure; never stack two pictures, bands or strips. The art style names how lines, colour and "
    "texture are rendered, never a physical object: do not draw the paper, canvas, print, page edges, mat, frame "
    "or blank margins around the picture."
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
