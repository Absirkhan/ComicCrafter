"""The art check is no stricter than a reader: a scene object's own marking, a state too far away to see, a slightly
different grip (book_comic.check_tolerance). The vision model's reading of the prompt is not tested here (no live calls)."""

import pytest
from PIL import Image

from book_comic.art_check import draw_checked, inspect_art, require_checked
from book_comic.best_draw import hard_defect, pick_fallback
from book_comic.check_tolerance import CONTACT_NOTE, HIDDEN_NOTE, HOLD_NOTE, SCENE_MARKING_NOTE
from book_comic.rejected_art import failure_reasons, requirement_failed, unmet_requirements
from book_comic.revise import failed_requirements
from conftest import FakeImages, FakeVision

BASE = {"has_text": False, "bad_anatomy": False, "identity_mismatch": False, "design_mismatch": False, "scene_mismatch": False}
HELIPAD = {**BASE, "head_top": 400, "has_text": True, "text_prominent": True, "text_marking": True, "text_seen": "letter 'H' on helipad"}
DOOR = [{"subject": "the door", "attribute": "state", "expected": "closed"}]


def _inspect(answer, **kwargs):
    vision = FakeVision(lambda p, i: dict(answer))
    return inspect_art(Image.new("RGB", (40, 60)), vision, **kwargs), vision.prompts[0]


# Case 1: one conventional marking that is part of a scene object is not drawn text (BOOKS-44 page 18).

def test_a_helipad_h_is_a_scene_marking_not_drawn_text():
    found, prompt = _inspect(HELIPAD, context="Extreme long shot: a hospital rooftop.")
    assert found["has_text"] is False and found["scene_marking"] is True and require_checked(found) is True
    assert hard_defect(found) is False and failure_reasons(found) == []
    assert SCENE_MARKING_NOTE in prompt and "text_marking" in prompt.split("Return JSON with exactly these fields: ", 1)[1]


def test_a_panel_with_only_a_helipad_h_is_accepted_on_the_first_draw():
    images, audit = FakeImages([Image.new("RGB", (10, 10), "red")]), []
    art = draw_checked(images, FakeVision(lambda p, i: dict(HELIPAD)), "Extreme long shot: a hospital rooftop.", [], "2:3", audit=audit)
    assert len(images.calls) == 1 and audit[0]["accepted"] is True
    assert art.info["comic_verification"]["scene_marking"] is True


@pytest.mark.parametrize("answer", [
    {"text_marking": False, "text_seen": "GENERATOR ROOM on a door"},           # a readable word: the checker says so
    {"text_marking": True, "text_seen": "'GENERATOR ROOM' on the door"},        # the flag contradicts its own description
    {"text_marking": True, "text_seen": "door sign with writing"},
    {"text_marking": True, "text_seen": "carved glyphs on floor tiles"},
    {"text_marking": True, "text_seen": "letter-like glyph on the card"},
    {"text_marking": True, "text_seen": "runes along the wall"},
    {"text_marking": True, "text_seen": "watermark in the corner"},
    {"text_marking": True, "text_seen": "logo with letters on the van"},
    {"text_marking": True, "text_seen": "empty speech bubble"},
    {"text_marking": "true", "text_seen": "letter 'H' on helipad"},             # not a boolean: not trusted
    {"text_seen": "letter 'H' on helipad"},                                     # no flag returned: as before
])
def test_words_signs_glyphs_logos_and_watermarks_still_fail(answer):
    found, _ = _inspect({**BASE, "head_top": 400, "has_text": True, "text_prominent": True, **answer}, context="brief")
    assert found["has_text"] is True and "scene_marking" not in found
    assert require_checked(found) is False and hard_defect(found) is True  # never kept by the best-of-three fallback


def test_three_draws_with_a_readable_word_are_still_rejected():
    word = {**BASE, "head_top": 400, "has_text": True, "text_prominent": True, "text_marking": False, "text_seen": "GENERATOR ROOM on a door"}
    images = FakeImages([Image.new("RGB", (10, 10), "red")])
    with pytest.raises(ValueError, match="comic_art_rejected"):
        draw_checked(images, FakeVision(lambda p, i: dict(word)), "scene", [], "2:3", fallback=True)
    assert len(images.calls) == 3


def test_the_character_sheet_stays_strict_about_a_scene_marking():
    found, _ = _inspect(HELIPAD, context="sheet brief", keep_faint_text=False)
    assert found["has_text"] is True and require_checked(found) is False


def test_a_marking_flag_without_has_text_changes_nothing():
    found, _ = _inspect({**BASE, "head_top": 400, "text_marking": True})
    assert found["has_text"] is False and "scene_marking" not in found


# Case 2: a state the checker cannot see is not a wrong state (BOOKS-44 page 1, an extreme long shot).

@pytest.mark.parametrize("attribute,expected", [("state", "closed"), ("pose", "kneeling"), ("hand", "right"),
                                                ("contact", "hand on the railing"), ("design", "brass trim")])
