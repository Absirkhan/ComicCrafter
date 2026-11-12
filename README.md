# ComicCrafter 🎨📚

**A zero-cost multi-agent AI system for automatic comic generation from text**

ComicCrafter transforms your stories into visual comics using free AI APIs. No expensive GPUs, no local model training, and no paid API subscriptions required!

## ✨ Features

- 🤖 **Multi-Agent Architecture**: Coordinated agents for story analysis, prompt generation, and layout planning
- 🎯 **Character Consistency**: RAG-based character memory using ChromaDB for visual consistency across panels
- 🎨 **Multiple AI Providers**: 
  - **Text Generation**: Groq (Llama 3.3), Google Gemini 2.5
  - **Image Generation**: HuggingFace Inference API (FLUX.1-dev)
- 📐 **Smart Layouts**: Automatic panel layout with multiple preset options
- 💬 **Dialogue Support**: Automatic speech bubble and caption overlays
- 🆓 **Zero Cost**: Uses only free API tiers

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- API keys (all free):
  - [Groq API Key](https://console.groq.com/keys) OR [Google API Key](https://makersuite.google.com/app/apikey)
  - [HuggingFace Token](https://huggingface.co/settings/tokens)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Absirkhan/ComicCrafter.git
   cd ComicCrafter
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install the package**
   ```bash
   pip install -e .
   ```

4. **Configure API keys**
   ```bash
   copy .env.example .env
   ```
   
   Edit `.env` and add your API keys:
   ```
   GROQ_API_KEY=your_groq_api_key_here
   GOOGLE_API_KEY=your_google_api_key_here
   HUGGINGFACE_TOKEN=your_huggingface_token_here
   ```

### Basic Usage

```python
from comiccrafter import ComicCrafter

# Your story
story = """
A brave knight discovers a dragon's lair in the mountains.
The dragon offers the knight a challenge: solve three riddles or face battle.
The knight cleverly solves all three riddles.
Impressed, the dragon becomes the knight's ally.
"""

# Initialize ComicCrafter
crafter = ComicCrafter(llm_provider="groq")

# Generate comic
pages = crafter.generate_comic(
    story_text=story,
    style="fantasy comic book style",
    max_scenes=4,
    add_dialogue=True,
    output_name="dragon_knight"
)

print(f"Generated {len(pages)} pages!")
```

### Run the Example

```bash
python examples/basic_example.py
```

### Run the Web Interface (FastAPI)

For an easy-to-use web interface with REST API:

```bash
python run_api.py
```

Then open your browser to:
- **Web Interface**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

The web interface provides:
- ✨ Interactive story input form
- 🎨 Real-time generation progress
- 🖼️ Instant preview of generated comics
- 📊 Job status tracking
- 🔌 Full REST API for integration

## 🌐 Web API

ComicCrafter includes a FastAPI web application for easy testing and integration.

### Start the API Server

```bash
python run_api.py
```

### Web Interface Features

- **Story Input**: Easy form for entering your story
- **Style Customization**: Choose visual style and parameters
- **Real-time Progress**: Watch generation progress live
- **Instant Preview**: View generated comics immediately
- **Job Management**: Track and manage multiple generation jobs

### REST API Endpoints

- `POST /api/generate` - Generate comic from text
- `GET /api/status/{job_id}` - Check generation status
- `GET /api/output/{filename}` - Download comic page
- `GET /api/jobs` - List all jobs
- `DELETE /api/jobs/{job_id}` - Delete job

For detailed API documentation, see [docs/API_GUIDE.md](docs/API_GUIDE.md) or visit http://localhost:8000/docs after starting the server.

### Python Client Example

```python
from examples.api_client_example import ComicCrafterClient

client = ComicCrafterClient()
job_id = client.generate_comic(
    story_text="Your story here...",
    style="comic book style"
)

# Wait for completion
status = client.wait_for_completion(job_id)

# Download results
files = client.download_all_outputs(job_id, Path("./output"))
```

## 📕 Book Comics (`book_comic`)

`book_comic` turns a book PDF into one comic page per chapter plus a cover
(`examples/book_example.py`, Celery task `generate_book_comic`). It needs only
`requirements.comic.txt`, poppler's `pdftotext` (`brew install poppler` /
`apt-get install poppler-utils`; the Docker image has it) and `OPENROUTER_API_KEY` /
`OPENROUTER_MODEL` (optional `OPENROUTER_IMAGE_MODEL`, `OPENROUTER_VISION_MODEL`).

```bash
pip install -r requirements.comic.txt
python examples/book_example.py book.pdf 1 3   # runs the pipeline synchronously, no Celery
```

### Celery worker

`worker/tasks.py` queues the same jobs on Celery with Redis (`CELERY_BROKER_URL`,
`CELERY_RESULT_BACKEND`, default `redis://localhost:6379/0`). Its tasks write story text with
OpenRouter (`llm_provider="openrouter"`, model from `OPENROUTER_MODEL`); Groq setups keep using
`GROQ_API_KEY` with `llm_provider="groq"`.

```bash
pip install -r requirements.worker.txt        # comic runtime + celery[redis]
pip install -r requirements.txt               # only for the generate_comic task (core.ComicCrafter)
redis-server &                                # or any reachable Redis
celery -A worker.tasks worker --loglevel=info
```

Queue a job from Python with `generate_book_comic.delay("book.pdf", first_chapter=1, last_chapter=3)`.

- **Bubble kinds**: each dialogue line has a `bubble`: `speech`, `thought`, `shout`, `whisper`,
  `broadcast`, `fear` or `song`, each with its own outline, tail and text size. Unknown or missing
  kinds are drawn as speech. The script writer picks one per line.
- **Lettering**: a bundled Hebrew + Latin font (`assets/fonts/Assistant-SemiBold.ttf`), so Latin names
  inside Hebrew text are drawn on any system. Use your own with `RenderOptions(font_path=...)` or
  `render_dialogue(..., font_path=...)`. Captions wrap at 40% of the panel width. They go in the corner
  the vision model picks, unless that corner covers a speaker's head. A caption in the corner read
  second keeps the band above its bottom free of bubbles, so the caption is read first. An optional
  `note` is drawn in the last-read bottom corner.
- **Image quality**: the writer starts every scene with a shot label. Panel 1 must be an establishing
  shot and every page needs at least two different shots; a page that breaks this rule is written once
  more. Image prompts include the comic craft rules, a strong no-text rule and the book's recurring
  props. The pipeline draws a character sheet once per book. Each panel then gets the sheet, the
  previous panel and an optional photo as reference images. A vision check redraws art (up to three draws, the best kept) if the
  model painted text or an extra hand into it; the character sheet is checked the same way. Image and vision costs are counted in `cost_usd`.
- **Cover**: `cover.png` is drawn from `cast.json`'s `cover`, using page one's panels as a reference
  strip. A seam (a second strip stacked on top) is detected and cropped off. Art whose head sits too
  high for the title gets its title block at the bottom instead; a head in the printers' top margin
  (above 8.5% of the height) is drawn again, and the last draw is kept if none clears it. The cover is
  lettered with a shade, a one-line shadowed title, a starring line and a footer, all inside the
  printers' text margin on the printed cover (`cover_lettering.SAFE_TOP`, `SAFE_BOTTOM`, `SAFE_WIDTH`:
  12.7 mm inside the trim after Lulu's and BookPod's cover crops). It is placed first in the PDF.
