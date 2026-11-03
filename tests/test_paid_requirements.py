from book_comic.preflight import review_page, _explicit_requirements
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
    assert 'one-eighth' in prompt


@pytest.mark.parametrize('scene,state', [('Hero opens the Case.', 'open'), ('Hero shuts the lid.', 'closed'),
                                        ('The Case is vertical.', 'upright'), ('The Case rests horizontally.', 'flat')])
def test_explicit_state_synonyms_remain_required(scene, state):
    required = [{'subject': 'Case', 'attribute': 'state', 'expected': state}]
    assert _explicit_requirements(scene, required) == required


@pytest.mark.parametrize('scene,expected', [
    ('A Sensor rests on the open Toolbox.', ['Toolbox']),
    ('The Toolbox is open beside the Sensor.', ['Toolbox']),
    ('Hero opens the Toolbox beside the Sensor.', ['Toolbox']),
    ('The Sensor is open on the open Toolbox.', ['Sensor', 'Toolbox']),
    ('The open Toolbox and Sensor rest on a table.', ['Sensor', 'Toolbox']),
])
def test_states_do_not_transfer_between_adjacent_objects(scene, expected):
    requirements = [{'subject': name, 'attribute': 'state', 'expected': 'open'} for name in ['Sensor', 'Toolbox']]
    result = _explicit_requirements(scene, requirements, ['Sensor', 'Toolbox'])
    assert [r['subject'] for r in result] == expected


def test_lettered_panel_reserves_natural_background_without_sending_its_words():
    prompt = panel_prompt({'characters': [], 'style': 'ink'},
                          {'scene': 'Close-up: Hero checks a device.', 'caption': 'PRIVATE_CAPTION',
                           'dialogue': [{'text': 'PRIVATE_DIALOGUE'}]}, 'Hero: teal blazer')
    assert 'CALM AREA: keep the requested crop; the head may reach into the upper third' in prompt
    assert 'one full-bleed illustration, never a blank strip' in prompt
    assert 'PRIVATE_CAPTION' not in prompt and 'PRIVATE_DIALOGUE' not in prompt


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
