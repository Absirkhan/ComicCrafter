"""Prompt generation node for LangGraph workflow."""

from typing import TYPE_CHECKING
from utils import get_logger

if TYPE_CHECKING:
    from agents.langgraph_workflow import ComicState

logger = get_logger(__name__)


def generate_prompts_node(state: "ComicState", prompt_agent) -> "ComicState":
    """Node: Generate image prompts for each scene.
    
    Args:
        state: Current workflow state
        prompt_agent: PromptAgent instance
        
    Returns:
        Updated state with prompts
    """
    logger.info("✍️  Node: Generate Image Prompts")
    try:
        # Check if dialogue should be added to images (not as overlay)
        add_dialogue = state.get("add_dialogue", False)
        
        prompts = prompt_agent.generate_prompts(
            state["scenes"],
            state["style"],
            add_dialogue=add_dialogue
        )
        state["prompts"] = prompts
        state["current_step"] = "generate_prompts"
        logger.info(f"✓ Generated {len(prompts)} image prompts")
    except Exception as e:
        logger.error(f"✗ Error generating prompts: {e}")
        import traceback
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        state["errors"].append(f"Prompt generation failed: {str(e)}")
    
    return state
