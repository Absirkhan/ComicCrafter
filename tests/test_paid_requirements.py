from book_comic.preflight import review_page
from book_comic.image_prompts import panel_prompt
from conftest import FakeVision
from PIL import Image
import pytest
from book_comic.art_check import draw_checked, inspect_art
from conftest import FakeImages


def test_preflight_does_not_invent_orientation_for_a_resting_case():
    scene = 'Extreme long shot: Hero stands beside the resting Case on a rocky plateau.'
    script = {'cast': {'characters': [{'name_en': 'Hero'}], 'props': [{'name': 'Case', 'look': 'green case'}]},
              'cover': {'scene': ''}, 'panels': [{'scene': scene, 'caption': '', 'dialogue': []}]}
    answer = {'action_continuity': True, 'text_agreement': True, 'design_continuity': True,
              'panels': [{'requirements': [{'subject': 'Hero', 'attribute': 'pose', 'expected': 'standing'},
                                           {'subject': 'Case', 'attribute': 'state', 'expected': 'upright'}]}],
              'cover_requirements': []}
    result = review_page(script, FakeVision(lambda p, i: answer), include_cover=False)
    assert result['panels'][0]['requirements'] == [{'subject': 'Hero', 'attribute': 'pose', 'expected': 'standing'}]
    assert result['panels'][0]['scene'] == scene


def test_extreme_long_shot_establishes_scale_before_full_character_description():
    prompt = panel_prompt({'characters': [], 'style': 'ink comic'},
                          {'scene': 'Extreme long shot: Hero watches the approaching storm.'}, 'Hero: teal blazer')
    assert prompt.startswith('EXTREME LONG SHOT:')
    assert 'one-sixth' in prompt


@pytest.mark.parametrize('attribute,expected,observed,rejected', [
    ('design', 'brass trim', 'not_visible', False),
    ('state', 'closed', 'open', True),
    ('hand', 'right', 'left', True),
    ('framing', 'hand_detail_only', 'body_visible', True),
])
def test_hidden_design_is_not_a_redesign_but_visible_contradictions_still_fail(attribute, expected, observed, rejected):
    answer = {'has_text': False, 'bad_anatomy': False,
              'requirement_checks': [{'index': 0, 'observed': observed, 'matches': observed != 'not_visible'}]}
    result = inspect_art(Image.new('RGB', (64, 64)), FakeVision(lambda p, i: answer),
                         requirements=[{'subject': 'Hero', 'attribute': attribute, 'expected': expected}])
    assert result['requirement_mismatch'] is rejected


def test_redraw_uses_specific_reviewer_feedback_within_existing_budget():
    images = FakeImages([Image.new('RGB', (64, 64), color) for color in ('red', 'blue')])
    def answer(prompt, image):
        failed = image.getpixel((0, 0)) == (255, 0, 0)
        return {'has_text': False, 'bad_anatomy': False, 'identity_mismatch': False,
                'design_mismatch': False, 'scene_mismatch': failed,
                'corrections': ['Make Hero a small distant figure.'] if failed else []}
    draw_checked(images, FakeVision(answer), 'Extreme long shot: Hero watches.', [], '3:2')
    assert len(images.calls) == 2
    assert 'Make Hero a small distant figure.' in images.calls[1]['prompt']
