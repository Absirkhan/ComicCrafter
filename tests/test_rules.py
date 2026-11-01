"""Writer-side craft rules."""

from book_comic.comic_rules import COMIC_BUBBLE_RULE, props_rule, scene_shot, shots_problem
from layout.bubble_shapes import BUBBLE_KINDS


def panels(*scenes):
    return [{"scene": s} for s in scenes]


def test_shot_variety_rules():
    assert scene_shot("Close-up: Dana smiles") == "Close-up"
    assert scene_shot("Dana smiles") is None
    assert shots_problem(panels("Wide shot: a", "Close-up: b", "Medium shot: c")) is None
    assert shots_problem(panels("Wide shot: a", "b", "Close-up: c")) == "scene_without_shot"
    assert shots_problem(panels("Close-up: a", "Wide shot: b")) == "first_panel_not_establishing"
    assert shots_problem(panels("Close-up: a", "Wide shot: b"), establishing=False) is None
    assert shots_problem(panels("Wide shot: a", "Wide shot: b", "Wide shot: c")) == "shots_not_varied"


def test_the_bubble_rule_names_every_kind():
    for kind in BUBBLE_KINDS:
        assert f'"{kind}"' in COMIC_BUBBLE_RULE


def test_props_are_optional():
    assert props_rule({}) == ""
    assert props_rule({"props": [{"name": "lantern", "look": "small brass lantern"}]}).count("lantern: small brass") == 1


def test_compiled_prompts_preserve_style_and_story_changes_without_forcing_faces_or_props():
    from book_comic.image_prompts import panel_prompt, sheet_prompt, cover_prompt
    cast = {'style': 'chibi flat monochrome', 'characters': [{'name_en': 'Hero', 'look': 'adult in teal blazer'}],
            'props': [{'name': 'book', 'look': 'small brown leather book'}]}
    panel = panel_prompt(cast, {'scene': 'Close-up: Hero opens the book in a new room.'}, 'Hero: adult in teal blazer', ('photo', 'sheet', 'previous'))
    assert 'unless the current scene explicitly changes location, time or lighting' in panel
    assert 'fixed identifying geometry' in panel and 'approved changes of pose' in panel
    assert 'focal subject specified by the scene' in panel and 'face or gesture first' not in panel
    assert 'A monochrome style stays monochrome' in panel
    assert 'keep heads below' not in panel
    sheet = sheet_prompt(cast, cast['characters'][0], ('photo',))
    assert 'including intentional exaggeration' in sheet and 'Use natural proportions' not in sheet
    assert 'specified age group controls depicted age' in sheet
    cover = cover_prompt(cast, {'scene': 'Hero crouches with the book.'}, ('photo', 'sheet', 'panels'))
    assert 'without forcing a standing pose' in cover
    assert 'Show only the props and companions requested by the cover scene' in cover
    assert 'Draw every story prop' not in cover
