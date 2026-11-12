"""Cover lettering and the hero's head stay inside the printers' margin on the printed cover, with fake clients.

The printed cover (the Books repo's comicPrint `coverFront`) scales the 2063 x 3150 px art to cover the front
panel and its bleed, so the art's edges are cut away. PRINTERS repeats both printers' cuts.
"""

import numpy as np
import pytest
from PIL import Image

from book_comic import cover as cover_module
from book_comic.back_cover_lettering import letter_back_cover
from book_comic.cover import HEAD_SAFE_MIN, HEADROOM_FIX, render_cover
from book_comic.cover_lettering import letter_cover
from book_comic.revise import REVISE_MARK
from conftest import FakeImages, FakeVision

W, H = 2063, 3150
MARGIN_MM = 12.7 + 1  # Lulu's text margin inside the trim, and 1 mm to spare
# panel: the front's trim width + the outer bleed; sheet: the trim height + both bleeds; top_cut: art cut above the trim.
PRINTERS = {"lulu": {"panel": 168.275 + 3.175, "sheet": 260.35 + 2 * 3.175, "bleed": 3.175, "top_cut": None},
            "bookpod": {"panel": 165 + 3.2, "sheet": 235 + 2 * 3.2, "bleed": 3.2, "top_cut": 7.8}}
SHORT = {"title": "Curiosity's Spark", "starring": "Starring Maya"}  # BOOKS-45
LONG = {"title": "The Extraordinarily Long Birthday Adventure of Grandpa",
        "starring": "Starring Maximilian Alexander the Third of the Northern Lighthouse Islands",  # wraps to two lines
        "footer": "For my dearest grandfather, with all the love in the world, from all of us at home"}  # two lines
HEBREW = {"title": "המצאת יום ההולדת הגדולה והמופלאה של סבא", "starring": "בכיכוב דנה", "footer": "בשביל סבא"}
CAST = {"style": "comic", "characters": [{"name_en": "Dana", "look": "red coat"}]}
CLEAN = {"has_text": False, "bad_anatomy": False, "identity_mismatch": False, "design_mismatch": False, "scene_mismatch": False}


def lettered_lines(image):
    """(top, bottom, left, right) in px of each run of rows holding white lettering, top to bottom."""
    mask = np.asarray(image).min(axis=2) >= 250
    rows, lines, start = [*mask.any(axis=1), False], [], None
    for y, on in enumerate(rows):
        if on and start is None:
            start = y
        elif not on and start is not None:
            xs = np.where(mask[start:y].any(axis=0))[0]
            lines.append((start, y, int(xs.min()), int(xs.max()) + 1))
            start = None
    return lines


def inside_trim_mm(line, printer):
    """How far inside the printed trim a lettered line sits: top, bottom, and the nearer side (the outer one)."""
    top, bottom, left, right = line
    scale = max(printer["panel"] / W, printer["sheet"] / H)
    overflow = H * scale - printer["sheet"]
    above = overflow / 2 if printer["top_cut"] is None else min(max(printer["top_cut"] - printer["bleed"], 0), overflow)
    side = (W * scale - printer["panel"]) / 2 + printer["bleed"]
    return {"top": top * scale - above - printer["bleed"], "bottom": (H - bottom) * scale - (overflow - above) - printer["bleed"],
            "side": min(left, W - right) * scale - side}


@pytest.mark.parametrize("printer", PRINTERS)
@pytest.mark.parametrize("at_bottom", [True, False])
@pytest.mark.parametrize("cover, lines", [(SHORT, 2), (LONG, 5), (HEBREW, 3)])
def test_cover_lettering_prints_inside_the_margin(printer, at_bottom, cover, lines):
    found = lettered_lines(letter_cover(Image.new("RGB", (W, H), (90, 120, 160)), cover, title_at_bottom=at_bottom))
    assert len(found) == lines  # the title stays one line; a long starring line and footer wrap to two
    for line in found:
        mm = inside_trim_mm(line, PRINTERS[printer])
        assert mm["bottom"] >= MARGIN_MM and mm["side"] >= MARGIN_MM
        # A top title on BookPod's B5 is 8.6 mm inside the trim: past its own 5 mm text line, short of Lulu's margin.
        assert mm["top"] >= (MARGIN_MM if printer == "lulu" else 8)


