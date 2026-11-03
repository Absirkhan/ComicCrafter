"""Per-shot calm area for lettering, the checker kept consistent with it, and the other scene rules."""

import pytest
from PIL import Image

from book_comic.art_check import draw_checked, inspect_art
from book_comic.comic_rules import NO_TEXT_RULE, SINGLE_IMAGE_RULE, crowd_rule
from book_comic.image_prompts import panel_prompt
from book_comic.lettering_space import BAND, CHECK_NOTE, CORNER, SIDE, useful_corrections
from conftest import FakeImages, FakeVision

CAST = {"style": "ink comic", "characters": [{"name_en": "Hero", "look": "teal blazer"}]}
LETTERED = {"caption": "PRIVATE_CAPTION", "dialogue": [{"text": "PRIVATE_LINE"}]}
CLEAN = {"has_text": False, "bad_anatomy": False, "identity_mismatch": False, "design_mismatch": False, "scene_mismatch": False}


def prompt_for(scene, lettered=True):
    return panel_prompt(CAST, {"scene": scene, **(LETTERED if lettered else {})}, "Hero: teal blazer")


@pytest.mark.parametrize("scene, line", [
    ("Extreme long shot: Hero crosses the valley.", BAND),
    ("Wide shot: Hero waits by the gate.", BAND),
    ("Medium shot: Hero argues with the wind.", SIDE),
    ("Close-up: Hero's face, eyes wide.", SIDE),
    ("Close-up: hand detail of Hero turning the brass key.", CORNER),
])
def test_each_shot_asks_for_the_calm_area_that_fits_its_crop(scene, line):
    prompt = prompt_for(scene)
    assert line in prompt
    assert "PRIVATE_CAPTION" not in prompt and "PRIVATE_LINE" not in prompt
    crop_end = prompt.index("One single continuous image")
    assert crop_end < prompt.index(line) < prompt.index("Scene:")  # crop, orientation, single image, then the area


@pytest.mark.parametrize("scene", ["Medium shot: Hero argues with the wind.", "Close-up: Hero's face, eyes wide."])
def test_medium_shots_and_close_ups_never_ask_for_a_clear_upper_third(scene):
    prompt = prompt_for(scene)
    assert "upper third clear" not in prompt and "below the upper third" not in prompt
    assert "the head may reach into the upper third" in prompt and "never lower, shrink or re-crop" in prompt


def test_an_unlettered_panel_asks_for_no_calm_area_and_lettering_is_never_named_to_the_image_model():
    assert "CALM AREA" not in prompt_for("Medium shot: Hero smiles.", lettered=False)
    for line in (BAND, SIDE, CORNER):
        assert "letter" not in line.lower() and "caption" not in line.lower()


def test_the_checker_is_told_the_calm_area_never_rejects_art():
    vision = FakeVision(lambda p, i: CLEAN)
    inspect_art(Image.new("RGB", (64, 64)), vision, context="brief")
    assert CHECK_NOTE in vision.prompts[0]
    assert "never set scene_mismatch" in CHECK_NOTE and "upper third" in CHECK_NOTE
    assert "taller than about one-quarter of the image height is still wrong" in CHECK_NOTE  # #11 kept
    inspect_art(Image.new("RGB", (64, 64)), vision)
    assert CHECK_NOTE not in vision.prompts[1]  # the sheet check has no brief and no calm area


def test_lettering_clearance_advice_is_dropped_from_the_redraw_but_real_corrections_stay():
    corrections = ["Keep the upper third of the canvas clear of faces and focal subjects for lettering clearance",
                   "Lower the character so the head and face remain below the upper third",
                   "Remove the pseudo-lettering from the poster on the left wall",
                   "Scale down the figure so it fills at most two-thirds of the frame height"]
    assert useful_corrections(corrections) == corrections[2:]
    images = FakeImages([Image.new("RGB", (64, 64), c) for c in ("red", "blue")])
    vision = FakeVision(lambda p, i: {**CLEAN, "scene_mismatch": i.getpixel((0, 0)) == (255, 0, 0), "corrections": corrections})
    draw_checked(images, vision, "Medium shot: Hero waits.", [], "2:1")
    redraw = images.calls[1]["prompt"]
    assert "pseudo-lettering from the poster" in redraw and "below the upper third" not in redraw


def test_a_seam_the_checker_reports_repeats_the_single_image_rule_on_redraw():
    images = FakeImages([Image.new("RGB", (64, 64), c) for c in ("red", "blue")])
    vision = FakeVision(lambda p, i: {**CLEAN, "has_text": i.getpixel((0, 0)) == (255, 0, 0),
                                      "corrections": ["Remove the horizontal panel divider line"] if i.getpixel((0, 0)) == (255, 0, 0) else []})
    art = draw_checked(images, vision, "Wide shot: Hero waits.", [], "2:1")
    assert SINGLE_IMAGE_RULE in images.calls[1]["prompt"] and SINGLE_IMAGE_RULE not in images.calls[0]["prompt"]
    assert art.info["comic_verification"]["seam"] is False  # bookkeeping, never a rejection flag
    assert "never stack two pictures, bands or strips" in SINGLE_IMAGE_RULE
    assert prompt_for("Wide shot: Hero waits.").count(SINGLE_IMAGE_RULE) == 2  # opening block and closing line


@pytest.mark.parametrize("scene", ["Wide shot: Hero walks down a rainy street.", "Medium shot: Hero waits on the station platform.",
                                   "Wide shot: Hero crosses the market square.", "Extreme long shot: Hero enters the old tunnel."])
def test_places_that_imply_crowds_are_empty_of_other_people(scene):
    prompt = prompt_for(scene)
    assert "no pedestrians, passers-by, background figures, silhouettes or reflections of people" in prompt
    assert prompt.count(crowd_rule(scene)) == 1


def test_quiet_places_get_no_crowd_line():
    assert crowd_rule("Wide shot: Hero kneels in a forest clearing.") == ""


def test_props_appear_once_and_no_unapproved_accessories():
    cast = {**CAST, "props": [{"name": "Amulet", "look": "round silver amulet"}]}
    prompt = panel_prompt(cast, {"scene": "Medium shot: Hero holds the Amulet."}, "Hero: teal blazer")
    assert "Each story prop appears exactly once, in the state the scene says: held or worn, never both" in prompt
    assert "No accessories beyond the approved appearance (gloves, jewellery, necklaces, pendants, watches, hats, bags)" in prompt


def test_walls_posters_murals_graffiti_and_plaques_carry_no_writing():
    for surface in ("Walls", "posters", "murals", "graffiti", "billboards", "plaques"):
        assert surface in NO_TEXT_RULE
