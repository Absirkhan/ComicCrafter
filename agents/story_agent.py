"""Story Agent for narrative decomposition and scene planning."""

from typing import List, Dict, Any, Optional
import json
from dataclasses import dataclass, asdict

from generation.api_clients import LLMClient, GroqClient
from rag.character_memory import CharacterMemory, Character
from utils import get_logger

logger = get_logger(__name__)


@dataclass
class Scene:
    """Represents a comic scene.
    
    Attributes:
        description: Scene description
        characters: List of character names in the scene
        dialogue: Dialogue lines for the scene
        action: Action description
        setting: Setting/location description
    """
    description: str
    characters: List[str]
    dialogue: List[str]
    action: str
    setting: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class StoryAgent:
    """Agent responsible for story analysis and scene decomposition."""
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        character_memory: Optional[CharacterMemory] = None
    ):
        """Initialize StoryAgent.
        
        Args:
            llm_client: LLM client for text generation
            character_memory: Character memory for consistency
        """
        self.llm = llm_client or GroqClient()
        self.character_memory = character_memory or CharacterMemory()
        logger.info("Initialized StoryAgent")
    
    def decompose_story(
        self,
        story_text: str,
        max_scenes: int = 6
    ) -> List[Scene]:
        """Decompose a story into comic scenes.
        
        Args:
            story_text: Input story text
            max_scenes: Maximum number of scenes to create
            
        Returns:
            List of Scene objects
        """
        logger.info(f"Decomposing story into max {max_scenes} scenes")
        
        prompt = self._create_decomposition_prompt(story_text, max_scenes)
        response = self.llm.generate_text(prompt, max_tokens=2048, temperature=0.7)
        
        scenes = self._parse_scenes(response)
        
        logger.info(f"Decomposed story into {len(scenes)} scenes")
        return scenes
    
    def _create_decomposition_prompt(
        self,
        story_text: str,
        max_scenes: int
    ) -> str:
        """Create prompt for story decomposition.
        
        Args:
            story_text: Input story text
            max_scenes: Maximum number of scenes
            
        Returns:
            Formatted prompt
        """
        prompt = f"""You are a comic book writer. Decompose the following story into {max_scenes} or fewer comic book scenes.

For each scene, provide:
1. A brief description of what happens
2. Characters present in the scene
3. Dialogue lines (if any)
4. Main action
5. Setting/location

Story:
{story_text}

Format your response as a JSON array of scenes. Each scene should have this structure:
{{
    "description": "Brief scene description",
    "characters": ["character1", "character2"],
    "dialogue": ["line1", "line2"],
    "action": "Main action description",
    "setting": "Location description"
}}

Respond with only the JSON array, no additional text."""
        
        return prompt
    
    def _parse_scenes(self, response: str) -> List[Scene]:
        """Parse LLM response into Scene objects.
        
        Args:
            response: LLM response text
            
        Returns:
            List of Scene objects
        """
        try:
            # Try to extract JSON from response
            response = response.strip()
            
            # Find JSON array in response
            start_idx = response.find('[')
            end_idx = response.rfind(']') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                scenes_data = json.loads(json_str)
                
                scenes = []
                for scene_data in scenes_data:
                    scene = Scene(
                        description=scene_data.get("description", ""),
                        characters=scene_data.get("characters", []),
                        dialogue=scene_data.get("dialogue", []),
                        action=scene_data.get("action", ""),
                        setting=scene_data.get("setting", "")
                    )
                    scenes.append(scene)
                
                return scenes
            else:
                logger.error("No JSON array found in response")
                return self._create_fallback_scene(response)
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return self._create_fallback_scene(response)
    
    def _create_fallback_scene(self, text: str) -> List[Scene]:
        """Create a fallback scene when parsing fails.
        
        Args:
            text: Original text
            
        Returns:
            List containing a single Scene
        """
        return [Scene(
            description=text[:200],
            characters=[],
            dialogue=[],
            action="Scene action",
            setting="Scene setting"
        )]
    
    def extract_characters(self, scenes: List[Scene]) -> List[Character]:
        """Extract and create character profiles from scenes.
        
        Args:
            scenes: List of scenes
            
        Returns:
            List of Character objects
        """
        # Collect unique character names
        character_names = set()
        for scene in scenes:
            character_names.update(scene.characters)
        
        logger.info(f"Extracting {len(character_names)} characters")
        
        # Generate character descriptions
        characters = []
        for name in character_names:
            character = self._generate_character_description(name, scenes)
            characters.append(character)
            
            # Store in character memory
            self.character_memory.add_character(character)
        
        return characters
    
    def _generate_character_description(
        self,
        character_name: str,
        scenes: List[Scene]
    ) -> Character:
        """Generate character description using LLM.
        
        Args:
            character_name: Name of the character
            scenes: List of scenes for context
            
        Returns:
            Character object
        """
        # Build context from scenes
        context_parts = []
        for scene in scenes:
            if character_name in scene.characters:
                context_parts.append(f"Scene: {scene.description}")
                if scene.dialogue:
                    context_parts.append(f"Dialogue: {', '.join(scene.dialogue)}")
        
        context = "\n".join(context_parts)
        
        prompt = f"""Based on these scenes, create a detailed character description for "{character_name}".

Context:
{context}

Provide:
1. Physical appearance (for visual consistency in comic generation)
2. Personality traits
3. Role in the story

Format your response as JSON:
{{
    "appearance": "Detailed physical description",
    "personality": "Personality traits",
    "role": "Character's role"
}}

Respond with only the JSON, no additional text."""
        
        try:
            response = self.llm.generate_text(prompt, max_tokens=512, temperature=0.7)
            
            # Parse response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                char_data = json.loads(json_str)
                
                character = Character(
                    name=character_name,
                    appearance=char_data.get("appearance", f"Character named {character_name}"),
                    personality=char_data.get("personality", ""),
                    role=char_data.get("role", "")
                )
                
                logger.debug(f"Generated description for {character_name}")
                return character
        except Exception as e:
            logger.warning(f"Failed to generate character description: {e}")
        
        # Fallback
        return Character(
            name=character_name,
            appearance=f"Character named {character_name}",
            personality="",
            role=""
        )
