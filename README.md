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
