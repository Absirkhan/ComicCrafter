"""Readable paid panels must use available safe space before giving up."""
import pytest
from PIL import Image, ImageDraw
from layout.bubble_planner import BubblePlan
from layout.comic_bubbles import render_dialogue
from book_comic.render import PageRenderer, RenderOptions
from conftest import FakeImages


@pytest.mark.parametrize('rtl,caption,words', [
    (True, 'הרוח התחזקה, אבל הדרך אל המגדל כבר הייתה ברורה.', 'אני יודע איך להגיע לשם.'),
    (False, 'The wind grew stronger, but the way to the tower was clear.', 'I know how to get there.'),
])
def test_caption_and_dialogue_use_safe_lower_space_without_shrinking_art(rtl, caption, words):
    art = Image.new('RGB', (1600, 900), '#acd1e0')
    ImageDraw.Draw(art).rectangle((320, 0, 1279, 539), fill='#285263')
    before = art.crop((320, 0, 1280, 540)).tobytes()
    plan = BubblePlan(speakers=[None], bubbles=[(0.5, 0.85)],
                      protected=[(0.2, 0, 0.6, 0.6)], protected_checked=True)
    result = render_dialogue(art, [words], caption, plan, rtl=rtl)
    assert result.size == art.size
    assert result.crop((320, 0, 1280, 540)).tobytes() == before
    assert result.tobytes() != art.tobytes()


def test_unusable_fast_layout_gets_one_precise_retry_without_an_image_call():
    class Vision:
        model = 'fake'
        def __init__(self): self.fast = self.precise = 0
        def ask_json(self, *args):
            self.fast += 1
            return {'lines': [{'mouth': None, 'bubble': [500, 150]}]}  # protection was not verified
        def ask_art_json(self, *args):
            self.precise += 1
            return {'lines': [{'mouth': None, 'bubble': [500, 150]}], 'protected': []}
    vision = Vision()
    images = FakeImages([Image.new('RGB', (64, 64))])
    renderer = PageRenderer({'characters': []}, images, vision, options=RenderOptions(check_art=True))
    result = renderer._letter(Image.new('RGB', (1600, 900)), {'caption': 'The light returned.',
                             'dialogue': [{'text': 'It works!', 'speaker': 'Hero'}]})
    assert result.size == (1600, 900)
    assert vision.fast == vision.precise == 1
    assert images.calls == []
