"""Grip, a wide shot cut at the knees, marks on a held map and movement direction are advisory; a squashed figure is a
defect (book_comic.staging_tolerance, check_tolerance). The checker strings are the real ones of a live 20-page comic
(2026-11-12). The vision model's reading of the prompt is not tested here (no live calls)."""

import pytest
from PIL import Image

from book_comic.art_check import draw_checked, inspect_art, require_checked
from book_comic.best_draw import hard_defect, pick_fallback
from book_comic.check_tolerance import CONTACT_NOTE, HOLD_NOTE, MARKS_ROW_NOTE, PROP_MARKS_NOTE, marks_only_row
from book_comic.comic_rules import PROPORTION_RULE
from book_comic.framing import SHOT_FRAMING
from book_comic.image_prompts import canvas_shape
from book_comic.lettering_space import CHECK_NOTE
from book_comic.preflight import REVIEW_PROMPT
from book_comic.rejected_art import failed_checks, requirement_failed
from book_comic.staging_tolerance import BODY_NOTE, DIRECTION_NOTE, fresh_redraw, still_held
from conftest import FakeImages, FakeVision

BASE = {"has_text": False, "bad_anatomy": False, "identity_mismatch": False, "design_mismatch": False, "scene_mismatch": False}
WIDE = SHOT_FRAMING["Wide shot"] + "\nWide shot: Hero stands in the old square, the city map in her hands."
GRIP_FIX = "Hold the map open with both hands pressed against the chest instead of holding it out in one hand"
FEET_FIXES = ["Frame as a wide shot with the entire body visible from head to feet",
              "Frame as a wide shot showing the entire body from head to feet with ground visible below the boots"]
MAP = [{"subject": "city map", "attribute": "contact", "expected": "gripped tightly against her chest"}]
MAP_PROP = [{"name": "city map", "look": "a folded paper map with blue lines and coloured zones"}]


def _inspect(answer, **kwargs):
    vision = FakeVision(lambda p, i: dict(answer))
    return inspect_art(Image.new("RGB", (40, 60)), vision, **kwargs), vision.prompts[0]


def _colours(*names):
    return [Image.new("RGB", (10, 10), n) for n in names]


# A. The grip, the number of hands, which hand and where a held object is held.

@pytest.mark.parametrize("expected,observed", [
    ("gripped tightly against her chest", "held in left hand at side, right hand on chest"),
    ("pressed against the chest", "held outward in front of torso rather than pressed against chest"),
    ("held open with both hands", "held open in one hand, the other hand at her side"),
])
def test_a_held_object_passes_its_contact_row_whatever_the_grip(expected, observed):
    row = {"subject": "city map", "attribute": "contact", "expected": expected}
    assert still_held(observed, expected) and requirement_failed({"index": 0, "observed": observed, "matches": False}, row) is False
    found, _ = _inspect({**BASE, "requirement_checks": [{"index": 0, "observed": observed, "matches": False}]}, context="brief", requirements=[row])
    assert found["requirement_mismatch"] is False and require_checked(found) is True


@pytest.mark.parametrize("expected,observed", [
    ("gripped tightly against her chest", "no map in the picture"),
    ("gripped tightly against her chest", "the map lies on the ground beside her"),
    ("gripped tightly against her chest", "the map is dropped, her hands are empty"),
    ("gripped tightly against her chest", "held by the robot companion"),
    ("gripped tightly against her chest", "she is holding a different object, a notebook"),
    ("gripped tightly against her chest", "map not held, tucked in her bag"),
    ("hand on the railing", "holding the map in both hands"),            # not a hold: the checker's verdict stands
])
def test_an_absent_dropped_or_someone_elses_object_still_fails(expected, observed):
    row = {"subject": "city map", "attribute": "contact", "expected": expected}
    assert requirement_failed({"index": 0, "observed": observed, "matches": False}, row) is True


@pytest.mark.parametrize("attribute", ["state", "pose", "direction", "design", "hand"])
def test_a_grip_never_excuses_another_kind_of_row(attribute):
    row = {"subject": "city map", "attribute": attribute, "expected": "held open"}
    assert requirement_failed({"index": 0, "observed": "held in left hand at side", "matches": False}, row) is True


