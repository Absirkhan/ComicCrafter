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


def test_a_tie_keeps_the_latest_draw_which_carries_the_corrections():
    images = FakeImages(colours("red", "green", "blue"))
    art = draw_checked(images, judge({c: {"scene_mismatch": True} for c in (RED, GREEN, BLUE)}), "scene", [], "2:3", fallback=True)
    assert art.getpixel((0, 0)) == BLUE


@pytest.mark.parametrize("hard", ["has_text", "bad_anatomy", "identity_mismatch"])
def test_a_hard_defect_is_never_kept_even_when_it_is_the_only_failure(hard):
    images = FakeImages(colours("red", "green", "blue"))
    vision = judge({RED: {hard: True}, GREEN: {"scene_mismatch": True, "design_mismatch": True}, BLUE: {hard: True}})
    art = draw_checked(images, vision, "scene", [], "2:3", fallback=True)
    assert art.getpixel((0, 0)) == GREEN


SEAM = {"scene_mismatch": True, "corrections": ["Remove the horizontal dividing seam across the top of the frame."]}


def test_a_seam_is_never_kept():
    # Production 2026-11-03 (e986d71f page 1 panel 1): the kept draw had a dividing line across the top.
    images = FakeImages(colours("red", "green", "blue"))
    vision = judge({RED: SEAM, GREEN: {"scene_mismatch": True, "design_mismatch": True}, BLUE: SEAM})
    art = draw_checked(images, vision, "scene", [], "2:3", fallback=True)
    assert art.getpixel((0, 0)) == GREEN


def test_three_seams_fail_the_panel():
    images = FakeImages(colours("red", "green", "blue"))
    with pytest.raises(ArtCheckError, match="comic_art_rejected"):
        draw_checked(images, judge({c: SEAM for c in (RED, GREEN, BLUE)}), "scene", [], "2:3", fallback=True)


def test_a_seam_word_without_a_scene_mismatch_is_not_a_hard_defect():
    # The checker flags a real seam as scene_mismatch; a stray word in another correction blocks nothing.
    images = FakeImages(colours("red", "green", "blue"))
    stray = {"design_mismatch": True, "corrections": ["Remove the strip of tape from the jacket."]}
    vision = judge({RED: stray, GREEN: {"design_mismatch": True, "scene_mismatch": True}, BLUE: stray})
    assert draw_checked(images, vision, "scene", [], "2:3", fallback=True).getpixel((0, 0)) == BLUE  # tie: the later


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
    assert [a.get("fallback") for a in r.audit] == [None, None, True]  # a tie keeps the latest draw


def test_the_character_sheet_never_uses_the_fallback(tmp_path):
    vision = judge({}, {"scene_mismatch": True})
    r = PageRenderer(CAST, FakeImages(colours("red", "green", "blue")), vision, SMALL,
                     RenderOptions(check_art=True, sheet_path=tmp_path / "sheet.png"))
    with pytest.raises(ArtCheckError, match="comic_art_rejected"):
        r.character_sheet()
    assert not (tmp_path / "sheet.png").exists()


def test_the_kept_draw_is_marked_selected_among_the_saved_rejections(tmp_path):
    import json
    vision = judge({RED: {"scene_mismatch": True, "design_mismatch": True}, GREEN: {"scene_mismatch": True},
                    BLUE: {"has_text": True}})
    r = PageRenderer(CAST, FakeImages(colours("red", "green", "blue")), vision, SMALL,
                     RenderOptions(check_art=True, rejected_dir=tmp_path / "rejected"))
    r.render_page([{"scene": "Dana at the gate"}], tmp_path / "page_02.png")
    saved = {p.stem: json.loads(p.read_text()) for p in (tmp_path / "rejected").glob("*.json")}
    assert sorted(saved) == ["panel_p1_d1", "panel_p1_d2", "panel_p1_d3"]
    assert [saved[f"panel_p1_d{d}"].get("selected") for d in (1, 2, 3)] == [None, True, None]


def test_a_failing_select_hook_never_changes_the_render():
    def boom(draw):
        raise RuntimeError("bookkeeping broke")
    images = FakeImages(colours("red", "green", "blue"))
    art = draw_checked(images, judge({c: {"scene_mismatch": True} for c in (RED, GREEN, BLUE)}), "scene", [], "2:3",
                       fallback=True, on_select=boom)
    assert art.getpixel((0, 0)) == BLUE


