"""Hard framing and facing rules in panel prompts, and their repeat on redraw."""

import pytest
from PIL import Image

from book_comic.art_check import draw_checked
from book_comic.framing import framing_block, scene_orientation, shot_framing
from book_comic.image_prompts import panel_prompt
from book_comic.render import PageRenderer, RenderOptions
from book_comic.scene_requirements import scene_requirements
from conftest import FakeImages, FakeVision
from layout.panel_layout import LayoutManager

CAST = {"style": "ink comic", "characters": [{"name_en": "Hero", "look": "teal blazer"}, {"name_en": "Omer", "look": "green cap"}]}
CLEAN = {"has_text": False, "bad_anatomy": False, "identity_mismatch": False, "design_mismatch": False, "scene_mismatch": False}


@pytest.mark.parametrize("scene, opening, phrase", [
    ("Extreme long shot: Hero crosses the valley.", "EXTREME LONG SHOT:", "taller than one-quarter of the image height is wrong"),
    ("Wide shot: Hero waits at the bus stop.", "WIDE SHOT:", "from the top of the head to the feet"),
    ("Medium shot: Hero argues with the clerk.", "MEDIUM SHOT: crop at the waist.", "hips, legs and feet are outside the frame"),
    ("Close-up: Hero's face, eyes wide.", "CLOSE-UP:", "head and shoulders only"),
])
def test_each_shot_label_opens_the_prompt_with_its_crop(scene, opening, phrase):
    prompt = panel_prompt(CAST, {"scene": scene}, "Hero: teal blazer")
    assert prompt.startswith(opening)
    assert phrase in prompt.split("Comic book panel.")[0]


def test_no_label_means_no_crop_but_the_single_image_rule_stays():
    assert shot_framing("Hero argues with the clerk.") == ""
    prompt = panel_prompt(CAST, {"scene": "Hero argues with the clerk."}, "Hero: teal blazer")
    assert prompt.startswith("One single continuous image: no panel borders, seams, split-screen")


@pytest.mark.parametrize("scene", [
    "Close-up: hand detail of Hero turning the brass key.",
    "Close-up of Hero's right hand on the brass key, no face or torso.",
    "Close-up: detail of his hands untying the knot.",
    # e35347af panel 3: the shot label then the hand as the subject, with the host's character direction appended
    "Close-up: Hero's hand closes the Notebook abruptly as footsteps approach, cloak edge visible. One human only. "
    "Expression and body language: Hero has an observant, curious presence; show this moment's emotion through the "
    "face when visible, otherwise through gesture or posture.",
    "Close-up: Hero's right hand presses the brass key into the lock.",
])
def test_named_hand_details_become_limb_only_crops(scene):
    requirements = scene_requirements(scene)
    assert {"subject": "frame", "attribute": "framing", "expected": "hand_detail_only"} in requirements
    prompt = panel_prompt(CAST, {"scene": scene}, "Hero: teal blazer")
    assert prompt.startswith("LIMB-ONLY MACRO DETAIL")
    assert "chest, torso" in prompt and "second hand appears only when the scene names both hands" in prompt


@pytest.mark.parametrize("scene", [
    "Close-up of Hero's hand on the door while his face shows fear.",
    "Medium shot: Hero raises both hands.",
    "Close-up: Hero's face as the hand of the clock strikes.",
    "Close-up: Hero's hand on the rail while Hero's face shows fear. Expression and body language: calm.",
])
def test_hands_with_a_visible_face_or_body_are_not_limb_only(scene):
    assert not any(r["attribute"] == "framing" for r in scene_requirements(scene))


@pytest.mark.parametrize("scene, expected", [
    ("Extreme long shot: Hero stands before the mouth of an old tunnel.", [("face", "the mouth of an old tunnel")]),
    ("Wide shot: Hero is facing the stone tunnel, lantern raised.", [("face", "the stone tunnel")]),
    ("Medium shot: Hero looks up at the clock tower.", [("look", "the clock tower")]),
    ("Wide shot: Hero walks toward the gate and opens it.", [("move", "the gate")]),
    ("Wide shot: Hero approaches the old well.", [("move", "the old well")]),
    ("Medium shot: Hero turns away from the burning house.", [("away", "the burning house")]),
    ("Wide shot: Hero stands with her back to the sea.", [("away", "the sea")]),
    ("Medium shot: Hero faces the viewer, grinning.", [("viewer", "the viewer")]),
    ("Wide shot: Hero, seen from behind, walks into the forest.", [("back", "the viewer"), ("move", "the forest")]),
])
def test_stated_facing_is_extracted(scene, expected):
    assert scene_orientation(scene, CAST) == expected


@pytest.mark.parametrize("scene", [
    "Wide shot: Hero runs through the forest.",
    "Medium shot: Hero stands before dawn breaks.",
    "Wide shot: Omer faces the tunnel while Hero sits.",
    "Wide shot: Hero waves while Omer faces the tunnel.",
    "Medium shot: Omer walks toward the gate.",
    "Close-up: Hero smiles.",
])
def test_no_direction_is_invented(scene):
    assert scene_orientation(scene, CAST) == []
    assert "ORIENTATION" not in panel_prompt(CAST, {"scene": scene}, "Hero: teal blazer")


