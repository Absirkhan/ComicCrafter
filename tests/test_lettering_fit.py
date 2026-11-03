"""Lettering still fits when a medium shot or close-up puts the head in the upper third and leaves one calm side
(book_comic/lettering_space.py), at the print panel size and with the production lettering font; nothing shrinks."""

import numpy as np
import pytest
from PIL import Image, ImageDraw

from book_comic.render import PageRenderer, RenderOptions
from conftest import FakeImages, FakeVision
from layout.bubble_planner import BubblePlan
from layout.comic_bubbles import render_dialogue
from layout.lettering import LETTERING_FONT

PANEL = (1837, 944)  # one of the three print-page panel slots (print_layouts, VERTICAL_STRIP)
FONT = str(LETTERING_FONT)  # the bridge letters every language with it (apps/worker/comics/preview.py)
CAST = {"style": "ink comic", "characters": [{"name_en": "Hero", "look": "teal blazer"}], "language": "he"}
# Head in the upper third, figure off-centre, scenery calm beside it (about two-fifths of the width here). Close-up faces are protected
# generously: the full panel height and over a third of its width.
LAYOUTS = {
    "medium shot, figure right": ([(0.55, 0.0, 0.2, 0.4), (0.5, 0.55, 0.3, 0.3)], (0.65, 0.3)),
    "medium shot, figure left": ([(0.25, 0.0, 0.2, 0.4), (0.2, 0.55, 0.3, 0.3)], (0.35, 0.3)),
    "close-up, face right": ([(0.4, 0.03, 0.36, 0.94)], (0.58, 0.62)),
    "close-up, face left": ([(0.24, 0.03, 0.36, 0.94)], (0.42, 0.62)),
}
SHORT = [(True, "הרוח התחזקה, אבל הדרך אל המגדל כבר הייתה ברורה.", "אני יודע איך להגיע לשם."),
         (False, "The wind grew stronger, but the way to the tower was clear.", "I know how to get there.")]
# The writer's limits: a caption up to 160 characters in two sentences, a dialogue line up to 70.
LONG = [(True, "הרוח התחזקה מעל הגבעות הרחוקות, אבל הדרך אל המגדל הישן כבר הייתה ברורה וקרובה. נועה ידעה שהיא חייבת להגיע לשם לפני רדת החשכה.",
         "אני יודע איך להגיע לשם, רק צריך עוד קצת אומץ ועוד כמה צעדים קטנים."),
        (False, "The wind grew stronger over the distant hills, but the way to the old tower was finally clear and close. Noa knew she had to get there before dark.",
         "I know how to get there, I just need a little more courage and a few s")]


def subject_art(boxes):
    """Dark subject rectangles on a plain background (the calm area)."""
    art = Image.new("RGB", PANEL, "#b9d3df")
    draw = ImageDraw.Draw(art)
    for x, y, w, h in boxes:
        draw.rectangle((int(x * PANEL[0]), int(y * PANEL[1]), int((x + w) * PANEL[0]) - 1, int((y + h) * PANEL[1]) - 1), fill="#40262b")
    return art


def assert_subjects_clear(before, after, boxes):
    """No caption or bubble covers a protected subject; only a bubble tail may point into it."""
    for x, y, w, h in boxes:
        area = (int(x * PANEL[0]), int(y * PANEL[1]), int((x + w) * PANEL[0]), int((y + h) * PANEL[1]))
        changed = np.any(np.asarray(before.crop(area)) != np.asarray(after.crop(area)), axis=2)
        assert changed.mean() < 0.02


@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("rtl, caption, words", SHORT + LONG)
def test_caption_and_bubble_fit_beside_a_head_in_the_upper_third(layout, rtl, caption, words):
    assert len(caption) <= 160 and len(words) <= 70
    boxes, mouth = LAYOUTS[layout]
    art = subject_art(boxes)
    plan = BubblePlan(speakers=[mouth], bubbles=[(0.15, 0.5)], protected=boxes, protected_checked=True)
    result = render_dialogue(art, [words], caption, plan, rtl=rtl, font_path=FONT)
    assert result.size == art.size and result.tobytes() != art.tobytes()
    assert_subjects_clear(art, result, boxes)


@pytest.mark.parametrize("layout", LAYOUTS)
def test_the_renderer_letters_those_panels_with_a_note_and_no_lettering_failure(layout):
    boxes, mouth = LAYOUTS[layout]
    answer = {"lines": [{"mouth": [int(mouth[0] * 1000), int(mouth[1] * 1000)], "bubble": [150, 500]}],
              "protected": [[int(v * 1000) for v in box] for box in boxes]}
    vision = FakeVision(lambda p, i: answer)
    renderer = PageRenderer(CAST, FakeImages([Image.new("RGB", (64, 64))]), vision,
                            options=RenderOptions(check_art=True, font_path=FONT))
    lettered = renderer._letter(subject_art(boxes), {"caption": SHORT[0][1], "note": "לנועה, באהבה",
                                                     "dialogue": [{"text": SHORT[0][2], "speaker": "Hero"}]})
    assert lettered.size == PANEL and renderer.lettering_checks == set()
    assert len(vision.prompts) == 1  # the first plan fit: no precise retry


def test_a_long_caption_takes_the_narrow_shape_beside_a_close_up_rather_than_failing():
    boxes, mouth = LAYOUTS["close-up, face left"]
    rtl, caption, words = LONG[1]
    plan = BubblePlan(speakers=[mouth], bubbles=[(0.8, 0.5)], protected=boxes, protected_checked=True)
    result = render_dialogue(subject_art(boxes), [words], caption, plan, rtl=rtl, font_path=FONT)
    assert result.size == PANEL
