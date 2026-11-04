"""Bare hands by default (fingerless gloves were the top design defect) and no rejection saved without a reason."""

from book_comic.comic_rules import bare_hands
from book_comic.image_prompts import cover_prompt, panel_prompt, sheet_prompt
from book_comic.rejected_art import failure_reasons

BARE = "Hands: bare skin on both hands, no gloves, fingerless gloves, mitts, wraps or straps of any kind."
CAST = {"style": "ink comic", "characters": [{"name_en": "Hero", "look": "teal blazer, cream tee"}]}


def test_every_panel_sheet_and_cover_asks_for_bare_hands():
    hero = CAST["characters"][0]
    assert BARE in panel_prompt(CAST, {"scene": "Medium shot: Hero reads the map."}, "Hero: teal blazer, cream tee")
    assert BARE in sheet_prompt(CAST, hero)
    assert BARE in cover_prompt(CAST, {"scene": "Hero on a rooftop at dusk"})


def test_handwear_named_by_the_look_a_prop_or_the_scene_is_respected():
    assert bare_hands("red coat and leather gloves") == ""
    assert bare_hands("teal blazer", "Close-up: Hero's gloved hand grips the rail.") == ""
    gauntlet = {**CAST, "props": [{"name": "Power Gauntlet", "look": "silver armoured forearm piece"}]}
    assert BARE not in panel_prompt(gauntlet, {"scene": "Close-up: Hero raises the Power Gauntlet."}, "Hero: teal blazer")
    # e986d71f panel 2: the gauntlet is not in this scene, so the hands stay bare (the matrix drew fingerless gloves)
    assert BARE in panel_prompt(gauntlet, {"scene": "Medium shot: Hero picks up the Neon Crystal."}, "Hero: teal blazer")


def test_role_and_prop_names_no_longer_hide_the_reason():
    found = {"design_mismatch": True, "corrections": ["Remove the fingerless glove from Hero's right hand.",
                                                      "Draw the Notebook closed."]}
    assert failure_reasons(found, names=["Dana Levi"]) == found["corrections"]


def test_a_private_name_is_still_kept_out():
    found = {"scene_mismatch": True, "corrections": ["Dana Levi faces the wrong way."]}
    assert failure_reasons(found, names=["Dana Levi"]) == ["no observation returned for: scene_mismatch"]


def test_a_failed_check_without_an_observation_still_gets_a_reason():
    assert failure_reasons({"scene_mismatch": True, "has_text": True, "corrections": []}) == [
        "no observation returned for: has_text, scene_mismatch"]
    assert failure_reasons({"scene_mismatch": False, "corrections": []}) == []


def test_a_prop_tucked_under_an_arm_is_drawn_there_not_hidden():
    prompt = panel_prompt(CAST, {"scene": "Extreme long shot: Hero on a roof, journal tucked under arm."}, "Hero: teal blazer")
    assert "A prop held, carried or tucked under an arm is visible: draw it exactly there." in prompt
