"""Back cover: setting-only prompt, the figure check, the fallback and the lettered panel, with fake clients."""

import pytest
from PIL import Image

from book_comic import back_cover as back_module
from book_comic.art_check import ArtCheckError
from book_comic.back_cover import render_back_cover
from book_comic.back_cover_lettering import PANEL_TOP, letter_back_cover
from book_comic.best_draw import pick_fallback
from book_comic.image_prompts import back_cover_prompt
from conftest import FakeImages, FakeVision

CAST = {"style": "gritty ink comic on cream paper", "characters": [{"name_en": "Hero", "look": "blue work shirt"}]}
BACK = {"scene": "A flooded Victorian hallway at midnight, copper pipes along the walls.",
        "tagline": "Terror flows through the pipes", "blurb": "A midnight call. A storm. A house that will not let go."}
HE_BACK = {"scene": "מסדרון", "tagline": "האימה זורמת בצינורות", "blurb": "שיחה בחצות. סערה. בית שלא מרפה."}


def colour(c):
    return lambda: Image.new("RGB", (400, 600), c)


def test_the_prompt_asks_for_an_empty_setting_without_naming_lettering():
    prompt = back_cover_prompt(CAST, BACK, (400, 600), ["style"])
    assert "nobody in it" in prompt and "flooded Victorian hallway" in prompt
    assert "front cover sets the drawing style" in prompt
    assert "on cream paper" not in prompt  # paper wording becomes a texture (drawable_style)
    for word in ("blurb", "tagline", "text box", "Terror flows"):
        assert word not in prompt
    assert "portrait frame" in prompt


def test_a_figure_is_a_hard_defect_never_kept():
    assert pick_fallback([(None, {"figure_visible": True, "has_text": False})]) is None
    assert pick_fallback([(None, {"figure_visible": False, "scene_mismatch": True})]) == 0


@pytest.mark.parametrize("answers, calls, kept", [
    ([{"figure_visible": False}], 1, (10, 20, 30)),
    ([{"figure_visible": True}, {"figure_visible": False}], 2, (40, 50, 60)),
])
def test_a_figure_is_redrawn_and_the_empty_setting_is_lettered(tmp_path, monkeypatch, answers, calls, kept):
    seen = []
    monkeypatch.setattr(back_module, "find_seam", lambda art: None)
    monkeypatch.setattr(back_module, "letter_back_cover", lambda art, back, fonts: seen.append(art.getpixel((5, 5))) or art)
    images = FakeImages([Image.new("RGB", (400, 600), (10, 20, 30)), Image.new("RGB", (400, 600), (40, 50, 60))])
    queue = list(answers)
    vision = FakeVision(lambda prompt, image: {"has_text": False, "bad_anatomy": False, "head_top": None, **queue.pop(0)})
    audit = []
    render_back_cover(CAST, BACK, (400, 600), tmp_path / "back.png", images, vision,
                      style_art=Image.new("RGB", (400, 600), "grey"), audit=audit)
    assert len(images.calls) == calls and seen == [kept]
    assert len(images.calls[0]["references"]) == 1  # the front cover as the style reference
    assert "figure_visible" in vision.prompts[0] and "identity_mismatch" not in vision.prompts[0]
    assert all(entry["kind"] == "back_cover" for entry in audit)
    assert (tmp_path / "back.png").exists()


def test_three_draws_with_people_fall_back_to_the_blurred_front_cover(tmp_path, monkeypatch):
    monkeypatch.setattr(back_module, "find_seam", lambda art: None)
    kept = []
    monkeypatch.setattr(back_module, "letter_back_cover", lambda art, back, fonts: kept.append(art) or art)
    images = FakeImages([Image.new("RGB", (400, 600), "grey")])
    vision = FakeVision(lambda prompt, image: {"has_text": False, "bad_anatomy": False, "figure_visible": True})
    front = Image.new("RGB", (400, 600), (200, 100, 50))
    audit = []
    render_back_cover(CAST, BACK, (400, 600), tmp_path / "back.png", images, vision, style_art=front, audit=audit)
    assert len(images.calls) == 3
    assert kept[0].size == (400, 600) and kept[0].getpixel((200, 300)) == (120, 60, 30)  # the front, darkened
    assert audit[-1]["fallback"] == "front_blur"


def test_without_a_front_cover_three_draws_with_people_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(back_module, "find_seam", lambda art: None)
    images = FakeImages([Image.new("RGB", (400, 600), "grey")])
    vision = FakeVision(lambda prompt, image: {"has_text": False, "bad_anatomy": False, "figure_visible": True})
    with pytest.raises(ArtCheckError, match="comic_back_cover_rejected"):
        render_back_cover(CAST, BACK, (400, 600), tmp_path / "back.png", images, vision)
    assert len(images.calls) == 3


def test_a_stacked_strip_is_cut_off_instead_of_drawing_again(tmp_path, monkeypatch):
    seams = iter([300, None])
    monkeypatch.setattr(back_module, "find_seam", lambda art: next(seams))
    monkeypatch.setattr(back_module, "letter_back_cover", lambda art, back, fonts: art)
    images = FakeImages([Image.new("RGB", (400, 600), "grey")])
    vision = FakeVision(lambda prompt, image: {"has_text": False, "bad_anatomy": False, "figure_visible": False})
    render_back_cover(CAST, BACK, (400, 600), tmp_path / "back.png", images, vision)
    assert len(images.calls) == 1


def test_an_unavailable_check_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(back_module, "find_seam", lambda art: None)
    with pytest.raises(ArtCheckError, match="comic_art_check_unavailable"):
        render_back_cover(CAST, BACK, (400, 600), tmp_path / "b.png", FakeImages([Image.new("RGB", (400, 600))]), FakeVision())


@pytest.mark.parametrize("back", [BACK, HE_BACK, {**BACK, "blurb": " ".join(["A long blurb sentence."] * 40)}])
def test_the_panel_darkens_the_upper_half_and_leaves_the_bottom(back):
    art = Image.new("RGB", (800, 1200), (200, 200, 200))
    out = letter_back_cover(art, back)
    assert out.size == art.size
    inside = out.getpixel((60 + 20, int(1200 * PANEL_TOP) + 20))
    assert sum(inside) < sum((200, 200, 200)) - 150  # the translucent dark panel
    assert out.getpixel((400, 1150)) == (200, 200, 200)  # below the panel the art is untouched
    assert out.getpixel((10, 10)) == (200, 200, 200)


def test_no_text_leaves_the_art_as_it_is():
    art = Image.new("RGB", (400, 600), (90, 90, 90))
    assert letter_back_cover(art, {"tagline": "", "blurb": ""}).getpixel((200, 300)) == (90, 90, 90)