def test_a_scene_mismatch_over_the_grip_alone_is_advisory():
    found, prompt = _inspect({**BASE, "head_top": 300, "scene_mismatch": True, "corrections": [GRIP_FIX]}, context="Medium shot: Hero holds the map.")
    assert found["scene_mismatch"] is False and found["staging_advisory"] is True and require_checked(found) is True
    assert "one hand or two, which hand" in HOLD_NOTE and "held by someone else, is still wrong" in HOLD_NOTE
    assert "held by someone else, does not match" in CONTACT_NOTE and HOLD_NOTE in prompt
    assert "do not turn the\ngrip, the number of hands, which hand or where it is held into a requirement" in REVIEW_PROMPT
    assert "Never relax these" in REVIEW_PROMPT


@pytest.mark.parametrize("corrections", [
    [],                                                                     # a mismatch the checker did not explain
    [GRIP_FIX, "Change the expression to worried"],
    [GRIP_FIX, "Remove the second person standing next to Hero"],
    ["Hold the map in both hands instead of leaving it on the ground"],     # it was not held
    ["Hold the map instead of holding the compass"],                        # another object was held
    ["Show Hero unfolding the map instead of walking"],                     # the focal action
    ["Hold the map and turn Hero to face the tower instead of holding it toward the camera"],
])
def test_any_other_correction_keeps_the_scene_mismatch(corrections):
    found, _ = _inspect({**BASE, "head_top": 300, "scene_mismatch": True, "corrections": corrections}, context="Medium shot: Hero holds the map.")
    assert found["scene_mismatch"] is True and require_checked(found) is False


# B and F1. A wide shot cut at the shins or knees is a wide shot; a cropped head or a close-up is not.

@pytest.mark.parametrize("correction", FEET_FIXES)
@pytest.mark.parametrize("shown", ["knees", "shins", "feet"])
def test_a_wide_shot_cut_at_the_knees_or_lower_is_accepted_on_the_first_draw(correction, shown):
    answer = {**BASE, "head_top": 180, "scene_mismatch": True, "body_shown": shown, "corrections": [correction]}
    images, audit = FakeImages(_colours("red", "blue")), []
    draw_checked(images, FakeVision(lambda p, i: dict(answer)), WIDE, [], "2:1", audit=audit)
    assert len(images.calls) == 1 and audit[0]["accepted"] is True  # no revision, so nothing squeezes the figure
    assert audit[0]["checks"]["staging_advisory"] is True


@pytest.mark.parametrize("change", [
    {"body_shown": "thighs"}, {"body_shown": "waist"}, {"body_shown": "chest"}, {"body_shown": "face"},  # a closer shot
    {"body_shown": None}, {"body_shown": "none"},                                                           # no signal
    {"head_top": 0}, {"head_top": None},                                                                    # head cropped or unknown
    {"corrections": [FEET_FIXES[0], "The top of the head is cut off"]},
    {"corrections": ["Pull back from the close-up so the entire body is visible"]},
    {"corrections": [FEET_FIXES[0], "Turn Hero to face the fountain"]},
])
def test_a_cropped_head_or_a_closer_shot_still_fails_a_wide_shot(change):
    answer = {**BASE, "head_top": 180, "scene_mismatch": True, "body_shown": "knees", "corrections": [FEET_FIXES[1]], **change}
    found, _ = _inspect(answer, context=WIDE)
    assert found["scene_mismatch"] is True and "staging_advisory" not in found


def test_the_knee_crop_counts_only_in_a_wide_shot_brief():
    answer = {**BASE, "head_top": 180, "scene_mismatch": True, "body_shown": "knees", "corrections": [FEET_FIXES[1]]}
    found, _ = _inspect(answer, context=SHOT_FRAMING["Extreme long shot"] + "\nExtreme long shot: Hero crosses the square.")
    assert found["scene_mismatch"] is True
    assert "the whole head is visible and the body is visible down to at least the knees" in CHECK_NOTE
    assert "a wide shot is wrong when the head is cropped" in CHECK_NOTE and "head and the feet are both visible" not in CHECK_NOTE
    assert "from the top of the head to the feet" in SHOT_FRAMING["Wide shot"]  # the draw prompt still asks for the feet


# C. Marks on a map, page or screen the hero holds or uses are not text, unless they form a real word.

@pytest.mark.parametrize("seen", ["pseudo-lettering in legend boxes", "pseudo-lettering lines on map",
                                  "contains pseudo-lettering 'PPI2' in a yellow zone", "tiny glyph-like marks on the map", None])
