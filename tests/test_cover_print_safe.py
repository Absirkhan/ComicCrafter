"""Cover lettering stays inside the printers' margin on the printed cover, with fake clients.

The printed cover (the Books repo's comicPrint `coverFront`) scales the 2063 x 3150 px art to cover the front
panel and its bleed, so the art's edges are cut away. PRINTERS repeats both printers' cuts.
"""

import numpy as np
import pytest
from PIL import Image

from book_comic.back_cover_lettering import letter_back_cover
from book_comic.cover_lettering import letter_cover

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
