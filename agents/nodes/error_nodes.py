"""Error handling node for LangGraph workflow."""

from typing import TYPE_CHECKING
from utils import get_logger

if TYPE_CHECKING:
    from agents.langgraph_workflow import ComicState

logger = get_logger(__name__)


def handle_error_node(state: "ComicState") -> "ComicState":
    """Node: Handle errors and set failure state.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with error status
    """
    logger.error("❌ Node: Handle Error")
    state["current_step"] = "error"
    state["success"] = False
    logger.error(f"Workflow failed with errors: {state['errors']}")
    return state
