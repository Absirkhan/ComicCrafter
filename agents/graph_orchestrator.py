"""LangGraph + LangChain integrated workflow for ComicCrafter with stateful multi-agent orchestration."""

from typing import TypedDict, List, Optional, Dict, Any, Literal
from pathlib import Path

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from agents.story_agent import StoryAgent, Scene, Character
from agents.prompt_agent import PromptAgent, ImagePrompt
from agents.layout_agent import LayoutAgent, PageLayout
from generation.image_generator import ImageGenerator
from rag.character_memory import CharacterMemory
from utils import get_logger

# Import node functions
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

logger = get_logger(__name__)


class ComicState(TypedDict):
    """State schema for the comic generation workflow.
    
    This state is passed between nodes and tracks the entire workflow progress.
    """
    # Input
    story_text: str
    style: str
    max_scenes: Optional[int]
    add_dialogue: Optional[bool]  # If True, dialogue in image; if False/None, overlay
    
    # Intermediate results
    scenes: List[Scene]
    characters: List[Character]
    prompts: List[ImagePrompt]
    images: List[bytes]  # Generated image data
    layouts: List[PageLayout]
    
    # Metadata and error tracking
    current_step: str
    retry_count: int
    errors: List[str]
    failed_images: List[int]  # Indices of failed image generations
    
    # Final output
    output_path: Optional[Path]
    success: bool