def test_the_bottom_title_block_of_books_45_moved_out_of_the_margin():
    """BOOKS-45: the starring line ended 4.2 mm above Lulu's trim and was cut off whole on BookPod's B5."""
    title, starring = lettered_lines(letter_cover(Image.new("RGB", (W, H), (90, 120, 160)), SHORT, title_at_bottom=True))
    assert round(inside_trim_mm(starring, PRINTERS["lulu"])["bottom"], 1) == 26.2
    assert round(inside_trim_mm(starring, PRINTERS["bookpod"])["bottom"], 1) == 14.3
    assert round(inside_trim_mm(title, PRINTERS["lulu"])["bottom"], 1) == 38.0
    assert title[1] - title[0] == 140 and (title[2], title[3]) == (361, 1706)  # the same face, size and centring as before


def test_the_back_cover_footer_prints_inside_the_margin():
    back = letter_back_cover(Image.new("RGB", (W, H), (90, 120, 160)), {"tagline": "", "blurb": "", "footer": LONG["footer"]})
    plain = letter_back_cover(Image.new("RGB", (W, H), (90, 120, 160)), {"tagline": "", "blurb": ""})
    assert not lettered_lines(plain)
    for line in lettered_lines(back):
        for printer in PRINTERS.values():
            mm = inside_trim_mm(line, printer)
            assert mm["bottom"] >= MARGIN_MM and mm["side"] >= MARGIN_MM


def test_the_head_limit_keeps_the_hair_inside_both_printers_top_margin():
    for printer in PRINTERS.values():
        assert inside_trim_mm((round(H * HEAD_SAFE_MIN), H, 0, W), printer)["top"] >= 13


def render(tmp_path, monkeypatch, heads, audit=None, rejected=None):
    """render_cover over fake draws whose check reports `heads` in turn; returns (image calls, title_at_bottom)."""
    answers = iter(heads)
    bottoms = []
    monkeypatch.setattr(cover_module, "letter_cover", lambda art, c, f, title_at_bottom: bottoms.append(title_at_bottom) or art)
    images = FakeImages([Image.new("RGB", (400, 600), c) for c in ("red", "green", "blue")])
    render_cover(CAST, {"scene": "Dana on the cliff", **SHORT}, (400, 600), tmp_path / "cover.png", images,
                 FakeVision(lambda p, i: {**CLEAN, "head_top": next(answers) * 1000}), audit=audit,
                 on_reject=(lambda *a, **k: rejected.append(a)) if rejected is not None else None)
    assert (tmp_path / "cover.png").exists()
    return images.calls, bottoms


def test_the_cover_brief_asks_for_setting_above_the_head(tmp_path, monkeypatch):
    calls, _ = render(tmp_path, monkeypatch, [0.3])
    assert len(calls) == 1
    assert "at least one eighth of the canvas height of that setting shows above the head" in calls[0]["prompt"]
    assert "title" not in calls[0]["prompt"].lower()  # naming it makes the model paint lettering


def test_a_head_in_the_top_margin_is_drawn_again_with_a_request_for_headroom(tmp_path, monkeypatch):
    audit, rejected = [], []
    calls, bottoms = render(tmp_path, monkeypatch, [0.048, 0.25], audit, rejected)  # BOOKS-45's hair began 4.8% down
    assert len(calls) == 2 and bottoms == [False]
    assert calls[1]["prompt"].startswith(REVISE_MARK) and HEADROOM_FIX in calls[1]["prompt"]
    assert [(r["accepted"], r.get("head_in_margin")) for r in audit] == [(False, True), (True, None)]
    assert rejected == []  # sound art: not recorded as a vision rejection


def test_a_head_just_below_the_margin_is_kept_without_another_draw(tmp_path, monkeypatch):
    calls, bottoms = render(tmp_path, monkeypatch, [0.09])
    assert len(calls) == 1 and bottoms == [True]  # under 20%: the title still moves to the bottom


def test_a_head_in_the_margin_on_every_draw_never_loses_the_cover(tmp_path, monkeypatch):
    audit = []
    calls, bottoms = render(tmp_path, monkeypatch, [0.04, 0.05, 0.06], audit)
    assert len(calls) == 3 and bottoms == [True]
    assert [r.get("fallback") for r in audit] == [None, None, True]  # the last draw is kept
