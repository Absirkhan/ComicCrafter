"""Blank paper margins: a print drawn on paper is trimmed to the picture, or redrawn when it cannot fill the panel."""

import random

import pytest

from PIL import Image

from book_comic.art_check import draw_checked
from book_comic.margins import MARGIN_CORRECTION, PAPER_TEXTURE, drawable_style, find_margins, target_aspect, trim_margins
from conftest import FakeImages, FakeVision

CREAM = (243, 236, 220)
CLEAN = {"has_text": False, "bad_anatomy": False, "identity_mismatch": False, "design_mismatch": False,
         "scene_mismatch": False, "head_top": 400, "lines": [], "protected": []}


def busy(width, height, seed=1):
    """Textured art: every row and column varies, like a drawn scene."""
    rng = random.Random(seed)
    image = Image.new("RGB", (width, height))
    image.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(width * height)])
    return image


def on_paper(picture, left, top, right, bottom, paper=CREAM):
    """The picture lying on paper with the given margins."""
    canvas = Image.new("RGB", (picture.width + left + right, picture.height + top + bottom), paper)
    canvas.paste(picture, (left, top))
    return canvas


def test_side_margins_like_e35347af_panel_3_are_trimmed_to_the_picture():
    art = on_paper(busy(300, 200), 120, 0, 120, 0)  # a 3:2 print centred on a wide panel
    box = find_margins(art)
    assert box is not None and abs(box[0] - 120) <= 8 and abs(box[2] - 420) <= 8
    picture, status = trim_margins(art, target_aspect(aspect_ratio="3:2"))
    assert status == "trimmed" and abs(picture.width - 300) <= 8


def test_a_picture_too_far_from_the_panel_shape_is_trimmed_but_marked_for_redraw():
    art = on_paper(busy(200, 200), 200, 0, 200, 0)
    picture, status = trim_margins(art, 600 / 200)
    assert status == "redraw" and abs(picture.width - 200) <= 8


def test_top_and_bottom_margins_count_too():
    picture, status = trim_margins(on_paper(busy(400, 200), 0, 60, 0, 60), 400 / 200)
    assert status == "trimmed" and abs(picture.height - 200) <= 8


def test_one_flat_sky_or_floor_is_scenery_never_cut():
    scene = busy(400, 300)
    scene.paste(Image.new("RGB", (400, 90), (120, 170, 230)), (0, 0))  # flat sky along the top only
    assert find_margins(scene) is None
    assert trim_margins(scene, 400 / 300) == (scene, None)


def test_full_art_and_plain_images_are_left_alone():
    art = busy(300, 200)
    assert trim_margins(art, 1.5) == (art, None)
    plain = Image.new("RGB", (30, 20), "red")
    assert trim_margins(plain, 1.5) == (plain, None)


def test_draw_checked_trims_before_the_check_and_keeps_the_panel_size():
    images = FakeImages([on_paper(busy(240, 160), 80, 0, 80, 0)])
    seen = []
    vision = FakeVision(lambda prompt, image: seen.append(image.size) or CLEAN)
    art = draw_checked(images, vision, "scene", [], "3:2", size=(240, 160))
    assert art.size == (240, 160) and len(images.calls) == 1
    assert all(size == (240, 160) for size in seen)
    left_column = [art.getpixel((0, y)) for y in range(art.height)]
    assert left_column.count(CREAM) < len(left_column) // 2  # the cream strip is gone


def test_draw_checked_redraws_a_print_that_cannot_fill_the_panel():
    images = FakeImages([on_paper(busy(100, 100, seed=2), 100, 0, 100, 0), busy(300, 100, seed=3)])
    vision = FakeVision(lambda prompt, image: CLEAN)
    art = draw_checked(images, vision, "scene", [], "3:1", size=(300, 100))
    assert len(images.calls) == 2
    assert MARGIN_CORRECTION in images.calls[1]["prompt"]
    assert art.size == (300, 100)


def test_an_untrimmable_print_is_judged_whole_never_as_a_crop_that_cuts_the_subject():
    seen = []
    images = FakeImages([on_paper(busy(100, 100, seed=4), 100, 0, 100, 0)])
    vision = FakeVision(lambda prompt, image: seen.append(image.copy()) or CLEAN)
    draw_checked(images, vision, "scene", [], "3:1", size=(300, 100), fallback=True)
    assert seen and all(img.getpixel((0, 50)) == CREAM for img in seen)  # the whole draw, margins and all


@pytest.mark.parametrize("style", [
    "woodcut folklore comic, parallel gouge marks, earthy inks on cream paper, preserve the specified age",
    "pencil sketchbook comic, light crosshatching on cream paper",
    "indie comic. Rendering: visible off-white paper with sparse teal accents.",
    "vintage pulp comic, halftone dots, aged paper and restrained vintage colors",
])
def test_stored_styles_never_ask_for_a_picture_on_paper(style):
    from book_comic.image_prompts import panel_prompt
    prompt = panel_prompt({"style": style, "characters": []}, {"scene": "Wide shot: Hero waits."}, "Hero: teal blazer")
    art_style = prompt.split("Art style: ", 1)[1].split("\n", 1)[0]
    assert "on cream paper" not in art_style and "visible off-white paper" not in art_style and "aged paper" not in art_style
    assert PAPER_TEXTURE in art_style


def test_cut_paper_and_paper_showing_through_stay_as_written():
    assert drawable_style("layered paper cutout comic, visibly cut edges and paper fibers") == "layered paper cutout comic, visibly cut edges and paper fibers"
    assert drawable_style("watercolor accents with paper showing through") == "watercolor accents with paper showing through"


def test_a_character_sheet_on_a_plain_background_is_never_trimmed_or_redrawn():
    sheet = on_paper(busy(60, 120, seed=5), 40, 30, 40, 30, paper=(255, 255, 255))
    images = FakeImages([sheet])
    art = draw_checked(images, FakeVision(lambda prompt, image: CLEAN), "sheet", [], "2:3")
    assert len(images.calls) == 1 and art.size == sheet.size


def test_a_flat_sky_above_and_flat_ground_below_are_scenery_not_margins():
    scene = busy(300, 400, seed=6)
    scene.paste(Image.new("RGB", (300, 60), (110, 160, 230)), (0, 0))     # sky
    scene.paste(Image.new("RGB", (300, 60), (40, 35, 30)), (0, 340))      # dark ground
    assert find_margins(scene) is None


def test_dark_edges_of_a_night_or_tunnel_scene_are_scenery_not_margins():
    tunnel = on_paper(busy(300, 200, seed=7), 90, 0, 90, 0, paper=(8, 8, 10))
    assert find_margins(tunnel) is None


def test_a_wide_panel_tells_the_model_its_shape_so_a_full_figure_is_not_an_upright_print():
    from book_comic.image_prompts import panel_prompt
    cast = {"style": "woodcut comic", "characters": []}
    wide = panel_prompt(cast, {"scene": "Wide shot: Hero stands in the apartment."}, "Hero: teal blazer", size=(1837, 944))
    assert "Canvas: a landscape frame about 1.9 times as wide as it is tall" in wide
    assert "never a narrower upright picture in the middle" in wide
    tall = panel_prompt(cast, {"scene": "Wide shot: Hero on the cliff."}, "Hero: teal blazer", splash=True, size=(1900, 2900))
    assert "Canvas: a portrait frame" in tall
    assert "Canvas:" not in panel_prompt(cast, {"scene": "Wide shot: Hero waits."}, "Hero: teal blazer")
