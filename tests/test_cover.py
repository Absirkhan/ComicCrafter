"""Cover art selection, seam detection and lettering, with fake clients."""

import pytest
from PIL import Image, ImageFont

from book_comic import cover as cover_module
from book_comic.cover import find_seam, panel_strip, render_cover
from book_comic.cover_lettering import FONTS_DIR, TITLE_FONT, letter_cover, one_line_font, resolve_font
from conftest import FakeImages, FakeVision

CAST = {"style": "comic", "characters": [{"name_en": "Dana", "look": "red coat"}],
        "props": [{"name": "the brass lantern", "look": "small brass hurricane lantern"}]}
COVER = {"scene": "Dana on the cliff", "title": "האור שחזר למגדלור", "starring": "בכיכוב דנה", "footer": ""}


def seamed(art):
    art = art.copy()
    art.paste((170, 172, 172), (0, 120, 400, 126))
    return art


def test_a_stacked_strip_seam_is_found_but_a_sky_is_not(noise):
    assert find_seam(seamed(noise())) == 126
    sky = noise()
    sky.paste((120, 160, 210), (0, 0, 400, 150))
    assert find_seam(sky) is None
    assert find_seam(noise()) is None


def test_the_cover_reference_shows_all_page_panels_in_order():
    assert panel_strip([]) is None
    strip = panel_strip([Image.new("RGB", (1800, 900), c) for c in ((200, 0, 0), (0, 200, 0), (0, 0, 200))])
    assert strip.height == 512
    assert [strip.getpixel((x, 256)) for x in (10, strip.width // 2, strip.width - 10)] == \
        [(200, 0, 0), (0, 200, 0), (0, 0, 200)]


@pytest.mark.parametrize("names, calls, colour, at_bottom", [
    (["clean"], 1, None, False),
    (["seamed", "clean"], 1, None, False),
    (["seamed", "seamed"], 1, None, False),  # both seamed: the seam is cut off
    (["high", "low"], 1, "blue", True),
    (["high", "high"], 1, "blue", True),  # both too high: never fails the job, the title moves to the bottom
    (["low"], 1, "red", False),
    (["seamed", "high"], 1, None, False),
    (["texted", "low"], 2, "red", False),
    (["texted", "high"], 2, "blue", True),
    (["handed", "low"], 2, "red", False),  # a third hand: drawn once more, the sound art kept
])
def test_cover_redraws_once_and_keeps_the_better_art(tmp_path, noise, monkeypatch, names, calls, colour, at_bottom):
    clean = noise()
    arts = {"clean": clean, "seamed": seamed(clean), "low": Image.new("RGB", (400, 600), "red"),
            "high": Image.new("RGB", (400, 600), "blue"), "texted": Image.new("RGB", (400, 600), "green"),
            "handed": Image.new("RGB", (400, 600), "yellow")}
    heads = {(255, 0, 0): 0.4, (0, 0, 255): 0.1}

    def inspect(prompt, art):
        pixel = art.getpixel((0, 0))
        return {"head_top": heads.get(pixel, 0.5) * 1000, "has_text": pixel == (0, 128, 0),
                "bad_anatomy": pixel == (255, 255, 0), "identity_mismatch": False, "design_mismatch": False, "scene_mismatch": False}

    lettered, bottoms = [], []
    monkeypatch.setattr(cover_module, "letter_cover",
                        lambda art, c, f, title_at_bottom: lettered.append(art) or bottoms.append(title_at_bottom) or art)
    images = FakeImages([arts[n] for n in names])
    render_cover(CAST, COVER, (400, 600), tmp_path / "cover.png", images, FakeVision(inspect),
                 panels=[Image.new("RGB", (300, 150))], references=["data:sheet"], reference_roles=["sheet"])
    assert len(images.calls) == calls
    art = lettered[0]
    assert art.size == (400, 600) and find_seam(art) is None
    assert bottoms == [at_bottom]
    if colour:
        assert art.getpixel((0, 0)) == Image.new("RGB", (1, 1), colour).getpixel((0, 0))
    prompt = images.calls[0]["prompt"]
    assert "small brass hurricane lantern" in prompt and "Absolutely no writing" in prompt
    assert "exactly two arms and two hands" in prompt
    assert "reference image 2 is the first page's panels" in prompt and len(images.calls[0]["references"]) == 2


def test_cover_lettering_shades_the_top_and_leaves_the_middle(tmp_path):
    art = Image.new("RGB", (400, 600), "white")
    lettered = letter_cover(art, {**COVER, "footer": "With love"})
    assert sum(lettered.getpixel((5, 5))) < 600
    assert lettered.getpixel((5, 300)) == (255, 255, 255)
    assert letter_cover(art, {"title": "Only a title"}).size == art.size  # starring and footer are optional


def test_a_high_head_moves_the_title_to_the_bottom_and_leaves_the_face_clear():
    art = Image.new("RGB", (400, 600), (90, 120, 160))
    shade_only = letter_cover(art, {"footer": "With love"})
    top = letter_cover(art, {**COVER, "footer": "With love"})
    low = letter_cover(art, {**COVER, "footer": "With love"}, title_at_bottom=True)
    lettered = lambda img, rows: sum(img.getpixel((x, y)) != shade_only.getpixel((x, y)) for x in range(400) for y in rows)
    upper, lower = range(0, 200), range(380, 600)
    assert lettered(top, upper) > 0 and lettered(low, upper) == 0  # nothing lettered where the head is
    assert lettered(top, lower) == 0 and lettered(low, lower) > 0  # the title and starring line sit at the bottom


def test_cover_fonts_are_bundled_and_a_title_font_choice_falls_back():
    for name in ("Rubik-Black.ttf", "Assistant-SemiBold.ttf", "Assistant-Regular.ttf"):
        ImageFont.truetype(str(FONTS_DIR / name), 96)
        assert resolve_font(name, TITLE_FONT) == FONTS_DIR / name
    for bad in (None, "", "../../etc/passwd", "Missing.ttf", "Rubik-Black.otf", "/no/such/font.ttf"):
        assert resolve_font(bad, TITLE_FONT) == TITLE_FONT
    assert resolve_font(str(FONTS_DIR / "Assistant-Regular.ttf"), TITLE_FONT).name == "Assistant-Regular.ttf"


def test_cover_title_always_fits_one_line():
    title = "המצאת יום ההולדת הגדולה של סבא"
    assert one_line_font(TITLE_FONT, title, 400, 1800).getlength(title) <= 1800
    assert one_line_font(TITLE_FONT, "קצר", 150, 1800).size == 150


def test_rejected_and_unchecked_covers_never_publish(tmp_path):
    for answer, code, calls in [({}, 'comic_art_check_unavailable', 1),
                                 ({'head_top': 400, 'has_text': True, 'bad_anatomy': False, 'identity_mismatch': False, 'design_mismatch': False, 'scene_mismatch': False}, 'comic_cover_rejected', 3)]:
        path = tmp_path / 'cover.png'
        images = FakeImages([Image.new('RGB', (400, 600), 'blue')])
        with pytest.raises(ValueError, match=code):
            render_cover(CAST, COVER, (400, 600), path, images, FakeVision(lambda p, i: answer))
        assert len(images.calls) == calls
        assert not path.exists()


def test_a_cover_whose_three_draws_all_drift_keeps_the_least_bad_one(tmp_path):
    """Soft drift only (no readable text, anatomy, face or seam): the page is not lost for the cover."""
    base = {'head_top': 400, 'has_text': False, 'bad_anatomy': False, 'identity_mismatch': False, 'design_mismatch': False}
    answers = iter([{**base, 'scene_mismatch': True, 'design_mismatch': True}, {**base, 'scene_mismatch': True},
                    {**base, 'scene_mismatch': True, 'design_mismatch': True}])
    images = FakeImages([Image.new('RGB', (400, 600), c) for c in ('red', 'green', 'blue')])
    audit = []
    path = tmp_path / 'cover.png'
    render_cover(CAST, COVER, (400, 600), path, images, FakeVision(lambda p, i: next(answers)), audit=audit)
    assert path.exists() and len(images.calls) == 3
    assert [r.get('fallback') for r in audit if r.get('kind') == 'cover'] == [None, True, None]


def test_a_cover_with_readable_text_on_every_draw_is_still_never_published(tmp_path):
    answer = {'head_top': 400, 'has_text': True, 'text_prominent': True, 'bad_anatomy': False,
              'identity_mismatch': False, 'design_mismatch': False, 'scene_mismatch': False}
    with pytest.raises(ValueError, match='comic_cover_rejected'):
        render_cover(CAST, COVER, (400, 600), tmp_path / 'c.png', FakeImages([Image.new('RGB', (400, 600), 'blue')]),
                     FakeVision(lambda p, i: answer))
