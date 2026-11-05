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


def test_faint_background_text_is_kept_without_a_redraw():
    """Tiny illegible glyphs on a distant sign are not what a reader notices (18 of 182 corrections, 2026-11-05)."""
    images = FakeImages(colours("red", "green"))
    art = draw_checked(images, judge({RED: {"has_text": True, "text_prominent": False}}), "scene", [], "2:3", fallback=True)
    assert art.getpixel((0, 0)) == RED and len(images.calls) == 1
    assert art.info["comic_verification"]["faint_text"] is True and art.info["comic_verification"]["has_text"] is False


def test_a_panel_seam_is_cut_off_locally_before_the_check(noise):
    from book_comic.seam import find_seam
    art = noise((400, 600))
    art.paste((170, 172, 172), (0, 40, 400, 46))  # a strip across the top, within STRIP of the height
    assert find_seam(art) == 46
    seen = []
    images = FakeImages([art])
    kept = draw_checked(images, FakeVision(lambda p, i: seen.append(i) or {**BASE, "head_top": 400}), "scene", [], "2:3", size=(400, 600))
    assert len(images.calls) == 1 and kept.size == (400, 600)
    assert find_seam(seen[0]) is None and find_seam(kept) is None


def test_the_check_judges_props_people_and_garments_as_a_reader_would():
    from book_comic.art_check import inspect_art
    vision = FakeVision(lambda p, i: {**BASE, "head_top": 400})
    inspect_art(Image.new("RGB", (10, 10)), vision, context="brief", props=[{"name": "the lantern", "look": "brass lantern"}])
    prompt = vision.prompts[0]
    assert "A prop matches when a reader would recognise it as the listed prop" in prompt
    assert "a distant, faceless background figure or silhouette alone is not a mismatch" in prompt
    assert "never sleeve length, fit, folds, trim or shade" in prompt


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


def test_the_second_draw_revises_the_first_and_the_third_rerolls():
    """Draw 2 edits the rejected draw 1 (sent as the last reference, with only the corrections); draw 3 starts fresh."""
    from book_comic.revise import REVISE_MARK
    images = FakeImages(colours("red", "green", "blue"))
    vision = judge({RED: {"design_mismatch": True, "corrections": ["Remove the gloves"]}, GREEN: {"scene_mismatch": True}})
    art = draw_checked(images, vision, "scene brief", ["data:photo", "data:sheet"], "2:3", fallback=True)
    assert art.getpixel((0, 0)) == BLUE and len(images.calls) == 3
    first, second, third = images.calls
    assert first["references"] == ["data:photo", "data:sheet"] and REVISE_MARK not in first["prompt"]
    assert second["prompt"].startswith(REVISE_MARK) and "Remove the gloves" in second["prompt"] and "scene brief" in second["prompt"]
    assert second["references"][:2] == ["data:photo", "data:sheet"] and second["references"][2].startswith("data:image/jpeg;base64,")
    assert third["references"] == ["data:photo", "data:sheet"] and REVISE_MARK not in third["prompt"]


def test_a_revision_that_fixes_the_draw_is_accepted_and_marked():
    images = FakeImages(colours("red", "green"))
    audit = []
    art = draw_checked(images, judge({RED: {"has_text": True, "text_prominent": True}}), "scene", [], "2:3", audit=audit)
    assert art.getpixel((0, 0)) == GREEN and len(images.calls) == 2
    assert audit[0].get("revised") is None and audit[1]["revised"] is True and audit[1]["accepted"] is True
    assert "no letters, words, numbers or glyphs anywhere" in images.calls[1]["prompt"]


def test_only_a_strip_across_the_top_is_cut_off(noise):
    """A flat line lower down looks like a floor or table edge to a pixel scan (review 2026-11-05): left to the check."""
    from book_comic.seam import cut_seam, seam_band
    bottom = noise((400, 600))
    bottom.paste((170, 172, 172), (0, 500, 400, 505))
    assert seam_band(bottom) is None and cut_seam(bottom, (400, 600)) is None
    top = noise((400, 600))
    top.paste((170, 172, 172), (0, 60, 400, 65))
    assert seam_band(top) == (60, 65) and cut_seam(top, (400, 600)).size == (400, 600)

