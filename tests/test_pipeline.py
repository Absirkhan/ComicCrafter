"""The multi-chapter book pipeline end to end, with fake writer, image and vision clients."""

from PIL import Image

from book_comic import pipeline
from book_comic.book_text import Chapter
from conftest import FakeImages, FakeVision


class FakeWriter:
    total_cost = 0.0

    def __init__(self, cast):
        self.cast = cast

    def build_cast(self, chapters):
        return self.cast

    def script_chapter(self, chapter, cast):
        return [{"scene": f"Wide shot: chapter {chapter.number}", "characters": ["Dana"], "caption": "פרק",
                 "dialogue": [{"speaker": "Dana", "text": "שלום", "bubble": "whisper"}]}]


def run(tmp_path, monkeypatch, cast, first, last, **kwargs):
    chapters = [Chapter(n, f"T{n}", "text") for n in (1, 2, 3)]
    monkeypatch.setattr(pipeline, "extract_chapters", lambda path: chapters)
    images = FakeImages([Image.new("RGB", (64, 96), "white")])
    vision = FakeVision(lambda p, i: {"head_top": 400, "has_text": False, "bad_anatomy": False, "identity_mismatch": False, "design_mismatch": False, "scene_mismatch": False} if "head_top" in p else {"lines": [{"bubble": [500, 200]}], "protected": []})
    result = pipeline.generate_book_comic(tmp_path / "book.pdf", tmp_path / "out", first, last,
                                          writer=FakeWriter(cast), images=images, vision=vision, **kwargs)
    return result, images


def test_chapters_across_runs_share_one_cover_and_pdf(tmp_path, monkeypatch):
    cast = {"style": "comic", "characters": [{"name": "דנה", "name_en": "Dana", "look": "red coat"}],
            "cover": {"scene": "Dana on a cliff", "title": "המגדלור", "starring": "בכיכוב דנה"}}
    result, images = run(tmp_path, monkeypatch, cast, 1, 2)
    assert result["cover"] and result["pages_in_pdf"] == 2
    assert len(images.calls) == 4  # sheet, two panels, cover
    assert len(images.calls[-1]["references"]) == 2  # cover: sheet and page one's panels
    result, images = run(tmp_path, monkeypatch, cast, 3, 3)
    assert result["pages_in_pdf"] == 3 and len(images.calls) == 1  # sheet and cover are reused


def test_an_old_cast_without_cover_uses_the_plain_renderer(tmp_path, monkeypatch):
    cast = {"style": "comic", "characters": [{"name": "דנה", "name_en": "Dana", "look": "red coat"}]}
    result, images = run(tmp_path, monkeypatch, cast, 1, 3, options=pipeline.RenderOptions())
    assert result["cover"] is None and result["pages_in_pdf"] == 3
    assert len(images.calls) == 3 and all(c["references"] == [] for c in images.calls)
