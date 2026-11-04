"""Turn a book PDF into a comic, one page per chapter.

Runs book_comic.pipeline synchronously and needs only requirements.comic.txt
(plus poppler's pdftotext). To queue the same job on a Celery worker instead,
see worker/tasks.py (generate_book_comic) and requirements.worker.txt.

Usage:
    python examples/book_example.py <book.pdf> [first_chapter] [last_chapter]
"""

import logging
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv  # noqa: E402

from book_comic.pipeline import generate_book_comic  # noqa: E402


def _output_dir(pdf: Path) -> Path:
    name = re.sub(r"[^A-Za-z0-9_-]", "_", pdf.stem).strip("_") or "comic"
    return ROOT_DIR / "output" / name


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv(ROOT_DIR / ".env")

    pdf = Path(sys.argv[1]).expanduser().resolve()
    first = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    last = int(sys.argv[3]) if len(sys.argv) > 3 else None

    result = generate_book_comic(pdf, _output_dir(pdf), first, last)

    print(f"Status: {result['status']}  (cost ${result['cost_usd']})")
    for page in result["pages"]:
        print(page)
    print(f"PDF ({result['pages_in_pdf']} pages): {result['pdf']}")
