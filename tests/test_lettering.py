"""Bubbles, captions, notes, fonts and page layout, drawn for real (no network)."""

import numpy as np
from PIL import Image

from layout.bubble_planner import BubblePlan
from layout.bubble_shapes import BUBBLE_KINDS
from layout.captions import draw_note
from layout.comic_bubbles import _font, draw_speech_bubble, render_dialogue
from layout.lettering import LETTERING_FONT
from layout.panel_layout import LayoutManager, LayoutType
from book_comic.render import PRINT_PAGE_SIZE


def test_the_page_gutters_between_panels_are_identical():
    for manager in (LayoutManager(), LayoutManager(page_width=PRINT_PAGE_SIZE[0], page_height=PRINT_PAGE_SIZE[1])):
        layout = manager.create_layout(LayoutType.VERTICAL_STRIP, num_panels=3)
        gaps = [below.y - (above.y + above.height) for above, below in zip(layout, layout[1:])]
        assert len(set(gaps)) == 1 and gaps[0] > 0
        assert len({(panel.x, panel.width) for panel in layout}) == 1  # full-width rows, read top to bottom


def test_print_page_size_is_6_875_by_10_5_inches_at_300_dpi():
    assert PRINT_PAGE_SIZE == (2063, 3150)


def test_every_bubble_kind_draws_its_own_shape_and_keeps_clear():
    drawn = {}
    for kind in BUBBLE_KINDS + ("unknown",):
        panel, placed = Image.new("RGB", (700, 420), (196, 214, 226)), [(0, 0, 700, 60)]
        draw_speech_bubble(panel, "שלום, מה שלומך?", (0.4, 0.3), (0.7, 0.7), placed, kind)
        assert len(placed) == 2  # its box is reserved for the next bubble
        assert placed[1][1] >= 60  # never over an earlier box (the caption band here)
        drawn[kind] = np.asarray(panel)
    assert (drawn["unknown"] == drawn["speech"]).all()  # an unknown kind is a plain speech bubble
    assert len({drawn[kind].tobytes() for kind in BUBBLE_KINDS}) == len(BUBBLE_KINDS)


def test_render_dialogue_draws_each_lines_kind():
    plan = BubblePlan(speakers=[(0.7, 0.7)], bubbles=[(0.4, 0.3)])
    art = Image.new("RGB", (700, 420), "white")
    speech = np.asarray(render_dialogue(art, ["Hi there"], "", plan))
    shout = np.asarray(render_dialogue(art, ["Hi there"], "", plan, kinds=["shout"]))
    assert not (speech == shout).all()


def test_a_latin_name_in_hebrew_lettering_is_drawn_not_boxes():
    assert LETTERING_FONT.is_file()
    font = _font(48, "המדדים הכינו את zovek למראה")
    glyph = lambda text: bytes(font.getmask(text))  # noqa: E731
    missing = glyph("")  # a code point no font maps: the empty box
    for letter in "zovek":
        assert glyph(letter) != missing
    assert glyph("ש") != missing


def test_a_font_path_setting_replaces_the_default_faces():
    font = _font(30, "hello", font_path=str(LETTERING_FONT))
    assert font.getname()[0] == "Assistant"
    assert _font(30, "hello", font_path="/missing/font.ttf") is not None  # falls back, never raises


def test_a_caption_moved_to_the_later_corner_keeps_the_bubble_below_it():
    art = Image.new("RGB", (800, 500), "white")
    # The speaker's head sits under the top-right corner, so the RTL caption moves top-left, and the
    # planner asked for the bubble at the top right: reading order puts it below the caption.
    plan = BubblePlan(speakers=[(0.85, 0.2)], bubbles=[(0.85, 0.08)])
    lettered = render_dialogue(art, ["שלום!"], "הקריינות נקראת לפני הבועה.", plan)
    ink = np.asarray(lettered.convert("L")) < 128
    bubble_rows = np.where(ink[:, 420:].any(axis=1))[0]
    caption_rows = np.where(ink[:, :380].any(axis=1))[0]
    assert len(bubble_rows) and len(caption_rows)
    assert bubble_rows.min() > caption_rows.max() - 2


