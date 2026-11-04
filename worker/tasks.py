import os
import re
import sys
from pathlib import Path

from celery import Celery
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "output"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"

load_dotenv(ROOT_DIR / ".env")
# ComicCrafter's config defaults to CWD-relative paths; pin them to the repo root.
os.environ.setdefault("OUTPUT_DIR", str(OUTPUT_DIR))
os.environ.setdefault("CHROMADB_PATH", str(ROOT_DIR / "data" / "chroma_db"))
sys.path.insert(0, str(ROOT_DIR))

app = Celery(
    "comic_worker",
    broker=os.getenv("CELERY_BROKER_URL", DEFAULT_REDIS_URL),
    backend=os.getenv("CELERY_RESULT_BACKEND", DEFAULT_REDIS_URL),
)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", name).strip("_")
    return cleaned or "comic"


@app.task(name="generate_comic")
def generate_comic(
    story: str,
    output_name: str = "comic",
    max_scenes: int = 4,
    style: str = "comic book style",
) -> dict:
    _require_env("OPENROUTER_API_KEY")
    _require_env("OPENROUTER_MODEL")

    # Imported lazily so the worker starts fast and heavy deps load in the child process.
    from core import ComicCrafter

    crafter = ComicCrafter(llm_provider="openrouter", image_provider="openrouter", output_dir=OUTPUT_DIR)
    pages = crafter.generate_comic(
        story_text=story,
        style=style,
        max_scenes=max_scenes,
        add_dialogue=True,
        output_name=_safe_filename(output_name),
    )

    page_paths = [str(Path(page).resolve()) for page in pages]
    return {
        "status": "success" if page_paths else "failed",
        "pages": page_paths,
        "scenes_requested": max_scenes,
    }


@app.task(name="generate_book_comic")
def generate_book_comic(
    pdf_path: str,
    output_name: str = "",
    first_chapter: int = 1,
    last_chapter: int | None = None,
) -> dict:
    """One comic page per chapter of a book PDF; pages and a combined PDF go to OUTPUT_DIR/<name>."""
    _require_env("OPENROUTER_API_KEY")
    _require_env("OPENROUTER_MODEL")

    from book_comic.pipeline import generate_book_comic as run

    pdf = Path(pdf_path).expanduser().resolve()
    output_dir = OUTPUT_DIR / _safe_filename(output_name or pdf.stem)
    return run(pdf, output_dir, first_chapter, last_chapter)