@pytest.mark.parametrize("observed", ["not_visible", "not visible", " Not_Visible "])
@pytest.mark.parametrize("matches", [False, True])
def test_a_requirement_the_checker_cannot_see_does_not_fail(attribute, expected, observed, matches):
    requirement = {"subject": "the door", "attribute": attribute, "expected": expected}
    check = {"index": 0, "observed": observed, "matches": matches}
    assert requirement_failed(check, requirement) is False
    found, _ = _inspect({**BASE, "requirement_checks": [check]}, requirements=[requirement])
    assert found["requirement_mismatch"] is False and require_checked(found) is True
    assert unmet_requirements(found, [requirement]) == [] and failed_requirements(found, [requirement]) == []


@pytest.mark.parametrize("attribute,expected,observed,matches", [
    ("state", "closed", "open", False),
    ("state", "closed", "open", True),                          # a literal contradiction waved through
    ("state", "closed", "the door stands wide open", False),    # free text, the checker's verdict
    ("state", "closed", "no door in the picture", False),       # a missing object is not "not visible"
    ("pose", "kneeling", "standing", True),
    ("hand", "right", "left", True),
    ("hand", "right", "ambiguous", True),
    ("direction", "walking left", "walking right", False),
])
def test_a_visibly_wrong_state_still_fails(attribute, expected, observed, matches):
    requirement = {"subject": "the door", "attribute": attribute, "expected": expected}
    check = {"index": 0, "observed": observed, "matches": matches}
    assert requirement_failed(check, requirement) is True
    found, _ = _inspect({**BASE, "requirement_checks": [check]}, requirements=[requirement])
    assert found["requirement_mismatch"] is True and require_checked(found) is False
    assert len(unmet_requirements(found, [requirement])) == 1


def test_an_extreme_long_shot_with_a_hidden_door_state_is_accepted_on_the_first_draw():
    hidden = {**BASE, "head_top": 400, "requirement_checks": [{"index": 0, "observed": "not_visible", "matches": False}]}
    images = FakeImages([Image.new("RGB", (10, 10), "red")])
    draw_checked(images, FakeVision(lambda p, i: dict(hidden)), "Extreme long shot: Hero crosses the yard.", [], "3:2", requirements=DOOR)
    assert len(images.calls) == 1


def test_a_visibly_open_door_is_redrawn_and_the_redraw_names_it():
    def answer(prompt, image):
        wrong = image.getpixel((0, 0)) == (255, 0, 0)
        return {**BASE, "head_top": 400, "requirement_checks": [{"index": 0, "observed": "open" if wrong else "closed", "matches": not wrong}]}
    images = FakeImages([Image.new("RGB", (10, 10), c) for c in ("red", "blue")])
    draw_checked(images, FakeVision(answer), "Wide shot: Hero by the door.", [], "3:2", requirements=DOOR)
    assert len(images.calls) == 2 and '"observed": "open"' in images.calls[1]["prompt"]


def test_a_hidden_row_does_not_count_against_a_draw_in_the_fallback_ranking():
    hidden = {**BASE, "scene_mismatch": True, "requirement_checks": [{"index": 0, "observed": "not_visible", "matches": False}]}
    wrong = {**BASE, "scene_mismatch": True, "requirement_checks": [{"index": 0, "observed": "open", "matches": False}]}
    assert pick_fallback([(None, hidden), (None, wrong)], DOOR) == 0  # the later draw would win a tie: this is not one


# Case 3: the grip or exact position of a correctly held object is wording for the checker; the verdict rule is unchanged.

def test_the_prompt_judges_the_action_not_the_grip_and_keeps_the_strict_checks():
    contact = [{"subject": "the notebook", "attribute": "contact", "expected": "pressed flat against the chest"}]
    _, prompt = _inspect({**BASE}, context="Close-up: Hero holds the notebook.", requirements=contact)
    assert HOLD_NOTE in prompt and CONTACT_NOTE in prompt and HIDDEN_NOTE in prompt
    assert "facing or gaze direction differs" in HOLD_NOTE and "the object or the person is a different one" in CONTACT_NOTE
    # What stays strict is still asked for, word for word.
    for strict in ("more than two arms or more than two hands, a hand with more than five fingers",
                   "identity_mismatch (different face, age, hair, facial hair or head/body proportions)",
                   "a different garment or hairstyle, a missing or added major garment, gloves",
                   "wrong planned shot, expression, focal action, movement direction, essential object state",
                   "A visible seam, border or dividing line that splits the picture into two images is a scene_mismatch"):
        assert strict in prompt
    _, plain = _inspect({**BASE})  # no brief: nothing to compare the action with
    assert HOLD_NOTE not in plain and CONTACT_NOTE not in plain


@pytest.mark.parametrize("flag", ["bad_anatomy", "identity_mismatch", "design_mismatch", "scene_mismatch"])
def test_a_scene_marking_or_a_hidden_state_never_hides_another_defect(flag):
    answer = {**HELIPAD, flag: True, "requirement_checks": [{"index": 0, "observed": "not_visible", "matches": False}]}
    found, _ = _inspect(answer, context="brief", requirements=DOOR)
    assert found[flag] is True and require_checked(found) is False


def test_a_contact_row_the_checker_calls_unmet_still_fails():
    contact = [{"subject": "the notebook", "attribute": "contact", "expected": "pressed flat against the chest"}]
    found, _ = _inspect({**BASE, "requirement_checks": [{"index": 0, "observed": "the notebook lies on the table", "matches": False}]},
                        context="brief", requirements=contact)
    assert found["requirement_mismatch"] is True
