"""Layout planning node for LangGraph workflow."""

from typing import TYPE_CHECKING
from utils import get_logger

if TYPE_CHECKING:
    from agents.langgraph_workflow import ComicState

logger = get_logger(__name__)


def plan_layout_node(state: "ComicState", layout_agent) -> "ComicState":
    """Node: Plan panel layouts for comic pages.
    
    Args:
        state: Current workflow state
        layout_agent: LayoutAgent instance
        
    Returns:
        Updated state with layouts
    """
    logger.info("📐 Node: Plan Layout")
    try:
        layouts = layout_agent.plan_layouts(state["scenes"])
        state["layouts"] = layouts
        state["current_step"] = "plan_layout"
        logger.info(f"✓ Planned layout for {len(layouts)} pages")
    except Exception as e:
        logger.error(f"✗ Error planning layout: {e}")
        state["errors"].append(f"Layout planning failed: {str(e)}")
    
    return state