def test_the_revision_carries_prop_evidence_and_never_a_framing_row():
    """Review 2026-11-05: a limb-only framing row is observed only and must not steer the revision; a wrong prop needs evidence."""
    from book_comic.art_check import inspect_art
    from book_comic.revise import revision_prompt
    requirements = [{"subject": "frame", "attribute": "framing", "expected": "hand_detail_only"}, {"subject": "book", "attribute": "state", "expected": "closed"}]
    answer = {**BASE, "head_top": 400, "design_mismatch": True,
              "requirement_checks": [{"index": 0, "observed": "body_visible", "matches": False}, {"index": 1, "observed": "open", "matches": False}],
              "prop_checks": [{"name": "the lantern", "visible": True, "observed": "a cream clock face", "matches": False}]}
    found = inspect_art(Image.new("RGB", (10, 10)), FakeVision(lambda p, i: answer), context="brief", requirements=requirements,
                        props=[{"name": "the lantern", "look": "brass lantern"}], anchors={"the lantern": "turquoise disk"})
    assert found["requirement_mismatch"] is True  # the book state, never the framing row
    prompt = revision_prompt("brief", found, (), requirements, {"the lantern": "turquoise disk"})
    assert "hand_detail_only" not in prompt.split("The original brief")[0]
    assert '"observed": "open"' in prompt and '"prop": "the lantern"' in prompt and '"canonical": "turquoise disk"' in prompt
    assert "redraw the character's face, hair, proportions and outfit" in prompt and "character exactly" not in prompt


def test_a_revision_keeps_only_what_was_not_the_defect():
    from book_comic.revise import revision_prompt
    staged = revision_prompt("brief", {**BASE, "scene_mismatch": True, "corrections": ["Turn Hero toward the city"]})
    assert "character exactly as they are" in staged and "re-stage the shot, action and facing" in staged and "Turn Hero toward the city" in staged
    assert "composition" not in staged.split("Change only")[0]
    seam_only = revision_prompt("brief", {**BASE, "scene_mismatch": True, "seam": True, "corrections": ["Remove the dividing line"]})
    assert "composition, camera, character exactly as they are" in seam_only and "re-stage" not in seam_only


def test_faint_text_is_kept_by_the_check_for_panels_and_covers_but_not_the_sheet():
    from book_comic.art_check import inspect_art, require_checked
    faint = lambda p, i: {**BASE, "head_top": 400, "has_text": True, "text_prominent": False}
    found = inspect_art(Image.new("RGB", (10, 10)), FakeVision(faint), context="cover brief")
    assert found["has_text"] is False and found["faint_text"] is True and require_checked(found, require_head=True) is True
    strict = inspect_art(Image.new("RGB", (10, 10)), FakeVision(faint), context="sheet brief", keep_faint_text=False)
    assert strict["has_text"] is True and require_checked(strict) is False
    # The character sheet path (render.character_sheet) passes strict_text: faint glyphs on it are redrawn, not kept.
    images = FakeImages(colours("red", "green"))
    art = draw_checked(images, judge({RED: {"has_text": True, "text_prominent": False}}), "sheet brief", [], "2:3", strict_text=True)
    assert art.getpixel((0, 0)) == GREEN and len(images.calls) == 2


def test_a_seam_cut_is_marked_in_the_audit_and_a_deep_line_is_not_cut(noise):
    from book_comic.seam import cut_seam
    art = noise((400, 600))
    art.paste((170, 172, 172), (0, 60, 400, 66))
    audit = []
    draw_checked(FakeImages([art]), FakeVision(lambda p, i: {**BASE, "head_top": 400}), "scene", [], "2:3", size=(400, 600), audit=audit)
    assert audit[0]["seam_cut"] is True and audit[0]["accepted"] is True
    deep = noise((400, 600))
    deep.paste((170, 172, 172), (0, 200, 400, 206))  # a third of the way down: a floor or table edge, left alone
    assert cut_seam(deep, (400, 600)) is None


def test_the_fresh_third_draw_is_told_about_every_rejected_draw():
    """Review 2026-11-05: a revision can fix one defect and lose another; draw 3 carries both."""
    from book_comic.comic_rules import ANATOMY_RULE, NO_TEXT_RULE
    images = FakeImages(colours("red", "green", "blue"))
    vision = judge({RED: {"has_text": True, "text_prominent": True}, GREEN: {"bad_anatomy": True}})
    art = draw_checked(images, vision, "scene", [], "2:3", fallback=True)
    third = images.calls[2]["prompt"]
    assert art.getpixel((0, 0)) == BLUE and NO_TEXT_RULE.strip() in third and ANATOMY_RULE.strip() in third


def test_cover_scene_drops_a_limb_only_clause_with_the_shot():
    from book_comic.comic_rules import cover_scene
    assert cover_scene("Extreme long shot: Hero on a rooftop, only his hands visible, holding a relic.") == "Hero on a rooftop, holding a relic."
    assert cover_scene("Hero kneels by the relic, her boot at the edge of the frame; rain falls.") == "Hero kneels by the relic, rain falls."
    assert cover_scene("Hero stands on the pier at dawn.") == "Hero stands on the pier at dawn."


def test_a_contradiction_waved_through_with_matches_true_still_reaches_the_revision():
    """Third review 2026-11-05: the check rejects a wrong hand side even when the model says matches=true; the revision must hear it."""
    from book_comic.art_check import inspect_art
    from book_comic.revise import failed_requirements, revision_prompt
    requirements = [{"subject": "Hero", "attribute": "hand", "expected": "right"}]
    answer = {**BASE, "head_top": 400, "requirement_checks": [{"index": 0, "observed": "left", "matches": True}]}
    found = inspect_art(Image.new("RGB", (10, 10)), FakeVision(lambda p, i: answer), context="brief", requirements=requirements)
    assert found["requirement_mismatch"] is True
    assert failed_requirements(found, requirements) == [{"required": requirements[0], "observed": "left"}]
    assert '"observed": "left"' in revision_prompt("brief", found, (), requirements)


