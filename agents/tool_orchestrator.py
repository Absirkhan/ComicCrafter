"""LangChain Tool-based orchestrator for ComicCrafter."""

from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass

from langchain_core.tools import tool

from agents.story_agent import StoryAgent, Scene, Character
from agents.prompt_agent import PromptAgent, ImagePrompt
from agents.layout_agent import LayoutAgent, PageLayout
from rag.character_memory import CharacterMemory
from utils import get_logger

logger = get_logger(__name__)


@dataclass
class AgentTool:
    """Simple tool wrapper for agent functions."""
    name: str
    func: Callable
    description: str


class ComicToolOrchestrator:
    """LangChain Tool-based orchestrator for comic generation agents."""
    
    def __init__(
        self,
        llm_client,
        character_memory: Optional[CharacterMemory] = None
    ):
        """Initialize the orchestrator.
        
        Args:
            llm_client: LLM client (GroqClient)
            character_memory: Character memory system
        """
        self.llm_client = llm_client
        self.character_memory = character_memory or CharacterMemory()
        
        # Initialize individual agents
        self.story_agent = StoryAgent(llm_client, self.character_memory)
        self.prompt_agent = PromptAgent(llm_client, self.character_memory)
        self.layout_agent = LayoutAgent()
        
        # Create agent tools
        self.tools = self._create_tools()
        
        logger.info("Initialized ComicToolOrchestrator with LangChain tools")
    
    def _create_tools(self) -> List[AgentTool]:
        """Create tools for each agent.
        
        Returns:
            List of AgentTool objects
        """
        tools = [
            AgentTool(
                name="DecomposeStory",
                func=self._decompose_story_tool,
                description=(
                    "Decomposes a story text into structured scenes. "
                    "Input: story_text and max_scenes (optional). "
                    "Returns: List of Scene objects with characters, setting, action, and description."
                )
            ),
            AgentTool(
                name="ExtractCharacters",
                func=self._extract_characters_tool,
                description=(
                    "Extracts and generates detailed character descriptions from scenes. "
                    "Input: scenes (list of Scene objects). "
                    "Returns: List of Character objects with appearance details."
                )
            ),
            AgentTool(
                name="GenerateImagePrompts",
                func=self._generate_prompts_tool,
                description=(
                    "Generates optimized image generation prompts for each scene. "
                    "Input: scenes and style. "
                    "Returns: List of ImagePrompt objects."
                )
            ),
            AgentTool(
                name="PlanLayout",
                func=self._plan_layout_tool,
                description=(
                    "Plans the panel layout for comic pages based on scenes. "
                    "Input: scenes. "
                    "Returns: List of PageLayout objects."
                )
            ),
            AgentTool(
                name="GetCharacterContext",
                func=self._get_character_context_tool,
                description=(
                    "Retrieves character context for maintaining visual consistency. "
                    "Input: character_name. "
                    "Returns: Character appearance description."
                )
            )
        ]
        
        return tools
    
    def _decompose_story_tool(self, input_str: str) -> List[Scene]:
        """Tool wrapper for story decomposition."""
        try:
            # Parse input (expecting "story_text|max_scenes")
            parts = input_str.split("|")
            story_text = parts[0].strip()
            max_scenes = int(parts[1].strip()) if len(parts) > 1 else None
            
            scenes = self.story_agent.decompose_story(story_text, max_scenes)
            logger.info(f"Decomposed story into {len(scenes)} scenes")
            return scenes
        except Exception as e:
            logger.error(f"Error in decompose_story_tool: {e}")
            return []
    
    def _extract_characters_tool(self, scenes: List[Scene]) -> List[Character]:
        """Tool wrapper for character extraction."""
        try:
            characters = self.story_agent.extract_characters(scenes)
            logger.info(f"Extracted {len(characters)} characters")
            return characters
        except Exception as e:
            logger.error(f"Error in extract_characters_tool: {e}")
            return []
    
    def _generate_prompts_tool(self, input_str: str) -> List[ImagePrompt]:
        """Tool wrapper for prompt generation."""
        try:
            # Parse input (expecting "scenes|style")
            parts = input_str.split("|")
            scenes = eval(parts[0].strip())  # Note: In production, use proper serialization
            style = parts[1].strip() if len(parts) > 1 else "comic book style"
            
            prompts = self.prompt_agent.generate_prompts(scenes, style)
            logger.info(f"Generated {len(prompts)} prompts")
            return prompts
        except Exception as e:
            logger.error(f"Error in generate_prompts_tool: {e}")
            return []
    
    def _plan_layout_tool(self, scenes: List[Scene]) -> List[PageLayout]:
        """Tool wrapper for layout planning."""
        try:
            layouts = self.layout_agent.plan_adaptive_layout(scenes)
            logger.info(f"Planned {len(layouts)} page layouts")
            return layouts
        except Exception as e:
            logger.error(f"Error in plan_layout_tool: {e}")
            return []
    
    def _get_character_context_tool(self, character_name: str) -> str:
        """Tool wrapper for character context retrieval."""
        try:
            context = self.character_memory.get_character_context(character_name)
            return context
        except Exception as e:
            logger.error(f"Error in get_character_context_tool: {e}")
            return ""
    
    def execute_tool(self, tool_name: str, input_data: Any) -> Any:
        """Execute a specific tool by name.
        
        Args:
            tool_name: Name of the tool to execute
            input_data: Input data for the tool
            
        Returns:
            Tool execution result
        """
        for tool in self.tools:
            if tool.name == tool_name:
                try:
                    result = tool.func(input_data)
                    logger.info(f"Executed tool '{tool_name}' successfully")
                    return result
                except Exception as e:
                    logger.error(f"Error executing tool '{tool_name}': {e}")
                    raise
        
        raise ValueError(f"Tool '{tool_name}' not found")
    
    def coordinate_comic_generation(
        self,
        story_text: str,
        style: str = "comic book style",
        max_scenes: Optional[int] = None
    ) -> Dict[str, Any]:
        """Coordinate the comic generation process using LangChain agents.
        
        Args:
            story_text: Input story text
            style: Visual style for the comic
            max_scenes: Maximum number of scenes
            
        Returns:
            Dictionary with scenes, characters, prompts, and layouts
        """
        logger.info("Starting LangChain-coordinated comic generation")
        
        # Step 1: Decompose story
        scenes = self.story_agent.decompose_story(story_text, max_scenes)
        logger.info(f"✓ Decomposed into {len(scenes)} scenes")
        
        # Step 2: Extract characters
        characters = self.story_agent.extract_characters(scenes)
        logger.info(f"✓ Extracted {len(characters)} characters")
        
        # Step 3: Generate prompts
        prompts = self.prompt_agent.generate_prompts(scenes, style)
        logger.info(f"✓ Generated {len(prompts)} image prompts")
        
        # Step 4: Plan layouts
        layouts = self.layout_agent.plan_adaptive_layout(scenes)
        logger.info(f"✓ Planned {len(layouts)} page layouts")
        
        return {
            "scenes": scenes,
            "characters": characters,
            "prompts": prompts,
            "layouts": layouts
        }