def test_marks_on_the_held_map_are_not_drawn_text(seen):
    answer = {**BASE, "head_top": 400, "has_text": True, "text_prominent": True, "text_on_prop": True, "text_seen": seen}
    found, prompt = _inspect(answer, context="Medium shot: Hero studies the city map.")
    assert found["has_text"] is False and found["prop_marking"] is True and require_checked(found) is True
    assert hard_defect(found) is False and failed_checks(found) == []
    assert PROP_MARKS_NOTE in prompt and "text_on_prop" in prompt.split("Return JSON with exactly these fields: ", 1)[1]


@pytest.mark.parametrize("answer", [
    {"text_on_prop": False, "text_seen": "pseudo-lettering lines on map"},       # the checker does not say it is only the prop
    {"text_seen": "pseudo-lettering lines on map"},                              # no flag: as before
    {"text_on_prop": "true", "text_seen": "pseudo-lettering lines on map"},      # not a boolean: not trusted
    {"text_on_prop": True, "text_seen": "'EXIT' on the map"},                    # a real word
    {"text_on_prop": True, "text_seen": "the word 'כניסה' on the page"},
    {"text_on_prop": True, "text_seen": "readable street names on the map"},
    {"text_on_prop": True, "text_seen": "pseudo-lettering on a poster on the wall"},
    {"text_on_prop": True, "text_seen": "graffiti letters behind the hero"},
    {"text_on_prop": True, "text_seen": "shop sign with garbled letters"},
    {"text_on_prop": True, "text_seen": "empty speech bubble"},
    {"text_on_prop": True, "text_seen": "watermark in the corner"},
])
def test_real_words_and_writing_off_the_prop_still_fail(answer):
    found, _ = _inspect({**BASE, "head_top": 400, "has_text": True, "text_prominent": True, **answer}, context="brief")
    assert found["has_text"] is True and "prop_marking" not in found
    assert require_checked(found) is False and hard_defect(found) is True


def test_the_character_sheet_stays_strict_about_marks_on_a_prop():
    answer = {**BASE, "head_top": 400, "has_text": True, "text_prominent": True, "text_on_prop": True, "text_seen": "pseudo-lettering lines on map"}
    found, _ = _inspect(answer, context="sheet brief", keep_faint_text=False)
    assert found["has_text"] is True and require_checked(found) is False


@pytest.mark.parametrize("observed", ["pseudo-lettering in legend boxes", "pseudo-lettering lines on map",
                                      "contains pseudo-lettering 'PPI2' in a yellow zone"])
def test_marks_on_the_map_are_not_a_changed_prop(observed):
    found, prompt = _inspect({**BASE, "prop_checks": [{"name": "city map", "visible": True, "observed": observed, "matches": False}]},
                             context="brief", props=MAP_PROP)
    assert found["prop_mismatch"] is False and require_checked(found) is True and MARKS_ROW_NOTE in prompt
    design = {"subject": "city map", "attribute": "design", "expected": "blue lines and coloured zones"}
    assert requirement_failed({"index": 0, "observed": observed, "matches": False}, design) is False


@pytest.mark.parametrize("observed", [
    "folded white/cream paper sheet without blue lines or colored zones",        # the real fair rejection
    "plain cream sheet with pseudo-lettering lines",
    "pseudo-lettering lines on a blank white sheet",
    "pseudo-lettering 'CITY' on the map",
    "a compass with letter-like marks",
])
def test_a_prop_that_changed_its_look_still_fails(observed):
    found, _ = _inspect({**BASE, "prop_checks": [{"name": "city map", "visible": True, "observed": observed, "matches": False}]},
                        context="brief", props=MAP_PROP)
    assert found["prop_mismatch"] is True and require_checked(found) is False
    assert marks_only_row("pseudo-lettering on the door", "old door") is False  # not a prop the hero reads


# E. Direction of movement and facing: wording for the checker; a direction row keeps the checker's verdict.

def test_direction_is_judged_by_the_story_beat_in_the_prompt_only():
    direction = [{"subject": "Hero", "attribute": "direction", "expected": "walking toward the old building"}]
    _, prompt = _inspect({**BASE}, context="Wide shot: Hero walks toward the old building.", requirements=direction)
    assert DIRECTION_NOTE in prompt and "movement direction" in prompt  # scene_mismatch still names it
    for phrase in ("only when it reverses the beat", "that target is not in the picture", "beside or slightly behind the hero",
                   "walks toward the camera right next to it", "When you cannot tell, judge as the brief says"):
        assert phrase in DIRECTION_NOTE
    for observed in ("walking away from the building", "the building is not in the picture", "walking toward the camera"):
        assert requirement_failed({"index": 0, "observed": observed, "matches": False}, direction[0]) is True
    turn = {**BASE, "head_top": 300, "scene_mismatch": True,
            "corrections": ["Turn Hero to face and move toward the old building rather than walking toward the camera"]}
    assert _inspect(turn, context=WIDE)[0]["scene_mismatch"] is True  # the checker's verdict is not overruled in code


