"""The 2026-11-10 production review: one full-bleed picture, and a failed check call is retried with backoff."""
import pytest
from PIL import Image

import book_comic.art_check as art_check
from book_comic.art_check import ArtCheckError, inspect_art, require_checked
from book_comic.comic_rules import SINGLE_IMAGE_RULE
from book_comic.image_prompts import panel_prompt
from conftest import FakeVision

BASE = {"has_text": False, "bad_anatomy": False, "identity_mismatch": False, "design_mismatch": False, "scene_mismatch": False,
        "head_top": 400}
ART = Image.new("RGB", (10, 10))


@pytest.fixture
def waits(monkeypatch):  # records the waits (conftest's autouse fixture already makes them instant)
    slept = []
    monkeypatch.setattr(art_check.time, "sleep", slept.append)
    return slept


def failing(times):
    """A vision answer that raises on its first `times` calls, then answers cleanly; .calls counts the calls."""
    def answer(prompt, image):
        answer.calls += 1
        if answer.calls <= times:
            raise TimeoutError("read timed out")
        return dict(BASE)
    answer.calls = 0
    return answer


def test_every_panel_asks_for_one_full_bleed_picture_without_naming_layouts():
    assert "full-bleed illustration whose setting runs unbroken to all four edges" in SINGLE_IMAGE_RULE
    for primer in ("panel border", "inset", "caption box", "split-screen"):  # naming them invites them (2026-11-10)
        assert primer not in SINGLE_IMAGE_RULE
    prompt = panel_prompt({"style": "comic", "characters": []}, {"scene": "Wide shot: Hero on a bridge."}, "Hero: teal coat")
    assert SINGLE_IMAGE_RULE in prompt


def test_gaze_stays_part_of_the_scene_check():
    vision = FakeVision(lambda p, i: dict(BASE))
    inspect_art(ART, vision, context="Medium shot: Hero stands on the bridge, gazing at the Pocket Watch.")
    assert "Gaze alone is not a scene_mismatch" not in vision.prompts[0]  # owner, 2026-11-10: gazing at the watch is the beat


def test_a_clean_answer_is_asked_once_without_waiting(waits):
    answer = failing(0)
    inspect_art(ART, FakeVision(answer), context="brief")
    assert answer.calls == 1 and waits == []


def test_a_failed_check_call_is_retried_after_a_wait(waits):
    answer = failing(1)
    found = inspect_art(ART, FakeVision(answer), context="brief")
    assert answer.calls == 2 and waits == [art_check.CHECK_BACKOFF_SECONDS[0]]
    assert require_checked(found) is True


def test_the_third_call_can_still_pass(waits):
    answer = failing(2)
    found = inspect_art(ART, FakeVision(answer), context="brief")
    assert answer.calls == 3 and waits == list(art_check.CHECK_BACKOFF_SECONDS)
    assert require_checked(found) is True


def test_three_failed_check_calls_leave_the_check_unavailable(waits):
    answer = failing(3)
    found = inspect_art(ART, FakeVision(answer), context="brief")
    assert answer.calls == art_check.CHECK_CALLS == 3
    with pytest.raises(ArtCheckError, match="comic_art_check_unavailable"):
        require_checked(found)
