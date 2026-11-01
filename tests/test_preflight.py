import json

import pytest

from book_comic.preflight import review_page
from conftest import FakeVision


@pytest.mark.parametrize('language', ['he', 'en'])
@pytest.mark.parametrize('cover', [False, True])
def test_review_preserves_approved_copy_cast_and_props(language, cover):
    captions = ['נועה מתקרבת.' if language == 'he' else 'Noa approaches.'] * 3
    script = {'language': language, 'cast': {'style': 'clay', 'characters': [{'name': 'נועה' if language == 'he' else 'Noa', 'name_en': 'Hero', 'look': 'teal blazer'}],
              'props': [{'name': 'owl', 'look': 'round brass body'}]}, 'cover': {'scene': 'Hero holds owl.', 'title': 'Title'},
              'panels': [{'scene': 'Hero moves.', 'caption': c, 'dialogue': [{'text': 'Hello'}]} for c in captions]}
    def answer(prompt, image):
        assert image is None
        data = json.loads(prompt.split('Storyboard data:\n')[1])
        assert 'נועה' not in json.dumps(data, ensure_ascii=False) and 'Noa' not in json.dumps(data)
        return {'action_continuity': True, 'text_agreement': True, 'design_continuity': True,
                'panels': [{'requirements': [{'subject': 'Hero', 'attribute': 'pose', 'expected': 'standing'}]} for _ in range(3)],
                'cover_requirements': [{'subject': 'owl', 'attribute': 'design', 'expected': 'round brass body'}] if cover else []}
    vision = FakeVision(answer)
    reviewed = review_page(script, vision, include_cover=cover)
    assert len(vision.prompts) == 1
    assert reviewed['cast'] == script['cast']
    assert [p['scene'] for p in reviewed['panels']] == [p['scene'] for p in script['panels']]
    assert reviewed['cover']['scene'] == script['cover']['scene']
    assert [p['caption'] for p in reviewed['panels']] == captions
    assert [p['dialogue'] for p in reviewed['panels']] == [p['dialogue'] for p in script['panels']]
    assert script['panels'][0]['scene'] == 'Hero moves.'


@pytest.mark.parametrize('answer', [{}, {'action_continuity': 'true'}, {'action_continuity': True, 'text_agreement': False, 'design_continuity': True}])
def test_preflight_rejects_missing_or_failed_checks(answer):
    script = {'cast': {'characters': []}, 'panels': [], 'cover': {'scene': ''}}
    with pytest.raises(ValueError, match='comic_preflight_failed'):
        review_page(script, FakeVision(lambda p, i: answer))


def test_private_names_do_not_corrupt_ordinary_words():
    script = {'language':'he', 'cast':{'characters':[{'name':'גיל','name_en':'Hero','look':'silver hair'}]},
              'panels':[{'scene':'Hero holds a compass.', 'caption':'זה לא מצפן רגיל. גיל מצא אותו. לגיל יש מצפן.', 'dialogue':[]}],
              'cover':{'scene':'Hero holds a compass.'}}
    def answer(prompt, image):
        data = json.loads(prompt.split('Storyboard data:\n')[1])
        assert data['panels'][0]['caption'] == 'זה לא מצפן רגיל. Hero מצא אותו. לHero יש מצפן.'
        return {'action_continuity':True,'text_agreement':True,'design_continuity':True,
                'panels':[{'requirements':[{'subject':'Hero','attribute':'pose','expected':'standing'}]}],
                'cover_requirements':[{'subject':'Hero','attribute':'pose','expected':'standing'}]}
    review_page(script, FakeVision(answer))
