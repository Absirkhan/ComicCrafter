"""Full-page splash pages: one portrait panel, the same references and checks, and strip-sized lettering."""

import numpy as np
import pytest
from PIL import Image

from book_comic.art_check import ArtCheckError
from book_comic.render import PRINT_PAGE_SIZE, PageRenderer, RenderOptions, print_layouts
from conftest import FakeImages, FakeVision
from generation.openrouter_image_client import closest_aspect_ratio
from layout.lettering import LETTERING_FONT
from layout.panel_layout import LayoutManager, LayoutType

CAST = {"style": "comic", "characters": [{"name_en": "Dana", "name": "דנה", "look": "red coat"}]}
CLEAN = {"head_top": 500, "has_text": False, "bad_anatomy": False, "identity_mismatch": False,
         "design_mismatch": False, "scene_mismatch": False}
PLAN = {"lines": [{"mouth": [500, 600], "bubble": [500, 880]}], "protected": [[400, 450, 200, 250]]}
SPLASH = {
    "he": {"scene": "Wide shot: Dana stands on the cliff above the sleeping city at dawn.", "characters": ["Dana"],
           "caption": "העיר עוד ישנה, אבל דנה כבר ידעה לאן ללכת.",
           "dialogue": [{"speaker": "Dana", "text": "הנה זה מתחיל!"}]},
    "en": {"scene": "Wide shot: Dana stands on the cliff above the sleeping city at dawn.", "characters": ["Dana"],
           "caption": "The city still slept, but Dana knew where to go.",
           "dialogue": [{"speaker": "Dana", "text": "Here it begins!"}]},
}


def judge(flags=None):
    return FakeVision(lambda p, i: {**CLEAN, **PLAN, **(flags or {}).get(i.getpixel((0, 0)), {})})


def scenery(colour="skyblue"):
    return Image.new("RGB", (1024, 1536), colour)


def test_full_page_layout_is_the_strips_outer_frame():
    layouts = LayoutManager(page_width=400, page_height=600, margin=10, gutter=10)
    (slot,) = layouts.create_layout(LayoutType.FULL_PAGE)
    strip = layouts.create_layout(LayoutType.VERTICAL_STRIP, num_panels=3)
    assert (slot.x, slot.y, slot.width) == (strip[0].x, strip[0].y, strip[0].width)
    assert slot.y + slot.height == 600 - 10  # down to the bottom margin
    assert layouts.auto_layout(1) == LayoutType.FULL_PAGE


@pytest.mark.parametrize("language", ["he", "en"])
def test_a_splash_page_fills_the_print_page_with_one_checked_lettered_panel(tmp_path, language):
    images, vision = FakeImages([scenery()]), judge()
    options = RenderOptions(photo="data:photo", sheet_path=tmp_path / "sheet.png", chain_panels=True, check_art=True,
                            fail_on_image_error=True, font_path=str(LETTERING_FONT), rejected_dir=tmp_path / "rejected")
    r = PageRenderer({**CAST, "language": language}, images, vision, print_layouts(), options)
    page = r.render_page([SPLASH[language]], tmp_path / "page.png")

    sheet, panel = images.calls
    (slot,) = print_layouts().create_layout(LayoutType.FULL_PAGE)
    content = slot.get_content_area()[2:]
    assert Image.open(page).size == PRINT_PAGE_SIZE
    assert panel["aspect_ratio"] == closest_aspect_ratio(*content) == "2:3"  # portrait, like the page
    assert sheet["references"] == ["data:photo"] and panel["references"] == ["data:photo", r.character_sheet()]
    assert "Full-page splash illustration" in panel["prompt"] and "establishing" in panel["prompt"]
    assert "top or bottom fifth" in panel["prompt"] and "Comic book panel." not in panel["prompt"]
    art = tmp_path / "art_page_1.png"
    assert Image.open(art).size == content  # the next page's chain reference and the cover's panel input
    assert not (tmp_path / "rejected").exists()
    lettered = np.asarray(Image.open(page).convert("L"))
    cx, cy, cw, ch = slot.get_content_area()
    assert (lettered[cy:cy + ch, cx:cx + cw] < 64).any()  # caption and bubble ink on the plain art


