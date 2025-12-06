"""Story-related nodes for LangGraph workflow."""

from typing import TYPE_CHECKING
from utils import get_logger

if TYPE_CHECKING:
    from agents.graph_orchestrator import ComicState

logger = get_logger(__name__)


def decompose_story_node(state: "ComicState", story_agent) -> "ComicState":
    """Node: Decompose story into scenes.
    
    Args:
        state: Current workflow state
        story_agent: StoryAgent instance
        
    Returns:
        Updated state with scenes
    """
    logger.info("📖 Node: Decompose Story")
    try:
        scenes = story_agent.decompose_story(
            state["story_text"],
            state.get("max_scenes")
        )
        state["scenes"] = scenes
        state["current_step"] = "decompose_story"
        logger.info(f"✓ Decomposed into {len(scenes)} scenes")
    except Exception as e:
        logger.error(f"✗ Error decomposing story: {e}")
        state["errors"].append(f"Story decomposition failed: {str(e)}")
    
    return state


def extract_characters_node(state: "ComicState", story_agent) -> "ComicState":
    """Node: Extract and generate character descriptions.
    
    Args:
        state: Current workflow state
        story_agent: StoryAgent instance
        
    Returns:
        Updated state with characters
    """
    logger.info("👤 Node: Extract Characters")
    try:
        characters = story_agent.extract_characters(state["scenes"])
        state["characters"] = characters
        state["current_step"] = "extract_characters"
        logger.info(f"✓ Extracted {len(characters)} characters")
    except Exception as e:
        logger.error(f"✗ Error extracting characters: {e}")
        state["errors"].append(f"Character extraction failed: {str(e)}")
    
    return state