def test_small_background_text_is_soft_and_a_draw_carrying_it_may_be_kept():
    images = FakeImages(colours("red", "green", "blue"))
    vision = judge({RED: {"has_text": True, "text_prominent": True}, GREEN: {"has_text": True, "text_prominent": False},
                    BLUE: {"identity_mismatch": True}})
    art = draw_checked(images, vision, "scene", [], "2:3", fallback=True)
    assert art.getpixel((0, 0)) == GREEN


@pytest.mark.parametrize("prominent", [True, None])
def test_prominent_or_unrated_text_stays_a_hard_defect(prominent):
    images = FakeImages(colours("red", "green", "blue"))
    text = {"has_text": True, "text_prominent": prominent}
    with pytest.raises(ArtCheckError, match="comic_art_rejected"):
        draw_checked(images, judge({RED: text, GREEN: text, BLUE: text}), "scene", [], "2:3", fallback=True)


def test_background_text_is_still_redrawn_before_any_fallback():
    images = FakeImages(colours("red", "green"))
    art = draw_checked(images, judge({RED: {"has_text": True, "text_prominent": False}}), "scene", [], "2:3", fallback=True)
    assert art.getpixel((0, 0)) == GREEN and len(images.calls) == 2


def test_the_check_asks_for_text_prominence_and_allows_dial_numerals():
    from book_comic.art_check import inspect_art, require_checked
    vision = FakeVision(lambda p, i: {**BASE, "head_top": 400, "text_prominent": False})
    found = inspect_art(Image.new("RGB", (10, 10)), vision)
    assert found["text_prominent"] is False and require_checked(found) is True
    assert "text_prominent" in vision.prompts[0]
    assert "including on a map, page, document or sign the hero holds or studies" in vision.prompts[0]
    assert "hour numerals, digits, ticks and needles on a watch, clock, compass or gauge face are normal" in vision.prompts[0]
    missing = inspect_art(Image.new("RGB", (10, 10)), FakeVision(lambda p, i: {**BASE, "head_top": 400}))
    assert missing["text_prominent"] is None and require_checked(missing) is True  # prominence is optional, never "unavailable"


GLOVED = {**BASE, "design_mismatch": True, "corrections": ["Remove the black fingerless tactical gloves from both hands."]}
BARE_BRIEF = "scene ... Hands: bare skin on both hands, no gloves, fingerless gloves, mitts, wraps or straps of any kind."


def test_unasked_gloves_are_a_hard_defect_and_never_kept():
    from book_comic.best_draw import hard_defect, unasked_gloves
    assert unasked_gloves(GLOVED, BARE_BRIEF)
    assert hard_defect({**GLOVED, "gloves": True})
    # a story whose hero wears gloves never gets the bare-hands line, so gloves there are not a hard defect
    assert not unasked_gloves(GLOVED, "scene ... Hero: red coat and leather gloves")
    assert not unasked_gloves({**BASE, "corrections": ["Remove the gloves."]}, BARE_BRIEF)  # no failed check


def test_a_panel_whose_only_soft_draw_has_gloves_keeps_another_draw():
    images = FakeImages(colours("red", "green", "blue"))
    vision = judge({RED: {"design_mismatch": True, "corrections": ["Remove the fingerless gloves."]},
                    GREEN: {"scene_mismatch": True, "design_mismatch": True},
                    BLUE: {"design_mismatch": True, "corrections": ["Remove the tactical gloves."]}})
    art = draw_checked(images, vision, BARE_BRIEF, [], "2:3", fallback=True)
    assert art.getpixel((0, 0)) == GREEN  # more failed checks, but no gloves


def test_gloves_on_every_draw_fail_the_panel():
    images = FakeImages(colours("red", "green", "blue"))
    gloves = {"design_mismatch": True, "corrections": ["Remove the fingerless gloves."]}
    with pytest.raises(ArtCheckError):
        draw_checked(images, judge({c: gloves for c in (RED, GREEN, BLUE)}), BARE_BRIEF, [], "2:3", fallback=True)