def test_a_splash_is_lettered_at_a_strip_panels_type_size(tmp_path):
    r = PageRenderer(CAST, FakeImages([scenery()]), judge(), print_layouts(), RenderOptions())
    tall = Image.new("RGB", (1837, 2924), "white")
    panel = {"caption": "The city still slept.", "dialogue": [{"speaker": "Dana", "text": "Here it begins!"}]}
    strip_height = print_layouts().create_layout(LayoutType.VERTICAL_STRIP, num_panels=3)[0].get_content_area()[3]
    ink = lambda image: int((np.asarray(image.convert("L")) < 128).sum())  # noqa: E731
    matched, page_sized = ink(r._letter(tall, panel, strip_height)), ink(r._letter(tall, panel))
    assert 0 < matched < page_sized / 4  # roughly a third of the font height: about a ninth of the ink


def test_a_rejected_splash_is_redrawn_and_saved_as_panel_1(tmp_path):
    out = tmp_path / "rejected"
    images = FakeImages([scenery("red"), scenery("blue")])
    r = PageRenderer(CAST, images, judge({(255, 0, 0): {"has_text": True}}), print_layouts(),
                     RenderOptions(check_art=True, rejected_dir=out))
    r.render_page([{"scene": SPLASH["en"]["scene"], "characters": ["Dana"]}], tmp_path / "page.png")
    assert len(images.calls) == 2 and sorted(p.name for p in out.iterdir()) == ["panel_p1_d1.json", "panel_p1_d1.png"]

    images = FakeImages([scenery("red")])
    r = PageRenderer(CAST, images, judge({(255, 0, 0): {"has_text": True}}), print_layouts(), RenderOptions(check_art=True))
    with pytest.raises(ArtCheckError, match="comic_art_rejected"):
        r.render_page([{"scene": SPLASH["en"]["scene"]}], tmp_path / "page_2.png")
    assert len(images.calls) == 3  # at most three draws
    assert r.failure_diagnostic()["panel"] == 1


@pytest.mark.parametrize("count", [0, 2, 4])
def test_only_one_or_three_panels_make_a_page(tmp_path, count):
    images = FakeImages([scenery()])
    r = PageRenderer(CAST, images, judge(), print_layouts(), RenderOptions(sheet_path=tmp_path / "sheet.png"))
    with pytest.raises(ValueError, match="comic_page_panel_count"):
        r.render_page([{"scene": "Wide shot: a"}] * count, tmp_path / "page.png")
    assert images.calls == []


def test_a_splash_takes_at_most_one_bubble(tmp_path):
    images = FakeImages([scenery()])
    panel = {**SPLASH["en"], "dialogue": [{"speaker": "Dana", "text": "One"}, {"speaker": "Dana", "text": "Two"}]}
    with pytest.raises(ValueError, match="comic_splash_lettering"):
        PageRenderer(CAST, images, judge(), print_layouts(), RenderOptions()).render_page([panel], tmp_path / "page.png")
    assert images.calls == []


def test_three_panel_pages_keep_the_strip(tmp_path):
    images = FakeImages([scenery()])
    r = PageRenderer(CAST, images, judge(), print_layouts(), RenderOptions(chain_panels=True))
    r.render_page([{"scene": f"Wide shot: {n}"} for n in "abc"], tmp_path / "page.png")
    strip = print_layouts().create_layout(LayoutType.VERTICAL_STRIP, num_panels=3)
    assert [c["aspect_ratio"] for c in images.calls] == [closest_aspect_ratio(*strip[0].get_content_area()[2:])] * 3
    assert all("splash" not in c["prompt"] for c in images.calls)
    assert [len(c["references"]) for c in images.calls] == [0, 1, 1]  # the previous panel of the page
    assert [Image.open(tmp_path / f"art_page_{n}.png").size for n in (1, 2, 3)] == \
        [tuple(s.get_content_area()[2:]) for s in strip]