def test_orientation_follows_the_crop_and_precedes_the_scene():
    prompt = panel_prompt(CAST, {"scene": "Extreme long shot: Hero stands before the mouth of an old tunnel."}, "Hero: teal blazer")
    crop, orientation, scene = (prompt.index(s) for s in ("EXTREME LONG SHOT", "ORIENTATION: Hero faces the mouth", "Scene:"))
    assert crop == 0 < orientation < scene
    assert "never behind" in prompt and "do not turn Hero around toward the camera" in prompt


def test_orientation_uses_the_hero_name_from_the_cast():
    cast = {"characters": [{"name_en": "Dana", "look": "red coat"}]}
    block = framing_block(cast, {"scene": "Wide shot: Dana walks toward the lighthouse."})
    assert "ORIENTATION: Dana moves toward the lighthouse" in block
    assert framing_block(cast, {"scene": "Wide shot: Hero walks toward the lighthouse."}).count("ORIENTATION: Dana") == 1


def colours(*names):
    return [Image.new("RGB", (64, 64), n) for n in names]


def test_redraw_after_a_scene_mismatch_repeats_the_framing():
    images = FakeImages(colours("red", "blue"))
    vision = FakeVision(lambda p, i: {**CLEAN, "scene_mismatch": i.getpixel((0, 0)) == (255, 0, 0)})
    framing = framing_block(CAST, {"scene": "Medium shot: Hero faces the tunnel."})
    draw_checked(images, vision, "prompt", [], "2:3", framing=framing)
    assert "MEDIUM SHOT" not in images.calls[0]["prompt"]
    assert "Repeat of the required framing: MEDIUM SHOT: crop at the waist." in images.calls[1]["prompt"]
    assert "ORIENTATION: Hero faces the tunnel" in images.calls[1]["prompt"]


def test_redraw_after_only_writing_does_not_repeat_the_framing():
    images = FakeImages(colours("red", "blue"))
    vision = FakeVision(lambda p, i: {**CLEAN, "has_text": i.getpixel((0, 0)) == (255, 0, 0)})
    draw_checked(images, vision, "prompt", [], "2:3", framing="MEDIUM SHOT: crop at the waist.")
    assert "Repeat of the required framing" not in images.calls[1]["prompt"]


def test_renderer_passes_the_panel_framing_to_the_redraw(tmp_path):
    images = FakeImages(colours("red", "blue"))
    vision = FakeVision(lambda p, i: {**CLEAN, "scene_mismatch": i.getpixel((0, 0)) == (255, 0, 0)})
    renderer = PageRenderer(CAST, images, vision, LayoutManager(page_width=400, page_height=600, margin=10, gutter=10),
                            RenderOptions(check_art=True))
    renderer.render_page([{"scene": "Wide shot: Hero walks toward the gate.", "characters": ["Hero"]}], tmp_path / "page_01.png")
    assert images.calls[0]["prompt"].startswith("WIDE SHOT:")
    assert "Repeat of the required framing: WIDE SHOT:" in images.calls[1]["prompt"]
    assert "ORIENTATION: Hero moves toward the gate" in images.calls[1]["prompt"]


def test_a_wide_shot_keeps_both_shoes_and_the_ground_inside_the_frame():
    prompt = panel_prompt(CAST, {"scene": "Wide shot: Hero stands in a modest apartment at dawn."}, "Hero: teal blazer")
    assert "both shoes and the ground they stand on are drawn above the bottom edge" in prompt


@pytest.mark.parametrize("scene, kind", [
    ("Close-up: Hero's fingers turn the brass dial.", "hand"),
    ("Close-up on Hero's palm holding the glowing seed.", "hand"),
    ("Extreme close-up: Hero's clenched fist around the rope.", "hand"),
    ("Close-up: Hero's gloved hand grips the rail.", "hand"),
    ("Close-up: Hero's boots splash through the puddle.", "feet"),
    ("Close-up: Hero's feet balance on the narrow beam. Expression and body language: steady, calm face.", "feet"),
])
def test_any_limb_named_after_the_close_up_label_is_a_limb_detail(scene, kind):
    assert {"subject": "frame", "attribute": "framing", "expected": f"{kind}_detail_only"} in scene_requirements(scene)


@pytest.mark.parametrize("scene", [
    "Close-up: Hero's face lit by the lantern.",
    "Close-up: Hero's eyes widen at the noise.",
    "Close-up: Hero's hand on the rail while his face shows fear.",
])
def test_a_close_up_of_the_face_stays_a_normal_close_up(scene):
    assert not any(r["attribute"] == "framing" for r in scene_requirements(scene))


def test_state_changes_draw_the_end_state_and_hidden_props_are_never_drawn():
    cast = {**CAST, "props": [{"name": "Notebook", "look": "brown leather journal"}]}
    prompt = panel_prompt(cast, {"scene": "Medium shot: Hero at a corner, Notebook tucked away."}, "Hero: teal blazer")
    assert "draw the instant just after it completes: the object is already in its new state" in prompt
    assert "tucked away, pocketed, stowed, packed, under clothing or out of sight is not drawn at all" in prompt
    assert "a prop the scene calls hidden or put away is not drawn" in prompt


def test_the_art_style_is_never_drawn_as_paper_frame_or_margins():
    prompt = panel_prompt({"style": "woodcut comic, earthy inks on cream paper", "characters": []},
                          {"scene": "Wide shot: Hero in a modest apartment."}, "Hero: teal blazer")
    assert "do not draw the paper, canvas, print, page edges, mat, frame or blank margins around the picture" in prompt