- **Full-page splash**: `PageRenderer.render_page` takes 3 panels (a vertical strip) or 1 panel (a
  full-page splash, `LayoutType.FULL_PAGE`: one portrait image in the strip's outer frame, with the same
  references and art check, a splash prompt, and at most one caption and one bubble lettered at a strip
  panel's type size). Any other count raises `ValueError`.
- **Print size** (optional): `book_comic.render.print_layouts()` gives 6.875 × 10.5 in pages
  (2063 × 3150 px), and `RenderOptions(dpi=PRINT_DPI)` tags the PNGs at 300 DPI.

`RenderOptions` defaults reproduce the plain renderer: one call per panel, no references and a gray
placeholder when an image fails. Set `fail_on_image_error=True` to raise instead. The pipeline turns on
`sheet_path`, `chain_panels` and `check_art` (`book_comic.pipeline.default_options`). Pass
`options=RenderOptions()` for the plain renderer.

Script fields (all optional; older `cast.json` / `script_NN.json` files still work):

| Field | Where | Meaning |
|---|---|---|
| `props[{name, look}]` | `cast.json` | Recurring objects, drawn the same in every panel and on the cover |
| `language` | `cast.json` | `he`, `en`, ... overrides reading direction (default: detected from the text) |
| `cover{scene, title, starring, footer, title_font}` | `cast.json` | Cover art direction and lettering; `title_font` is a bundled font file name or a font path |
| `dialogue[].bubble` | `script_NN.json` | Bubble kind (default `speech`) |
| `note` | `script_NN.json` panel | Dedication caption in the bottom corner |

Run the tests with `pytest -q` (no network calls; fake clients).

The bundled fonts (Assistant, Rubik) are licensed under the SIL Open Font License 1.1; the licence
texts are in `assets/fonts/`.

## 📖 Documentation

### Project Structure

```
ComicCrafter/
├── src/comiccrafter/
│   ├── agents/              # Multi-agent system
│   │   ├── story_agent.py   # Story decomposition
│   │   ├── prompt_agent.py  # Image prompt generation
│   │   └── layout_agent.py  # Layout planning
│   ├── rag/                 # Character consistency
│   │   ├── character_memory.py
│   │   └── vector_store.py
│   ├── generation/          # Image generation
│   │   ├── image_generator.py
│   │   └── api_clients.py
│   ├── layout/              # Page composition
│   │   ├── panel_layout.py
│   │   └── text_overlay.py
│   ├── utils/               # Utilities
│   │   ├── config.py
│   │   └── logger.py
│   └── core.py              # Main orchestrator
├── tests/                   # Unit tests
├── evaluation/              # Evaluation tools
├── examples/                # Example scripts
├── docs/                    # Documentation
└── requirements.txt
```

### Core Components

#### 1. **StoryAgent**
Analyzes and decomposes stories into comic scenes using LLMs.

```python
from comiccrafter.agents import StoryAgent

agent = StoryAgent()
scenes = agent.decompose_story(story_text, max_scenes=6)
```

#### 2. **PromptAgent**
Generates optimized image prompts from scenes.

```python
from comiccrafter.agents import PromptAgent

agent = PromptAgent()
prompts = agent.generate_prompts(scenes, style="comic book style")
```

#### 3. **LayoutAgent**
Plans optimal panel layouts for pages.

```python
from comiccrafter.agents import LayoutAgent

agent = LayoutAgent()
layouts = agent.plan_adaptive_layout(scenes)
```

#### 4. **CharacterMemory**
Maintains character consistency using RAG.

```python
from comiccrafter.rag import CharacterMemory, Character

memory = CharacterMemory()
character = Character(
    name="Hero",
    appearance="tall warrior with silver armor",
    personality="brave and kind"
)
memory.add_character(character)
```

#### 5. **ImageGenerator**
Orchestrates image generation with consistency.

```python
from comiccrafter.generation import ImageGenerator

generator = ImageGenerator()
panel = generator.generate_panel(
    prompt="knight fighting dragon",
    character_context="tall warrior with silver armor"
)
```

## 🎯 Advanced Usage

### Custom Scenes

```python
from comiccrafter.agents.story_agent import Scene

scenes = [
    Scene(
        description="Hero enters the dark forest",
        characters=["Hero"],
        dialogue=["I must find the ancient sword"],
        action="Walking through misty trees",
        setting="Dark enchanted forest at dusk"
    ),
    # Add more scenes...
]

pages = crafter.generate_from_scenes(scenes)
```

### Custom Layouts

```python
from comiccrafter.layout import LayoutType

# Force specific layout
crafter.layout_agent.create_custom_layout(
    scene_indices=[0, 1, 2, 3],
    layout_type=LayoutType.GRID_2X2
)
```

### API Provider Selection

```python
# Use Gemini instead of Groq
crafter = ComicCrafter(llm_provider="gemini")

# Use different image model
from comiccrafter.generation import HuggingFaceClient

image_client = HuggingFaceClient(model="stabilityai/stable-diffusion-xl-base-1.0")
crafter.image_generator = ImageGenerator(image_client)
```

## 🔧 Configuration

Edit `.env` for configuration:

```env
# Required API Keys
GROQ_API_KEY=your_key
GOOGLE_API_KEY=your_key
HUGGINGFACE_TOKEN=your_token

# Optional: Model Selection
DEFAULT_LLM_MODEL=llama-3.3-70b-versatile
DEFAULT_IMAGE_MODEL=black-forest-labs/FLUX.1-dev
GEMINI_MODEL=gemini-2.0-flash-exp

# Optional: Output Settings
OUTPUT_DIR=./output
MAX_PANELS_PER_PAGE=6
IMAGE_WIDTH=512
IMAGE_HEIGHT=512

# Optional: ChromaDB
CHROMADB_PATH=./data/chroma_db
CHROMADB_COLLECTION=comic_characters
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Groq** for fast Llama 3.3 inference
- **Google** for Gemini API
- **HuggingFace** for free inference API
- **ChromaDB** for vector storage
- **LangChain** for LLM orchestration

## 🐛 Known Issues & Limitations

- Image generation may be slow on free HuggingFace tier
- API rate limits apply to free tiers
- Character consistency depends on model quality
- Best results with clear, descriptive stories

## 📧 Contact

Project Link: [https://github.com/Absirkhan/ComicCrafter](https://github.com/Absirkhan/ComicCrafter)

## 🗺️ Roadmap

- [ ] Support for more image models
- [ ] Advanced panel composition
- [ ] PDF export with multiple pages
- [ ] Web interface
- [ ] Animation support
- [ ] Style transfer options
- [ ] Multi-language support

---

**Made with ❤️ by the ComicCrafter Team**
