"""Opt-in saving of rejected draws: file names, non-personal JSON, the cap, and no effect on the outcome."""

import json

import pytest
from PIL import Image

from book_comic.art_check import ArtCheckError, draw_checked
from book_comic.cover import render_cover
from book_comic.rejected_art import RejectedArtSaver
from book_comic.render import PageRenderer, RenderOptions
from conftest import FakeImages, FakeVision
from layout.panel_layout import LayoutManager

CAST = {"style": "comic", "characters": [{"name_en": "Dana", "name": "דנה", "look": "red coat"}]}
SMALL = LayoutManager(page_width=400, page_height=600, margin=10, gutter=10)
SCENE = "Dana opens the secret door at dawn"
RED, BLUE = (255, 0, 0), (0, 0, 255)
CLEAN = {"head_top": 500, "has_text": False, "bad_anatomy": False, "identity_mismatch": False,
         "design_mismatch": False, "scene_mismatch": False}


def colours(*names):
    return [Image.new("RGB", (40, 60), n) for n in names]


def judge(flags):
    return FakeVision(lambda p, i: {**CLEAN, **flags.get(i.getpixel((0, 0)), {})})


def renderer(images, vision, **options):
    return PageRenderer(CAST, images, vision, SMALL, RenderOptions(check_art=True, **options))


def records(directory):
    return {p.name: json.loads(p.read_text()) for p in sorted(directory.glob("*.json"))}


def test_nothing_is_written_without_a_rejected_dir(tmp_path):
    r = renderer(FakeImages(colours("red", "blue")), judge({RED: {"has_text": True}}))
    r.render_page([{"scene": SCENE}], tmp_path / "page_01.png")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["art_page_01_1.png", "page_01.png"]
    assert r.rejected.saved == 0


def test_a_rejected_then_accepted_panel_writes_one_pair(tmp_path):
    out = tmp_path / "rejected"
    r = renderer(FakeImages(colours("red", "blue")), judge({RED: {"has_text": True, "bad_anatomy": True}}), rejected_dir=out)
    r.render_page([{"scene": SCENE, "characters": ["Dana"]}], tmp_path / "page_01.png")
    assert sorted(p.name for p in out.iterdir()) == ["panel_p1_d1.json", "panel_p1_d1.png"]
    assert Image.open(out / "panel_p1_d1.png").getpixel((0, 0)) == RED  # the rejected art, not the accepted one
    assert records(out)["panel_p1_d1.json"] == {"stage": "panel", "panel": 1, "draw": 1,
                                                "failed_checks": ["has_text", "bad_anatomy"], "reasons": []}


def test_cover_and_sheet_rejects_are_stage_cover_and_sheet_panel_0(tmp_path):
    out = tmp_path / "rejected"
    r = renderer(FakeImages(colours("red", "blue")), judge({RED: {"identity_mismatch": True}}),
                 rejected_dir=out, sheet_path=tmp_path / "sheet.png")
    r.character_sheet()
    images = FakeImages(colours("red", "blue"))
    render_cover(CAST, {"scene": SCENE, "title": "T"}, (400, 600), tmp_path / "cover.png", images,
                 judge({RED: {"has_text": True}}), on_reject=r.rejected.hook("cover"))
    assert records(out) == {
        "cover_p0_d1.json": {"stage": "cover", "panel": 0, "draw": 1, "failed_checks": ["has_text"], "reasons": []},
        "sheet_p0_d1.json": {"stage": "sheet", "panel": 0, "draw": 1, "failed_checks": ["identity_mismatch"], "reasons": []},
    }


def test_an_unavailable_check_is_saved_before_the_raise(tmp_path):
    out = tmp_path / "rejected"
    saver = RejectedArtSaver(out)
    with pytest.raises(ArtCheckError, match="comic_art_check_unavailable"):
        draw_checked(FakeImages(colours("red")), FakeVision(lambda p, i: {**CLEAN, "has_text": None}),
                     SCENE, [], "2:3", on_reject=saver.hook("panel", 2))
    assert records(out)["panel_p2_d1.json"]["failed_checks"] == ["check_unavailable"]


def test_at_most_twelve_pairs_per_renderer_and_the_outcome_is_unchanged(tmp_path):
    out = tmp_path / "rejected"
    r = renderer(FakeImages(colours("red")), judge({RED: {"has_text": True}}), rejected_dir=out)
    for page in range(5):  # three rejected draws per page
        with pytest.raises(ArtCheckError, match="comic_art_rejected"):
            r.render_page([{"scene": SCENE}], tmp_path / f"page_{page}.png")
        for f in out.glob("*"):
            f.rename(out / f"{page}_{f.name}")  # keep each page's files apart to count them
    assert len(list(out.glob("*.png"))) == 12 and len(list(out.glob("*.json"))) == 12


def test_a_failing_save_never_changes_the_render(tmp_path):
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x")
    r = renderer(FakeImages(colours("red", "blue")), judge({RED: {"has_text": True}}), rejected_dir=blocker)
    r.render_page([{"scene": SCENE}], tmp_path / "page_01.png")
    assert (tmp_path / "page_01.png").exists()


def test_reasons_keep_only_failed_observations_and_no_brief_text(tmp_path):
    out = tmp_path / "rejected"
    requirements = [{"subject": "Hero", "attribute": "pose", "expected": "kneeling"},
                    {"subject": "door", "attribute": "state", "expected": "open"}]
    answer = {**CLEAN, "scene_mismatch": True, "requirement_mismatch": True,
              "requirement_checks": [{"index": 0, "observed": "the girl stands upright beside a wall", "matches": False},
                                     {"index": 1, "observed": "the door is wide open", "matches": True}],
              "corrections": ["Draw the figure kneeling on the floor", "Dana should hold the key",
                              "opens the secret door at dawn"]}
    draws = iter([answer, CLEAN])
    saver = RejectedArtSaver(out, names=["Dana", "דנה"])
    draw_checked(FakeImages(colours("red", "blue")), FakeVision(lambda p, i: next(draws)), SCENE, [], "2:3",
                 requirements=requirements, on_reject=saver.hook("panel", 3))
    record = records(out)["panel_p3_d1.json"]
    assert record["failed_checks"] == ["scene_mismatch", "requirement_mismatch"]
    assert record["reasons"] == ["the girl stands upright beside a wall", "Draw the figure kneeling on the floor"]
    text = json.dumps(record, ensure_ascii=False)
    assert "Dana" not in text and "secret door" not in text and "kneeling\"" not in text
    assert set(record) == {"stage", "panel", "draw", "failed_checks", "reasons"}


def test_reasons_are_trimmed_and_capped_at_eight(tmp_path):
    saver = RejectedArtSaver(tmp_path)
    found = {**CLEAN, "has_text": True, "corrections": ["x" * 400] + [f"remove sign {n}" for n in range(12)]}
    saver.save("panel", 1, 1, Image.new("RGB", (4, 4)), found)
    reasons = records(tmp_path)["panel_p1_d1.json"]["reasons"]
    assert len(reasons) == 8 and reasons[0] == "x" * 300
