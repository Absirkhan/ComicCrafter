# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ComicCrafter is a zero-cost multi-agent AI system for automatic comic generation from text. It uses free AI APIs (Groq, Google Gemini, HuggingFace, local GGML) to transform stories into visual comics with character consistency via RAG-based memory (ChromaDB).

## Development Commands

### Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Install package in editable mode
pip install -e .
```

### Configuration
```bash
# Copy example environment file
cp .env.example .env
# Edit .env with your API keys (GROQ_API_KEY, HUGGINGFACE_TOKEN, etc.)
```

### Running the Application
```bash
# Start FastAPI web server on http://localhost:8000
python api.py

# Alternative: using uvicorn directly
uvicorn api:app --host 0.0.0.0 --port 8000

# Run core module directly (CLI mode)
python core.py <story_file>
```

### API Endpoints
- `GET /` - Web interface
- `POST /api/generate` - Generate comic from text
- `POST /api/workflow` - Execute LangGraph workflow with full visibility
- `GET /api/status/{job_id}` - Check generation status
- `GET /api/output/{filename}` - Download comic page
- `GET /docs` - FastAPI interactive documentation

## High-Level Architecture

### Multi-Agent System with Three Orchestration Modes

ComicCrafter supports three coordination approaches (selected via `core.py` init parameters):

1. **LangGraph Stateful Workflow** (default, recommended) - `use_langgraph=True`
   - Stateful multi-agent orchestration using LangGraph's StateGraph
   - Conditional routing and automatic retry logic
   - Tracks workflow state through `ComicState` TypedDict
   - Graph compiled in `agents/graph_orchestrator.py`

2. **LangChain Tool-Based** - `use_langchain=True, use_langgraph=False`
   - Agent coordination via LangChain tools
   - Implemented in `agents/tool_orchestrator.py`

3. **Direct Agent Coordination** - `use_langchain=False, use_langgraph=False`
   - Sequential agent calls without framework overhead
   - Simpler but less fault-tolerant

### LangGraph Workflow (ComicGraphOrchestrator)

The recommended workflow executes these nodes in sequence:

```
decompose_story → extract_characters → generate_prompts → generate_images
    ↓ (conditional)
retry_failed_images → plan_layout → assemble_comic → END
```

**Node Architecture** (modular, in `agents/nodes/`):
- `story_nodes.py` - Story decomposition and character extraction
- `prompt_nodes.py` - Image prompt generation with character context
- `image_nodes.py` - Image generation with retry logic and placeholder creation
- `layout_nodes.py` - Panel layout planning
- `assembly_nodes.py` - Final comic assembly
- `error_nodes.py` - Error handling

**State Flow**: All nodes operate on `ComicState` TypedDict which tracks:
- Input: `story_text`, `style`, `max_scenes`, `add_dialogue`
- Intermediate: `scenes`, `characters`, `prompts`, `images`, `layouts`
- Metadata: `current_step`, `retry_count`, `errors`, `failed_images`
- Output: `output_path`, `success`

**Conditional Routing**: After `generate_images`, the workflow checks:
- If <50% failed images → retry (max 2 times)
- If all failed → error handling
- Otherwise → continue to layout

### Core Agents

1. **StoryAgent** (`agents/story_agent.py`)
   - Decomposes story text into `Scene` objects using LLM
   - Extracts `Character` objects with appearance and personality
   - Uses character memory for consistency

2. **PromptAgent** (`agents/prompt_agent.py`)
   - Generates optimized image prompts from scenes
   - Injects character descriptions from RAG memory
   - Creates negative prompts for quality control
   - Returns `ImagePrompt` objects

3. **LayoutAgent** (`agents/layout_agent.py`)
   - Plans adaptive page layouts based on scene count
   - Supports multiple layout types: SINGLE, VERTICAL_2, HORIZONTAL_2, GRID_2X2, etc.
   - Returns `PageLayout` objects with scene indices

### RAG-Based Character Memory

**Location**: `rag/character_memory.py`, `rag/vector_store.py`

**Purpose**: Maintains visual consistency across panels by storing and retrieving character descriptions

**Implementation**:
- Uses ChromaDB vector store for similarity search
- `CharacterMemory` class wraps vector operations
- `Character` dataclass stores name, appearance, personality, metadata
- Embeddings generated via sentence-transformers
- Queried by PromptAgent when generating prompts for panels with known characters

**Storage**: ChromaDB persisted to `CHROMADB_PATH` (default: `./data/chroma_db`)

### Image Generation Pipeline

**Location**: `generation/image_generator.py`, `generation/api_clients.py`, `generation/langchain_clients.py`

**Backends** (controlled by `IMAGE_BACKEND` env var):
- `ggml` - Local generation via stable-diffusion.cpp (no rate limits)
- `huggingface` - HuggingFace Inference API (free tier, rate limited)
- `replicate` - Replicate API with advanced features (paid)

**Flow**:
1. `ImageGenerator.generate_panel()` receives prompt + character context
2. Merges prompt with character appearance from RAG
3. Sends to configured backend client
4. Returns PIL Image object
5. LangGraph workflow includes automatic retry on failure

### Page Layout and Assembly

**Location**: `layout/panel_layout.py`, `layout/text_overlay.py`

**LayoutManager**:
- `create_layout()` - Generates panel positions for a layout type
- `compose_page()` - Composites panel images onto page canvas

**TextOverlay**:
- Adds speech bubbles and captions to panels
- `TextBox` dataclass: text, position, type (SPEECH_BUBBLE, CAPTION, etc.)
- Supports dialogue overlay or in-image generation (controlled by `add_dialogue` param)

### Configuration System

**Location**: `utils/config.py`

**Config class** (Pydantic BaseModel) loads from `.env`:
- API keys: `GROQ_API_KEY`, `GOOGLE_API_KEY`, `HUGGINGFACE_TOKEN`, `REPLICATE_API_TOKEN`
- Models: `DEFAULT_LLM_MODEL`, `DEFAULT_IMAGE_MODEL`, `GEMINI_MODEL`
- Backend: `IMAGE_BACKEND` (ggml/huggingface/replicate)
- Storage: `CHROMADB_PATH`, `CHROMADB_COLLECTION`
- Output: `OUTPUT_DIR`, `MAX_PANELS_PER_PAGE`, `IMAGE_WIDTH`, `IMAGE_HEIGHT`

Accessed via `get_config()` singleton pattern.

## Key Design Patterns

### Dialogue Mode (Two Approaches)

1. **In-Image Dialogue** (`add_dialogue=True` in workflow)
   - Dialogue text included in image generation prompt
   - Generated by the model (e.g., "character saying 'Hello'")
   - No post-processing overlay needed

2. **Overlay Dialogue** (`add_dialogue=False` or post-generation)
   - Images generated without dialogue
   - Speech bubbles added via `TextOverlay` after generation
   - Default for backward compatibility

The workflow uses `add_dialogue` flag in `ComicState` to control this behavior.

### Error Handling in LangGraph

- Failed image generations tracked in `state["failed_images"]` (list of indices)
- `retry_failed_images_node` uses simplified prompts for retry
- After max retries, placeholder images created via `_create_placeholder_image()`
- Workflow continues even with partial failures (uses placeholders)
- All errors logged to `state["errors"]` list

### Agent-LLM Client Separation

Agents don't directly instantiate LLM clients. Instead:
- `ComicCrafter` creates LLM client (`LangChainLLMClient` or similar)
- Passes client to agent constructors
- Enables easy swapping of LLM providers without modifying agents

## Important Implementation Notes

### Module Import Structure

All imports in `agents/`, `generation/`, `layout/`, `rag/`, `utils/` are relative (no package prefix). For example:
```python
from agents.story_agent import StoryAgent  # in core.py
from generation.image_generator import ImageGenerator  # in core.py
```

This is because the package is not installed via setup.py but used directly with `pip install -e .` or run from root.

### ChromaDB Persistence

CharacterMemory initializes ChromaDB in persistent mode:
```python
self.client = chromadb.PersistentClient(path=str(chromadb_path))
```
This means character data persists across runs. Call `clear_character_memory()` to reset.

### FastAPI Job Management

`api.py` stores jobs in memory (`jobs` dict). In production, this should use a database. Jobs track:
- `job_id`, `status` (pending/processing/completed/failed)
- `created_at`, `completed_at`
- `output_files` (list of paths)
- `error` message (if failed)

Background tasks use `BackgroundTasks` from FastAPI to avoid blocking requests.

### Scene and Character Data Models

Defined in `agents/story_agent.py`:
```python
@dataclass
class Scene:
    description: str
    characters: List[str]
    dialogue: List[str]
    action: str
    setting: str

