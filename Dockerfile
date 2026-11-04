# Comic engine image: runs one comic job per container, then exits.
#   docker run --rm --env-file comic.env -v <work>:/work comic-engine python <script>
# Secrets are passed at run time and never baked into the image.
# Also the base image of hosts that run the engine in-process (e.g. a comics worker): the engine
# lives at /engine/ComicCrafter (on PYTHONPATH, bundled OFL fonts in assets/fonts); hosts add their
# own runtime and switch USER as needed.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/engine:/engine/ComicCrafter

# libfribidi0: Pillow's bundled libraqm loads it at run time; without it Hebrew (RTL) lettering is
# drawn in logical order, i.e. reversed. poppler-utils: book_comic.book_text runs pdftotext.
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-dejavu-core libfribidi0 poppler-utils \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /engine/ComicCrafter
COPY requirements.comic.txt .
RUN pip install -r requirements.comic.txt

COPY . .

RUN useradd --uid 10001 --no-create-home comic && mkdir -p /work && chown comic /work
USER comic
WORKDIR /work

# Smoke check: the public modules import, the bundled lettering fonts are in the image and Pillow
# lays out RTL text.
CMD ["python", "-c", "import book_comic.render, book_comic.cover, book_comic.cover_lettering, book_comic.art_check, generation.openrouter_image_client, generation.vision_client, layout.bubble_planner, layout.bubble_shapes, layout.captions, layout.panel_layout; from layout.lettering import FONTS_DIR; assert sorted(p.name for p in FONTS_DIR.glob('*.ttf')), 'fonts missing'; from PIL import features; assert features.check('raqm'), 'no RTL text layout'; print('comic engine ok')"]
