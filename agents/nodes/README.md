# LangGraph Nodes Architecture

This document describes the modular node structure for the LangGraph workflow in ComicCrafter.

## Directory Structure

```
agents/
├── nodes/
│   ├── __init__.py              # Exports all node functions
│   ├── story_nodes.py           # Story decomposition & character extraction
│   ├── prompt_nodes.py          # Image prompt generation
│   ├── image_nodes.py           # Image generation & retry logic
│   ├── layout_nodes.py          # Panel layout planning
│   ├── assembly_nodes.py        # Comic assembly
│   └── error_nodes.py           # Error handling
├── langgraph_workflow.py        # Main orchestrator with StateGraph
├── langchain_agents.py          # LangChain tool-based coordination
├── story_agent.py               # Story agent implementation
├── prompt_agent.py              # Prompt agent implementation
└── layout_agent.py              # Layout agent implementation
```

## Node Files

### 1. **story_nodes.py**
**Purpose:** Story analysis and character extraction

**Functions:**
- `decompose_story_node(state, story_agent)` - Breaks story into scenes
- `extract_characters_node(state, story_agent)` - Extracts character descriptions

**Dependencies:** StoryAgent

---

### 2. **prompt_nodes.py**
**Purpose:** Image prompt generation

**Functions:**
- `generate_prompts_node(state, prompt_agent)` - Creates optimized image prompts

**Dependencies:** PromptAgent

---

### 3. **image_nodes.py**
**Purpose:** Image generation and retry logic

**Functions:**
- `generate_images_node(state, image_generator)` - Generates images for all prompts
- `retry_failed_images_node(state, image_generator)` - Retries failed images with simplified prompts
- `_create_placeholder_image()` - Creates placeholder for unrecoverable failures

**Dependencies:** ImageGenerator, PIL.Image

**Features:**
- Automatic retry with simplified prompts
- Max 2 retry attempts
- Placeholder generation for persistent failures

---

### 4. **layout_nodes.py**
**Purpose:** Panel layout planning

**Functions:**
- `plan_layout_node(state, layout_agent)` - Plans page layouts based on scenes

**Dependencies:** LayoutAgent

---

### 5. **assembly_nodes.py**
**Purpose:** Final comic assembly

**Functions:**
- `assemble_comic_node(state)` - Assembles final comic from images and layouts

**Dependencies:** None (stateless)

---

### 6. **error_nodes.py**
**Purpose:** Error handling and failure state management

**Functions:**
- `handle_error_node(state)` - Handles workflow errors gracefully

**Dependencies:** None (stateless)

---

## Workflow Integration

The `ComicGraphOrchestrator` in `langgraph_workflow.py` coordinates these nodes:

```python
from agents.nodes import (
    decompose_story_node,
    extract_characters_node,
    generate_prompts_node,
    generate_images_node,
    retry_failed_images_node,
    plan_layout_node,
    assemble_comic_node,
    handle_error_node
)

# Nodes are wrapped in instance methods for agent access
def _decompose_story_node(self, state):
    return decompose_story_node(state, self.story_agent)
```

## Workflow Graph

```
┌─────────────────┐
│ decompose_story │
└────────┬────────┘
         │
         ▼
┌──────────────────┐
│extract_characters│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│generate_prompts  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│generate_images   │
└────────┬─────────┘
         │
    ┌────┴────┐
    │  Check  │
    └────┬────┘
         │
    ┌────┴────────────────┐
    │                     │
    ▼                     ▼
┌────────────┐      ┌────────────┐
│retry_failed│      │plan_layout │
└─────┬──────┘      └─────┬──────┘
      │                   │
      └─────────┬─────────┘
                ▼
         ┌──────────────┐
         │assemble_comic│
         └──────────────┘
```

## Benefits of Modular Structure

1. **Separation of Concerns**
   - Each node file has a single responsibility
   - Easy to locate and modify specific functionality

2. **Testability**
   - Individual nodes can be tested independently
   - Mock agents can be passed in for unit testing

3. **Reusability**
   - Node functions can be imported and used in different workflows
   - Easy to create custom workflows with different node combinations

4. **Maintainability**
   - Changes to one node don't affect others
   - Clear organization makes codebase easier to navigate

5. **Extensibility**
   - New nodes can be added without modifying existing ones
   - Easy to create alternative implementations

## Adding New Nodes

To add a new node:

1. Create a new file in `agents/nodes/` (e.g., `quality_check_nodes.py`)
2. Implement node function(s):
   ```python
   def quality_check_node(state, quality_checker):
       # Node implementation
       return state
   ```
3. Export in `agents/nodes/__init__.py`:
   ```python
   from .quality_check_nodes import quality_check_node
   __all__ = [..., "quality_check_node"]
   ```
4. Add to workflow in `langgraph_workflow.py`:
   ```python
   workflow.add_node("quality_check", self._quality_check_node)
   ```

## Node Function Signature

All nodes follow this pattern:

```python
def node_function(
    state: ComicState,
    agent_or_generator: Optional[Any] = None
) -> ComicState:
    """Node description.
    
    Args:
        state: Current workflow state
        agent_or_generator: Required agent/generator instance
        
    Returns:
        Updated state
    """
    # Node implementation
    return state
```

## State Schema

Nodes operate on `ComicState` TypedDict:

```python
class ComicState(TypedDict):
    # Input
    story_text: str
    style: str
    max_scenes: Optional[int]
    
    # Intermediate results
    scenes: List[Scene]
    characters: List[Character]
    prompts: List[ImagePrompt]
    images: List[bytes]
    layouts: List[PageLayout]
    
    # Metadata
    current_step: str
    retry_count: int
    errors: List[str]
    failed_images: List[int]
    
    # Output
    output_path: Optional[Path]
    success: bool
```
