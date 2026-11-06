"""Every image prompt ends wordless whatever the scene asks, and a has_text rejection says what writing it saw.

Production: a back cover asking for "a small white card lying face up with a black mirrored symbol" drew an
aleph-like glyph, was rejected for has_text, and its reason read "no observation returned for: has_text".
"""

import pytest
from PIL import Image

from book_comic.art_check import TEXT_SEEN_CHARS, inspect_art, require_checked
from book_comic.comic_rules import NO_TEXT_RULE, WORDLESS_OVERRIDE
from book_comic.image_prompts import back_cover_prompt, cover_prompt, panel_prompt, sheet_prompt
from book_comic.rejected_art import failure_reasons
from conftest import FakeVision

CAST = {"style": "ink comic", "characters": [{"name_en": "Hero", "look": "teal blazer"}]}
CARD = "a small white card lying face up with a black mirrored symbol"
SCENE = f"Medium shot: Hero kneels by {CARD}."


def _prompts():
    return {
        "panel": panel_prompt(CAST, {"scene": SCENE}, "Hero: teal blazer"),
        "splash": panel_prompt(CAST, {"scene": SCENE}, "Hero: teal blazer", splash=True),
        "cover": cover_prompt(CAST, {"scene": f"Hero holds {CARD}"}),
        "back_cover": back_cover_prompt(CAST, {"scene": f"An empty alley at night, {CARD} on the wet ground"}, (1000, 1500)),
    }


def test_the_override_is_part_of_the_one_no_text_rule():
    assert NO_TEXT_RULE.startswith("Wordless picture: " + WORDLESS_OVERRIDE)
    assert WORDLESS_OVERRIDE.startswith("Whatever the scene says, nothing in the picture carries letters, numbers, symbols")
    assert "simple icons" not in NO_TEXT_RULE  # an icon is a symbol: no line asks for one any more


@pytest.mark.parametrize("kind", ["panel", "splash", "cover", "back_cover"])
def test_every_prompt_kind_carries_the_rule_once_after_the_scene(kind):
    prompt = _prompts()[kind]
    assert prompt.count(WORDLESS_OVERRIDE) == 1
    assert prompt.rindex("black mirrored symbol") < prompt.index(WORDLESS_OVERRIDE)


def test_the_character_sheet_carries_it_too():
    assert WORDLESS_OVERRIDE in sheet_prompt(CAST, CAST["characters"][0])


def _inspect(answer, **kwargs):
    vision = FakeVision(lambda p, i: answer)
    found = inspect_art(Image.new("RGB", (40, 60)), vision, **kwargs)
    return found, vision.prompts[0]


def test_the_check_asks_for_text_seen_and_keeps_it_short():
    found, prompt = _inspect({"has_text": True, "bad_anatomy": False, "figure_visible": False, "text_prominent": True,
                              "text_seen": "  letter-like glyph\n on the card " + "x" * 200}, setting=True)
    assert "text_seen" in prompt.split("Return JSON with exactly these fields: ", 1)[1]
    assert found["text_seen"].startswith("letter-like glyph on the card ") and len(found["text_seen"]) == TEXT_SEEN_CHARS
    assert require_checked(found) is False  # the string is not a check flag; has_text still rejects


@pytest.mark.parametrize("answer", [
    {"has_text": False, "bad_anatomy": False, "text_seen": "a card"},  # no writing: nothing to describe
    {"has_text": True, "bad_anatomy": False, "text_seen": "   "},
    {"has_text": True, "bad_anatomy": False, "text_seen": 7},
    {"has_text": True, "bad_anatomy": False},
])
def test_text_seen_is_none_without_a_usable_description(answer):
    found, _ = _inspect(answer)
    assert found["text_seen"] is None


def test_require_checked_ignores_text_seen_on_a_clean_draw():
    found, _ = _inspect({"has_text": False, "bad_anatomy": False, "figure_visible": False}, setting=True)
    assert found["text_seen"] is None and require_checked(found) is True
    assert require_checked({**found, "text_seen": "faint marks on a sign"}) is True


def test_the_rejection_reason_is_what_the_check_saw():
    found = {"has_text": True, "text_seen": "letter-like glyph on the card", "corrections": []}
    assert failure_reasons(found) == ["letter-like glyph on the card"]


def test_text_seen_is_not_a_reason_when_has_text_did_not_fail():
    found = {"has_text": False, "faint_text": True, "scene_mismatch": True, "text_seen": "tiny marks on a sign", "corrections": []}
    assert failure_reasons(found) == ["no observation returned for: scene_mismatch"]
