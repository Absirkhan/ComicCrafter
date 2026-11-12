"""A narration caption is fixed in a top corner of its image and no bubble or tail touches it:
strip panels and full-page splashes, left-to-right and right-to-left."""

import numpy as np
import pytest
from PIL import Image

from book_comic.render import PageRenderer, RenderOptions
from conftest import FakeImages, FakeVision, caption_box
from layout import comic_bubbles as bubbles
from layout.bubble_planner import BubblePlan
from layout.lettering import LETTERING_FONT

PANEL = (1837, 944)  # a print strip panel
SPLASH = (1837, 2924)  # a full-page splash
FONT = str(LETTERING_FONT)
TEXTS = {
    "short": {False: ("A deep groan echoes through the structure.", ["The beams are shifting again."]),
              True: ("רעם עמוק מהדהד בכל המבנה.", ["הקורות זזות שוב."])},
    "long": {False: ("The wind grew stronger over the distant hills, but the way to the old tower was finally clear "
                     "and close. Noa knew she had to get there before dark.", ["I know how to get there."]),
             True: ("הרוח התחזקה מעל הגבעות הרחוקות, אבל הדרך אל המגדל הישן כבר הייתה ברורה וקרובה. נועה ידעה שהיא "
                    "חייבת להגיע לשם לפני רדת החשכה.", ["אני יודע איך להגיע לשם."])},
    "two bubbles": {False: ("Her expression tightens with renewed focus.", ["One more chance.", "Get the timing right."]),
                    True: ("המבט שלה מתחדד בריכוז מחודש.", ["עוד הזדמנות אחת.", "הפעם בתזמון הנכון."])},
}
# Where the old rule let the caption float: subjects protected under both top corners, or filling the top.
SUBJECTS = {
    "calm top": [(0.42, 0.3, 0.16, 0.5)],
    "close-up filling the top": [(0.2, 0.0, 0.6, 0.7)],
    "subjects under both top corners": [(0.0, 0.0, 0.3, 0.4), (0.7, 0.0, 0.3, 0.4)],
}


def assert_top_corner(image, rtl, reading_first=True):
    left, top, right, bottom = caption_box(image)
    inset = max(8, image.height // 40)
    assert abs(top - inset) <= 1
    if rtl == reading_first:
        assert abs(image.width - 1 - right - inset) <= 2  # top-right
    else:
        assert abs(left - inset) <= 1  # top-left
    return left, top, right + 1, bottom + 1


def assert_caption_untouched(art, caption, plan, lettered, box, rtl, type_height=None):
    """The caption's pixels equal a render of the caption alone (in one of the text shapes): nothing is drawn over it."""
    alone = BubblePlan(speakers=[], bubbles=[], protected=plan.protected)
    shapes = [bubbles._render_dialogue_once(art, [], caption, alone, rtl=rtl, font_path=FONT, caption_width=width,
                                            type_height=type_height).crop(box).tobytes()
              for width in (0.46, 0.65, 0.88, 0.34)]
    assert lettered.crop(box).tobytes() in shapes


@pytest.mark.parametrize("subjects", SUBJECTS)
@pytest.mark.parametrize("rtl", [False, True])
@pytest.mark.parametrize("length", TEXTS)
def test_the_caption_is_in_a_top_corner_and_no_bubble_or_tail_touches_it(length, rtl, subjects):
    caption, lines = TEXTS[length][rtl]
    art = Image.new("RGB", PANEL, "#7f97a3")
    mouth = (0.5, 0.45)
    plan = BubblePlan(speakers=[mouth] * len(lines), bubbles=[(0.2, 0.1), (0.8, 0.1)][:len(lines)],
                      protected=SUBJECTS[subjects], protected_checked=True)
    lettered = bubbles.render_dialogue(art, lines, caption, plan, rtl=rtl, font_path=FONT)
    box = assert_top_corner(lettered, rtl)
    assert_caption_untouched(art, caption, plan, lettered, box, rtl)
    paper = np.all(np.asarray(lettered) == 255, axis=2)
    assert paper.any() and not paper[box[1]:box[3], box[0]:box[2]].any()  # bubbles drawn, none on the caption


@pytest.mark.parametrize("rtl", [False, True])
def test_a_head_under_the_reading_first_corner_moves_the_caption_to_the_other_top_corner_only(rtl):
    caption, lines = TEXTS["short"][rtl]
    head = (0.75, 0.0, 0.2, 0.4) if rtl else (0.05, 0.0, 0.2, 0.4)
    plan = BubblePlan(speakers=[None], bubbles=[(0.5, 0.1)], protected=[head], protected_checked=True)
    lettered = bubbles.render_dialogue(Image.new("RGB", PANEL, "#7f97a3"), lines, caption, plan, rtl=rtl, font_path=FONT)
    assert_top_corner(lettered, rtl, reading_first=False)


@pytest.mark.parametrize("kind", ["speech", "thought", "broadcast", "shout"])
def test_a_tail_never_crosses_the_caption(kind):
    # The speaker is above a box and the planner wants the bubble right below it: the old tail ran through the box
    box = (200, 150, 420, 50)
    area = (box[0], box[1], box[0] + box[2], box[1] + box[3])
    blank = Image.new("RGB", (800, 500), "#7f97a3")
    crossed, clear = blank.copy(), blank.copy()
    bubbles.draw_speech_bubble(crossed, "Hello there", (0.5, 0.52), (0.5, 0.1), [box], kind)
    bubbles.draw_speech_bubble(clear, "Hello there", (0.5, 0.52), (0.5, 0.1), [box], kind, tail_clear=[box])
    assert crossed.crop(area).tobytes() != blank.crop(area).tobytes()
    assert clear.crop(area).tobytes() == blank.crop(area).tobytes()
    assert clear.tobytes() != blank.tobytes()


@pytest.mark.parametrize("rtl", [False, True])
@pytest.mark.parametrize("subjects", SUBJECTS)
def test_a_full_page_splash_keeps_its_caption_in_a_top_corner_clear_of_the_bubble(rtl, subjects):
    caption, lines = TEXTS["short"][rtl]
    answer = {"lines": [{"mouth": [500, 300], "bubble": [300, 60]}],
              "protected": [[int(v * 1000) for v in box] for box in SUBJECTS[subjects]]}
    renderer = PageRenderer({"style": "ink comic", "characters": [{"name_en": "Hero", "look": "teal blazer"}]},
                            FakeImages([Image.new("RGB", (64, 64))]), FakeVision(lambda p, i: answer),
                            options=RenderOptions(check_art=True, font_path=FONT))
    art = Image.new("RGB", SPLASH, "#7f97a3")
    panel = {"caption": caption, "dialogue": [{"text": lines[0], "speaker": "Hero"}]}
    lettered = renderer._letter(art, panel, type_height=PANEL[1])
    box = assert_top_corner(lettered, rtl)
    plan = BubblePlan(speakers=[(0.5, 0.3)], bubbles=[(0.3, 0.06)], protected=SUBJECTS[subjects])
    assert_caption_untouched(art, caption, plan, lettered, box, rtl, type_height=PANEL[1])