@dataclass
class Character:
    name: str
    appearance: str
    personality: str
    role: Optional[str] = None
```

These are serialized/deserialized when using API endpoints.

## Common Development Workflows

### Adding a New LangGraph Node

1. Create node function in appropriate `agents/nodes/*.py` file
2. Add signature: `def my_node(state: ComicState, agent) -> ComicState`
3. Export in `agents/nodes/__init__.py`
4. Add wrapper method in `ComicGraphOrchestrator`
5. Register in `_build_graph()` with `workflow.add_node()`
6. Add edges to connect to workflow

### Changing Image Generation Backend

Edit `.env`:
```bash
IMAGE_BACKEND=ggml  # or huggingface, replicate
```

For GGML, also set:
```bash
SD_CPP_EXECUTABLE=/path/to/sd.exe
SD_MODEL_PATH=/path/to/model.gguf
```

### Debugging LangGraph Workflow

Enable detailed logging in `utils/logger.py` and watch console output. Each node logs entry/exit. Check `state["errors"]` for failure messages.

### Testing API Endpoints

Use FastAPI's built-in docs:
1. Start server: `python api.py`
2. Open browser: `http://localhost:8000/docs`
3. Use "Try it out" for interactive testing

Or use curl:
```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"story_text": "A hero saves the day", "style": "comic book", "max_scenes": 4}'
```

## File Organization Logic

- **agents/** - Multi-agent system (story analysis, prompt generation, layout planning)
- **agents/nodes/** - Modular LangGraph workflow nodes
- **generation/** - Image generation clients and orchestration
- **layout/** - Page composition and text overlay
- **rag/** - RAG-based character consistency (ChromaDB)
- **utils/** - Configuration, logging, helpers
- **core.py** - Main `ComicCrafter` orchestrator class
- **api.py** - FastAPI web application

## Dependencies of Note

- **langgraph** - Stateful multi-agent workflows
- **langchain** - LLM orchestration and tool calling
- **chromadb** - Vector database for character memory
- **sentence-transformers** - Embedding generation
- **Pillow** - Image manipulation
- **fastapi** - Web API framework
- **groq** - Groq API client (Llama 3.3)
- **replicate** - Replicate API client (optional)