class ComicGraphOrchestrator:
    """LangGraph-based orchestrator with stateful workflow and conditional routing."""
    
    def __init__(
        self,
        llm_client,
        image_client,
        character_memory: Optional[CharacterMemory] = None,
        output_dir: Optional[Path] = None
    ):
        """Initialize the orchestrator.
        
        Args:
            llm_client: LLM client (GroqClient)
            image_client: Image generation client (HuggingFaceClient)
            character_memory: Character memory system
            output_dir: Directory for saving outputs
        """
        self.llm_client = llm_client
        self.image_client = image_client
        self.character_memory = character_memory or CharacterMemory()
        self.output_dir = output_dir or Path("output")
        
        # Initialize agents
        self.story_agent = StoryAgent(llm_client, self.character_memory)
        self.prompt_agent = PromptAgent(llm_client, self.character_memory)
        self.layout_agent = LayoutAgent()
        self.image_generator = ImageGenerator(image_client)
        
        # Build the workflow graph
        self.workflow = self._build_graph()
        
        logger.info("Initialized ComicGraphOrchestrator with LangGraph workflow")
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow.
        
        Returns:
            Compiled StateGraph
        """
        # Create the graph
        workflow = StateGraph(ComicState)
        
        # Add nodes
        workflow.add_node("decompose_story", self._decompose_story_node)
        workflow.add_node("extract_characters", self._extract_characters_node)
        workflow.add_node("generate_prompts", self._generate_prompts_node)
        workflow.add_node("generate_images", self._generate_images_node)
        workflow.add_node("retry_failed_images", self._retry_failed_images_node)
        workflow.add_node("plan_layout", self._plan_layout_node)
        workflow.add_node("assemble_comic", self._assemble_comic_node)
        workflow.add_node("handle_error", self._handle_error_node)
        
        # Set entry point
        workflow.set_entry_point("decompose_story")
        
        # Add edges (linear flow)
        workflow.add_edge("decompose_story", "extract_characters")
        workflow.add_edge("extract_characters", "generate_prompts")
        workflow.add_edge("generate_prompts", "generate_images")
        
        # Conditional routing after image generation
        workflow.add_conditional_edges(
            "generate_images",
            self._check_image_generation,
            {
                "retry": "retry_failed_images",
                "continue": "plan_layout",
                "error": "handle_error"
            }
        )
        
        # Retry logic
        workflow.add_conditional_edges(
            "retry_failed_images",
            self._check_retry_result,
            {
                "continue": "plan_layout",
                "error": "handle_error"
            }
        )
        
        # Final steps
        workflow.add_edge("plan_layout", "assemble_comic")
        workflow.add_edge("assemble_comic", END)
        workflow.add_edge("handle_error", END)
        
        # Compile the graph
        return workflow.compile()
    
    # ==================== NODE WRAPPER FUNCTIONS ====================
    
    def _decompose_story_node(self, state: ComicState) -> ComicState:
        """Wrapper for decompose_story_node."""
        return decompose_story_node(state, self.story_agent)
    
    def _extract_characters_node(self, state: ComicState) -> ComicState:
        """Wrapper for extract_characters_node."""
        return extract_characters_node(state, self.story_agent)
    
    def _generate_prompts_node(self, state: ComicState) -> ComicState:
        """Wrapper for generate_prompts_node."""
        return generate_prompts_node(state, self.prompt_agent)
    
    def _generate_images_node(self, state: ComicState) -> ComicState:
        """Wrapper for generate_images_node."""
        return generate_images_node(state, self.image_generator, self.character_memory)
    
    def _retry_failed_images_node(self, state: ComicState) -> ComicState:
        """Wrapper for retry_failed_images_node."""
        return retry_failed_images_node(state, self.image_generator)
    
    def _plan_layout_node(self, state: ComicState) -> ComicState:
        """Wrapper for plan_layout_node."""
        return plan_layout_node(state, self.layout_agent)
    
    def _assemble_comic_node(self, state: ComicState) -> ComicState:
        """Wrapper for assemble_comic_node."""
        return assemble_comic_node(state)
    
    def _handle_error_node(self, state: ComicState) -> ComicState:
        """Wrapper for handle_error_node."""
        return handle_error_node(state)
    
    # ==================== ROUTING FUNCTIONS ====================
    
    def _check_image_generation(self, state: ComicState) -> Literal["retry", "continue", "error"]:
        """Check image generation results and decide next step."""
        if state.get("errors"):
            return "error"
        
        failed_count = len(state.get("failed_images", []))
        total_count = len(state.get("prompts", []))
        
        if failed_count == 0:
            return "continue"
        elif failed_count < total_count * 0.5 and state.get("retry_count", 0) < 2:
            # Less than 50% failed and haven't exceeded retries
            return "retry"
        elif failed_count == total_count:
            # All failed
            return "error"
        else:
            # Some failed but continue with what we have
            return "continue"
    
    def _check_retry_result(self, state: ComicState) -> Literal["continue", "error"]:
        """Check retry results and decide next step."""
        if state.get("errors"):
            return "error"
        
        # Continue even if some images still failed (will use placeholders)
        return "continue"
    
    # ==================== HELPER METHODS ====================
    # Note: Placeholder image creation is now in agents/nodes/image_nodes.py
    
    def generate_comic(
        self,
        story_text: str,
        style: str = "comic book",
        max_scenes: Optional[int] = None,
        add_dialogue: bool = False
    ) -> Dict[str, Any]:
        """Generate a comic using the LangGraph workflow.
        
        Args:
            story_text: The story to convert to comic
            style: Visual style for the comic
            max_scenes: Maximum number of scenes
            add_dialogue: If True, include dialogue in generated images
            
        Returns:
            Final state dictionary with results
        """
        logger.info("🚀 Starting LangGraph comic generation workflow")
        logger.info(f"   Dialogue mode: {'in-image' if add_dialogue else 'overlay (post-generation)'}")
        
        # Initialize state
        initial_state: ComicState = {
            "story_text": story_text,
            "style": style,
            "max_scenes": max_scenes,
            "add_dialogue": add_dialogue,
            "scenes": [],
            "characters": [],
            "prompts": [],
            "images": [],
            "layouts": [],
            "current_step": "start",
            "retry_count": 0,
            "errors": [],
            "failed_images": [],
            "output_path": None,
            "success": False
        }
        
        # Run the workflow
        try:
            final_state = self.workflow.invoke(initial_state)
            
            if final_state["success"]:
                logger.info("✅ Comic generation completed successfully")
            else:
                logger.warning("⚠️ Comic generation completed with errors")
            
            return final_state
            
        except Exception as e:
            logger.error(f"❌ Workflow execution failed: {e}")
            initial_state["errors"].append(f"Workflow execution failed: {str(e)}")
            initial_state["success"] = False
            return initial_state