def test_a_draw_rejected_for_paper_margins_gets_a_fresh_roll_not_a_revision(monkeypatch):
    import book_comic.art_check as art_check
    from book_comic.revise import REVISE_MARK
    calls = []
    def margins(art, aspect):
        calls.append(1)
        return art, "redraw" if len(calls) == 1 else None
    monkeypatch.setattr(art_check, "trim_margins", margins)
    images = FakeImages(colours("red", "green"))
    art = draw_checked(images, judge({}), "scene", [], "2:3", size=(400, 600))
    assert art.getpixel((0, 0)) == GREEN and len(images.calls) == 2
    from book_comic.margins import MARGIN_CORRECTION
    assert REVISE_MARK not in images.calls[1]["prompt"] and MARGIN_CORRECTION in images.calls[1]["prompt"]


def test_cover_scene_spares_the_sentences_around_a_limb_clause():
    from book_comic.comic_rules import cover_scene
    assert cover_scene("Hero on a rooftop. Only his hands visible, holding a relic.") == "Hero on a rooftop. Holding a relic."
    direction = " Expression and body language: tense, the face when visible shows fear."
    assert cover_scene("Extreme long shot: Hero on a rainy rooftop holding the relic, only his hands visible." + direction) == \
        "Hero on a rainy rooftop holding the relic." + direction


def test_a_pose_waved_through_with_matches_true_reaches_the_revision():
    from book_comic.revise import failed_requirements
    from book_comic.rejected_art import unmet_requirements
    requirements = [{"subject": "Hero", "attribute": "pose", "expected": "kneeling"}, {"subject": "book", "attribute": "state", "expected": "open"}]
    found = {"requirement_checks": [{"index": 0, "observed": "standing", "matches": True}, {"index": 1, "observed": "closed", "matches": False}]}
    assert [check["observed"] for check, _ in unmet_requirements(found, requirements)] == ["standing", "closed"]
    assert [row["required"]["attribute"] for row in failed_requirements(found, requirements)] == ["pose", "state"]
    free_text = {"requirement_checks": [{"index": 0, "observed": "kneeling on one knee", "matches": True}]}
    assert unmet_requirements(free_text, requirements) == []  # free text with matches=true is not a contradiction, anywhere


def test_the_back_cover_keeps_faint_glyphs_like_any_cover():
    from book_comic.art_check import inspect_art, require_checked
    found = inspect_art(Image.new("RGB", (10, 10)), FakeVision(lambda p, i: {**BASE, "head_top": 400, "has_text": True, "text_prominent": False, "figure_visible": False}), setting=True)
    assert found["faint_text"] is True and require_checked(found) is True


def test_cover_scene_opens_with_a_capital_and_never_degenerates():
    from book_comic.comic_rules import cover_scene
    assert cover_scene("Only his hands visible, gripping the ledge. Hero on a rooftop.") == "Gripping the ledge. Hero on a rooftop."
    assert cover_scene("Hero waits. Expression and body language: only his hands visible.") == "Hero waits."  # the whole limb clause goes
    degenerate = "Extreme long shot: ; only his hands visible."
    assert cover_scene(degenerate) == "; only his hands visible."  # nothing but punctuation would be left: the scene as written


def test_the_check_and_the_fallback_ranking_use_the_same_unmet_row_rule():
    """Fifth review 2026-11-05: free text for a literal state no longer rejects; the ranking counts the shared rule."""
    from book_comic.art_check import inspect_art
    requirements = [{"subject": "Hero", "attribute": "pose", "expected": "kneeling"}]
    answer = {**BASE, "head_top": 400, "requirement_checks": [{"index": 0, "observed": "kneeling on one knee", "matches": True}]}
    found = inspect_art(Image.new("RGB", (10, 10)), FakeVision(lambda p, i: answer), context="brief", requirements=requirements)
    assert found["requirement_mismatch"] is False
    hidden_design = {**BASE, "scene_mismatch": True, "requirement_checks": [{"index": 0, "observed": "not_visible", "matches": False}]}
    wrong_hand = {**BASE, "scene_mismatch": True, "requirement_checks": [{"index": 0, "observed": "left", "matches": True}]}
    design_req = [{"subject": "Hero", "attribute": "design", "expected": "teal blazer"}]
    hand_req = [{"subject": "Hero", "attribute": "hand", "expected": "right"}]
    assert pick_fallback([(None, hidden_design), (None, {**BASE, "scene_mismatch": True})], design_req) == 1  # tie: the later draw
    assert pick_fallback([(None, {**BASE, "scene_mismatch": True}), (None, wrong_hand)], hand_req) == 0  # the real contradiction loses