def test_the_caption_starts_in_the_reading_first_corner_whatever_the_model_picked():
    art = Image.new("RGB", (800, 500), "white")
    plan = BubblePlan(speakers=[], bubbles=[], caption_corner="top-left")
    ink = np.asarray(render_dialogue(art, [], "בוקר שקט בסדנה.", plan).convert("L")) < 128
    assert ink[:, 400:].any() and not ink[:, :400].any()  # Hebrew: top-right
    plan.caption_corner = "top-right"
    ink = np.asarray(render_dialogue(art, [], "A quiet morning.", plan).convert("L")) < 128
    assert ink[:, :400].any() and not ink[:, 400:].any()  # left-to-right: top-left


def test_a_note_goes_in_the_last_read_bottom_corner():
    art = Image.new("RGB", (800, 500), "white")
    assert draw_note(art, "") is art
    rtl = np.asarray(draw_note(art, "באהבה מסבתא").convert("L")) < 128
    assert rtl[250:, :400].any() and not rtl[:250].any() and not rtl[:, 400:].any()
    ltr = np.asarray(draw_note(art, "With love").convert("L")) < 128
    assert ltr[250:, 400:].any() and not ltr[:, :400].any()


def test_wrapping_balances_short_final_lines_in_both_languages():
    from PIL import ImageDraw
    from layout.lettering import _wrap
    draw = ImageDraw.Draw(Image.new('RGB', (800, 500)))
    for text in ('Fascinating. Not a single bruise on it.', 'מעניין מאוד אין אפילו סימן אחד על זה.'):
        font = _font(32, text, font_path=str(LETTERING_FONT))
        width = int(draw.textlength(text, font=font) * 0.55)
        lines = _wrap(draw, text, font, width).splitlines()
        assert ' '.join(lines) == text
        assert all(draw.textlength(line, font=font) <= width for line in lines)
        assert len(lines[-1].split()) > 1


def test_bubbles_avoid_protected_companions_and_props_in_both_languages():
    from layout.lettering import overlap_area
    protected = (240, 0, 220, 220)
    for text in ('What is that?', 'מה זה שם?'):
        art, placed = Image.new('RGB', (800, 500), 'white'), [protected]
        draw_speech_bubble(art, text, (0.4, 0.15), (0.8, 0.8), placed)
        assert overlap_area(placed[-1], protected) == 0


def test_render_dialogue_passes_all_protected_subjects_to_placement(monkeypatch):
    import layout.comic_bubbles as bubbles
    boxes = []
    monkeypatch.setattr(bubbles, 'draw_speech_bubble', lambda image, text, center, speaker, placed, *args: boxes.append(list(placed)))
    for rtl, text in ((False, 'Hello'), (True, 'שלום')):
        plan = BubblePlan(speakers=[(0.8, 0.7)], bubbles=[(0.2, 0.1)], protected=[(0.1, 0.2, 0.3, 0.4)])
        bubbles.render_dialogue(Image.new('RGB', (800, 500), 'white'), [text], '', plan, rtl=rtl)
        assert (80, 100, 240, 200) in boxes[-1]


def test_unseen_speaker_has_no_tail_outside_bubble():
    # A random downward tail used to escape the reserved bubble rectangle.
    for kind in ('speech', 'thought', 'whisper', 'broadcast'):
        panel = Image.new('RGB', (900, 600), (196, 214, 226))
        placed = []
        draw_speech_bubble(panel, 'Hello there', (.5, .4), None, placed, kind)
        changed = np.any(np.asarray(panel) != (196, 214, 226), axis=2)
        ys, xs = np.where(changed)
        x,y,w,h = placed[0]
        assert xs.min() >= x-5 and xs.max() <= x+w+5
        assert ys.min() >= y-5 and ys.max() <= y+h+5


def test_whisper_keeps_normal_dialogue_text_size_and_contrast():
    panels, boxes = [], []
    for kind in ('speech', 'whisper'):
        panel = Image.new('RGB', (900, 600), 'white')
        placed = []
        draw_speech_bubble(panel, 'זה לא מצפן רגיל.', (.5,.4), None, placed, kind, font_path=str(LETTERING_FONT))
        panels.append(np.asarray(panel)); boxes.append(placed[0])
    assert boxes[0] == boxes[1]
    x,y,w,h = boxes[0]
    # Interior text remains identical; only the outline conveys whispering.
    interior = (slice(y+h//4,y+3*h//4),slice(x+w//4,x+3*w//4))
    assert np.array_equal(panels[0][interior], panels[1][interior])