# F. A wrong crop is redrawn from scratch, and a squashed figure is a defect that is never kept by default.

def test_a_wrong_crop_is_redrawn_fresh_not_revised():
    def answer(prompt, image):
        wrong = image.getpixel((0, 0)) == (255, 0, 0)
        return {**BASE, "head_top": 0 if wrong else 200, "scene_mismatch": wrong, "body_shown": "chest" if wrong else "feet",
                "corrections": [FEET_FIXES[1]] if wrong else []}
    images, audit = FakeImages(_colours("red", "blue")), []
    draw_checked(images, FakeVision(answer), WIDE, [], "2:1", audit=audit, framing=SHOT_FRAMING["Wide shot"])
    second = images.calls[1]
    assert len(images.calls) == 2 and not second["prompt"].startswith("REVISE") and "revised" not in audit[1]
    assert len(second["references"]) == 0 and "Repeat of the required framing: WIDE SHOT:" in second["prompt"]
    assert PROPORTION_RULE in second["prompt"]  # the wide-shot framing carries it


@pytest.mark.parametrize("found,fresh", [
    ({"scene_mismatch": True, "corrections": ["Pull back from the close-up to a wide shot"]}, True),
    ({"scene_mismatch": True, "corrections": ["The head is cut off at the top edge"]}, True),
    ({"squashed_figure": True}, True),
    ({"margins_redraw": True, "scene_mismatch": True}, True),
    ({"scene_mismatch": True, "seam": True, "corrections": ["Remove the border line that splits the frame"]}, False),
    ({"scene_mismatch": True, "corrections": ["Turn Hero to face the gate"]}, False),   # a facing fix is still a revision
    ({"scene_mismatch": True, "corrections": ["Scale down the figure so it fills at most two-thirds of the frame height"]}, False),
    ({"has_text": True, "corrections": ["Frame as a wide shot"]}, False),               # not a scene mismatch
    ({"design_mismatch": True}, False),
])
def test_which_rejections_start_the_next_draw_from_scratch(found, fresh):
    assert fresh_redraw(found) is fresh


def test_a_squashed_figure_is_rejected_redrawn_fresh_and_told_the_proportions():
    def answer(prompt, image):
        return {**BASE, "head_top": 200, "squashed_figure": image.getpixel((0, 0)) == (255, 0, 0)}
    images, audit = FakeImages(_colours("red", "blue")), []
    art = draw_checked(images, FakeVision(answer), "Medium shot: Hero waits.", [], "2:1", audit=audit)
    assert len(images.calls) == 2 and audit[0]["accepted"] is False and audit[0]["checks"]["squashed_figure"] is True
    assert not images.calls[1]["prompt"].startswith("REVISE") and PROPORTION_RULE in images.calls[1]["prompt"]
    assert "squashed_figure" not in art.info["comic_verification"]  # a clean draw carries no flag
    assert failed_checks(audit[0]["checks"]) == ["squashed_figure"]


def test_a_squashed_figure_loses_the_fallback_but_is_not_a_hard_defect():
    squashed, drift = {**BASE, "squashed_figure": True, "scene_mismatch": True}, {**BASE, "scene_mismatch": True}
    assert hard_defect(squashed) is False                       # three squashed draws still yield a page, not an error
    assert pick_fallback([(None, drift), (None, squashed)]) == 0  # the later draw would win a tie: this is not one
    assert pick_fallback([(None, squashed), (None, squashed)]) == 1
    _, prompt = _inspect({**BASE})
    assert BODY_NOTE in prompt and "legs clearly too short for the torso" in BODY_NOTE
    fields = prompt.split("Return JSON with exactly these fields: ", 1)[1]
    assert "squashed_figure" in fields and "body_shown" in fields
    assert "more than two arms or more than two hands" in prompt  # bad_anatomy is as it was


def test_draw_prompts_ask_for_natural_proportions_instead_of_a_figure_shortened_to_fit():
    assert SHOT_FRAMING["Wide shot"].endswith(PROPORTION_RULE)
    assert "legs about half the body height" in PROPORTION_RULE and "crop it at the knees" in PROPORTION_RULE
    assert "never compress or shorten the legs or the torso to fit the frame" in PROPORTION_RULE
    assert "never shortened or squashed to fit" in canvas_shape((1200, 500))
