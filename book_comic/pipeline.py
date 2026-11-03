"""Book PDF -> one comic page per chapter (and a cover) -> PNG pages and a combined PDF."""

import json
import logging
from pathlib import Path
from typing import Callable, Dict, Optional

from PIL import Image

from book_comic.book_text import extract_chapters
from book_comic.cover import render_cover
from book_comic.render import PageRenderer, RenderOptions, save_pdf
from book_comic.script import ScriptWriter
from generation.openrouter_image_client import OpenRouterImageClient
from generation.vision_client import VisionClient

logger = logging.getLogger(__name__)


def _cached(path: Path, build: Callable[[], object]):
    """Load JSON from path, or build it and save it, so reruns don't pay for the same LLM call."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    value = build()
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return value


def default_options(output_dir: Path) -> RenderOptions:
    """Book defaults: a character sheet drawn once per book, panels chained and checked for painted text."""
    return RenderOptions(sheet_path=output_dir / "character_sheet.png", chain_panels=True, check_art=True)


def _draw_cover(renderer: PageRenderer, cast: Dict, output_dir: Path, path: Path) -> Optional[Path]:
    """The cover from cast["cover"], with the first drawn page's panels as reference. None if skipped."""
    first_page = next(iter(sorted(output_dir.glob("page_*.png"))), None)
    if not cast.get("cover", {}).get("scene") or first_page is None:
        return None
    panels = [Image.open(p).convert("RGB") for p in sorted(output_dir.glob(f"art_{first_page.stem}_*.png"))]
    options = renderer.options
    roles, references = [], []
    for role, url in (("photo", options.photo), ("sheet", renderer.character_sheet())):
        if url:
            roles.append(role)
            references.append(url)
    try:
        return render_cover(
            cast, cast["cover"], (renderer.layouts.page_width, renderer.layouts.page_height), path,
            renderer.images, renderer.vision, panels=panels, references=references, reference_roles=roles,
            dpi=options.dpi, on_reject=renderer.rejected.hook("cover"),
        )
    except Exception as e:
        if options.fail_on_image_error:
            raise
        logger.warning(f"Cover failed; the comic has no cover: {e}")
        return None


def generate_book_comic(
    pdf_path: Path,
    output_dir: Path,
    first_chapter: int = 1,
    last_chapter: Optional[int] = None,
    options: Optional[RenderOptions] = None,
    draw_cover: bool = True,
    writer: Optional[ScriptWriter] = None,
    images: Optional[OpenRouterImageClient] = None,
    vision: Optional[VisionClient] = None,
) -> Dict:
    """Make one comic page per chapter in [first_chapter, last_chapter], and a cover.

    The character sheet, chapter scripts and cover are cached in output_dir, so pages made in
    separate runs share the same characters. The PDF holds the cover and every page made so far.

    Args:
        options: How pages are drawn (default: default_options; RenderOptions() is the plain renderer)
        draw_cover: Draw cover.png from the cast's "cover" when it isn't there yet
        writer, images, vision: Script, image and vision clients (OpenRouter defaults when None)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    chapters = extract_chapters(pdf_path)
    last_chapter = last_chapter or chapters[-1].number
    selected = [c for c in chapters if first_chapter <= c.number <= last_chapter]
    logger.info(f"{len(chapters)} chapters found; drawing {len(selected)}")

    writer = writer or ScriptWriter()
    cast = _cached(output_dir / "cast.json", lambda: writer.build_cast(chapters))
    renderer = PageRenderer(
        cast, images or OpenRouterImageClient(), vision or VisionClient(),
        options=options or default_options(output_dir),
    )

    pages = []
    for chapter in selected:
        panels = _cached(
            output_dir / f"script_{chapter.number:02d}.json",
            lambda: writer.script_chapter(chapter, cast),
        )
        pages.append(renderer.render_page(panels, output_dir / f"page_{chapter.number:02d}.png"))

    cover = output_dir / "cover.png"
    if draw_cover and not cover.exists():
        _draw_cover(renderer, cast, output_dir, cover)

    all_pages = sorted(output_dir.glob("page_*.png"))
    pdf = save_pdf(([cover] if cover.exists() else []) + all_pages, output_dir / f"{pdf_path.stem}-comic.pdf")
    return {
        "status": "success",
        "pages": [str(p) for p in pages],
        "cover": str(cover) if cover.exists() else None,
        "pdf": str(pdf),
        "pages_in_pdf": len(all_pages),
        "cost_usd": round(writer.total_cost + renderer.total_cost, 4),
    }
