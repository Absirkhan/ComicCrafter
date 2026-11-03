"""Best-of-three fallback: a panel whose three draws were all rejected keeps the least-bad draw without a hard defect."""

import pytest
from PIL import Image

from book_comic.art_check import ArtCheckError, draw_checked
from book_comic.best_draw import pick_fallback
from book_comic.render import PageRenderer, RenderOptions
from conftest import FakeImages, FakeVision
from layout.panel_layout import LayoutManager

RED, GREEN, BLUE = (255, 0, 0), (0, 128, 0), (0, 0, 255)
BASE = {"has_text": False, "bad_anatomy": False, "identity_mismatch": False, "design_mismatch": False, "scene_mismatch": False}
CAST = {"style": "comic", "characters": [{"name_en": "Dana", "look": "red coat"}],
        "props": [{"name": "the lantern", "look": "brass lantern"}]}
SMALL = LayoutManager(page_width=400, page_height=600, margin=10, gutter=10)


def colours(*names):
    return [Image.new("RGB", (10, 10), n) for n in names]


def judge(flags, extra=None):
    return FakeVision(lambda p, i: {**BASE, "head_top": 400, "lines": [], "protected": [], **(extra or {}),
                                    **flags.get(i.getpixel((0, 0)), {})})


def test_the_draw_with_the_fewest_failed_checks_is_kept():
    images = FakeImages(colours("red", "green", "blue"))
    vision = judge({RED: {"scene_mismatch": True, "design_mismatch": True}, GREEN: {"scene_mismatch": True},
                    BLUE: {"design_mismatch": True, "scene_mismatch": True}})
    audit = []
    art = draw_checked(images, vision, "scene", [], "2:3", audit=audit, fallback=True)
    assert art.getpixel((0, 0)) == GREEN and len(images.calls) == 3
    assert [r.get("fallback") for r in audit] == [None, True, None]
    assert all(r["accepted"] is False for r in audit)
    assert art.info["comic_verification"]["fallback"] is True


def test_a_tie_keeps_the_earliest_draw():
    images = FakeImages(colours("red", "green", "blue"))
    art = draw_checked(images, judge({c: {"scene_mismatch": True} for c in (RED, GREEN, BLUE)}), "scene", [], "2:3", fallback=True)
    assert art.getpixel((0, 0)) == RED


@pytest.mark.parametrize("hard", ["has_text", "bad_anatomy", "identity_mismatch"])
def test_a_hard_defect_is_never_kept_even_when_it_is_the_only_failure(hard):
    images = FakeImages(colours("red", "green", "blue"))
    vision = judge({RED: {hard: True}, GREEN: {"scene_mismatch": True, "design_mismatch": True}, BLUE: {hard: True}})
    art = draw_checked(images, vision, "scene", [], "2:3", fallback=True)
    assert art.getpixel((0, 0)) == GREEN


def test_three_hard_defects_still_fail_the_panel():
    images = FakeImages(colours("red", "green", "blue"))
    vision = judge({RED: {"has_text": True}, GREEN: {"bad_anatomy": True}, BLUE: {"identity_mismatch": True}})
    with pytest.raises(ArtCheckError, match="comic_art_rejected"):
        draw_checked(images, vision, "scene", [], "2:3", fallback=True)


def test_without_the_fallback_three_soft_rejections_still_fail():
    images = FakeImages(colours("red", "green", "blue"))
    with pytest.raises(ArtCheckError, match="comic_art_rejected"):
        draw_checked(images, judge({c: {"scene_mismatch": True} for c in (RED, GREEN, BLUE)}), "scene", [], "2:3")


def test_an_unavailable_check_still_raises_at_once():
    images = FakeImages(colours("red", "green", "blue"))
    with pytest.raises(ArtCheckError, match="comic_art_check_unavailable"):
        draw_checked(images, judge({RED: {"has_text": None}}), "scene", [], "2:3", fallback=True)
    assert len(images.calls) == 1


def test_failed_requirement_checks_break_a_tie_in_flags():
    rejected = [(None, {"requirement_mismatch": True, "requirement_checks": [{"matches": False}, {"matches": False}]}),
                (None, {"requirement_mismatch": True, "requirement_checks": [{"matches": True}, {"matches": False}]})]
    assert pick_fallback(rejected) == 1


def test_a_kept_draw_anchors_only_props_it_drew_correctly(tmp_path):
    lantern = [{"name": "the lantern", "visible": True, "observed": "a green plastic torch", "matches": False}]
    vision = judge({}, {"scene_mismatch": True, "prop_mismatch": True, "prop_checks": lantern})
    r = PageRenderer(CAST, FakeImages(colours("red", "green", "blue")), vision, SMALL, RenderOptions(check_art=True))
    path = r.render_page([{"scene": "Dana holds the lantern"}], tmp_path / "page_02.png")
    assert path.exists() and "the lantern" not in r.prop_anchors
    assert [a.get("fallback") for a in r.audit] == [True, None, None]


def test_the_character_sheet_never_uses_the_fallback(tmp_path):
    vision = judge({}, {"scene_mismatch": True})
    r = PageRenderer(CAST, FakeImages(colours("red", "green", "blue")), vision, SMALL,
                     RenderOptions(check_art=True, sheet_path=tmp_path / "sheet.png"))
    with pytest.raises(ArtCheckError, match="comic_art_rejected"):
        r.character_sheet()
    assert not (tmp_path / "sheet.png").exists()
