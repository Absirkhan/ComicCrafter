"""Edge bands (2026-11-10 review): an empty caption strip or page margin along one edge, closed by a ruled line, is cut off."""
import pytest
from PIL import Image

from book_comic.art_check import draw_checked
from book_comic.seam import cut_seam, edge_band_box
from conftest import FakeImages, FakeVision

BASE = {"has_text": False, "bad_anatomy": False, "identity_mismatch": False, "design_mismatch": False, "scene_mismatch": False,
        "head_top": 400}
WHITE, INK, SKY = (245, 245, 242), (20, 20, 20), (180, 210, 240)


def banded(noise, side, depth=40, line=6, size=(400, 600), band=WHITE, ink=INK):
    art = noise(size)
    w, h = size
    boxes = {"top": ((0, 0, w, depth), (0, depth, w, depth + line)),
             "bottom": ((0, h - depth, w, h), (0, h - depth - line, w, h - depth)),
             "left": ((0, 0, depth, h), (depth, 0, depth + line, h)),
             "right": ((w - depth, 0, w, h), (w - depth - line, 0, w - depth, h))}
    strip, rule = boxes[side]
    art.paste(band, strip)
    if ink is not None:
        art.paste(ink, rule)
    return art


@pytest.mark.parametrize("side", ["top", "bottom", "left", "right"])
def test_a_blank_band_closed_by_a_ruled_line_is_cut_on_any_edge(noise, side):
    art = banded(noise, side)
    left, top, right, bottom = edge_band_box(art)
    cut = {"top": top, "bottom": 600 - bottom, "left": left, "right": 400 - right}[side]
    assert 44 <= cut <= 52  # the band and its line (at quarter scale), no deeper
    assert cut_seam(art, (400, 600)).size == (400, 600)


def test_a_plain_light_sky_without_a_ruled_line_is_scenery(noise):
    art = banded(noise, "top", band=SKY, ink=None)
    assert edge_band_box(art) is None and cut_seam(art, (400, 600)) is None


def test_a_dark_floor_along_the_bottom_is_never_cut(noise):
    art = banded(noise, "bottom", band=(60, 50, 40), ink=(10, 10, 10))
    assert edge_band_box(art) is None


def test_a_band_deeper_than_the_strip_limit_is_left_to_the_check(noise):
    art = banded(noise, "top", depth=150)  # a quarter of the height: a second picture, not a strip
    assert edge_band_box(art) is None


def test_a_cut_band_is_marked_in_the_audit_and_the_check_sees_the_cut_art(noise):
    art = banded(noise, "top")
    seen, audit = [], []

    def answer(prompt, image):
        seen.append(image)
        return dict(BASE)

    out = draw_checked(FakeImages([art]), FakeVision(answer), "scene", [], "2:3", size=(400, 600), audit=audit)
    assert audit[0]["seam_cut"] is True and audit[0]["accepted"] is True
    assert out.size == (400, 600)
    assert seen[0].getpixel((200, 2)) != WHITE  # the blank strip is gone before the check


def test_a_light_sky_over_smooth_mid_tone_scenery_is_never_cut():
    """The scan runs at quarter size, which smooths scenery: a mid-tone row under a sky must not pass for a ruled line."""
    art = Image.new("RGB", (400, 600), (128, 120, 110))  # a plain wall or street, flat after smoothing
    art.paste(SKY, (0, 0, 400, 40))
    assert edge_band_box(art) is None
