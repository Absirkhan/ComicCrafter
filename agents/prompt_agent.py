"""Prompt Agent for generating image prompts from scenes."""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from generation.api_clients import LLMClient, GroqClient
from rag.character_memory import CharacterMemory
from agents.story_agent import Scene
from utils import get_logger

logger = get_logger(__name__)


@dataclass
class ImagePrompt:
    """Image generation prompt for a panel.
    
    Attributes:
        prompt: Main image generation prompt
        character_context: Character consistency context
        negative_prompt: Negative prompt for guidance
        scene_index: Index of the source scene
    """
    prompt: str
    character_context: str
    negative_prompt: str = ""
    scene_index: int = 0


class PromptAgent:
    """Agent responsible for converting scenes to image generation prompts."""
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        character_memory: Optional[CharacterMemory] = None
    ):
        """Initialize PromptAgent.
        
        Args:
            llm_client: LLM client for prompt generation
            character_memory: Character memory for consistency
        """
        self.llm = llm_client or GroqClient()
        self.character_memory = character_memory or CharacterMemory()
        logger.info("Initialized PromptAgent")
    
    def generate_prompts(
        self,
        scenes: List[Scene],
        style: str = "comic book style"
    ) -> List[ImagePrompt]:
        """Generate image prompts from scenes.
        
        Args:
            scenes: List of Scene objects
            style: Visual style description
            
        Returns:
            List of ImagePrompt objects
        """
        logger.info(f"Generating image prompts for {len(scenes)} scenes")
        
        prompts = []
        for i, scene in enumerate(scenes):
            prompt = self._generate_scene_prompt(scene, i, style)
            prompts.append(prompt)
        
        logger.info(f"Generated {len(prompts)} image prompts")
        return prompts
    
    def _generate_scene_prompt(
        self,
        scene: Scene,
        scene_index: int,
        style: str
    ) -> ImagePrompt:
        """Generate image prompt for a single scene.
        
        Args:
            scene: Scene object
            scene_index: Index of the scene
            style: Visual style
            
        Returns:
            ImagePrompt object
        """
        # Build base prompt from scene
        prompt_parts = []
        
        # Add setting/location
        if scene.setting:
            prompt_parts.append(f"Setting: {scene.setting}")
        
        # Add action
        if scene.action:
            prompt_parts.append(f"Action: {scene.action}")
        else:
            prompt_parts.append(f"Scene: {scene.description}")
        
        # Get character contexts
        character_contexts = []
        for char_name in scene.characters:
            context = self.character_memory.get_character_context(
                char_name,
                scene.description
            )
            if context:
                character_contexts.append(f"{char_name}: {context}")
        
        # Combine character contexts
        character_context = ", ".join(character_contexts) if character_contexts else ""
        
        # Use LLM to enhance prompt
        base_prompt = ", ".join(prompt_parts)
        enhanced_prompt = self._enhance_prompt(base_prompt, scene, style)
        
        # Create negative prompt
        negative_prompt = self._create_negative_prompt()
        
        logger.debug(f"Generated prompt for scene {scene_index}: {enhanced_prompt[:100]}")
        
        return ImagePrompt(
            prompt=enhanced_prompt,
            character_context=character_context,
            negative_prompt=negative_prompt,
            scene_index=scene_index
        )
    
    def _enhance_prompt(
        self,
        base_prompt: str,
        scene: Scene,
        style: str
    ) -> str:
        """Enhance prompt using LLM.
        
        Args:
            base_prompt: Base prompt text
            scene: Scene object
            style: Visual style
            
        Returns:
            Enhanced prompt
        """
        enhancement_prompt = f"""You are an expert at creating image generation prompts for comic books.

Scene Description: {scene.description}
Setting: {scene.setting}
Action: {scene.action}
Characters: {', '.join(scene.characters)}

Base prompt: {base_prompt}
Style: {style}

Create a detailed, vivid image generation prompt that:
1. Describes the visual composition
2. Captures the mood and atmosphere
3. Specifies camera angle and framing
4. Includes the style "{style}"
5. Is optimized for image generation AI (be specific about visual elements)

Keep it under 150 words. Respond with only the prompt, no additional text."""
        
        try:
            enhanced = self.llm.generate_text(
                enhancement_prompt,
                max_tokens=256,
                temperature=0.8
            )
            return enhanced.strip()
        except Exception as e:
            logger.warning(f"Failed to enhance prompt: {e}")
            return f"{base_prompt}, {style}"
    
    def _create_negative_prompt(self) -> str:
        """Create a standard negative prompt.
        
        Returns:
            Negative prompt string
        """
        return (
            "blurry, low quality, distorted, deformed, ugly, bad anatomy, "
            "bad proportions, watermark, signature, text, out of frame, "
            "multiple panels, speech bubbles"
        )
    
    def refine_prompt_for_character(
        self,
        prompt: ImagePrompt,
        character_name: str
    ) -> ImagePrompt:
        """Refine a prompt to focus on a specific character.
        
        Args:
            prompt: Original ImagePrompt
            character_name: Character to focus on
            
        Returns:
            Refined ImagePrompt
        """
        character = self.character_memory.get_character(character_name)
        
        if not character:
            logger.warning(f"Character not found: {character_name}")
            return prompt
        
        # Add character details to prompt
        refined_prompt = f"{prompt.prompt}, focusing on {character_name}"
        character_context = character.appearance
        
        logger.debug(f"Refined prompt for character: {character_name}")
        
        return ImagePrompt(
            prompt=refined_prompt,
            character_context=character_context,
            negative_prompt=prompt.negative_prompt,
            scene_index=prompt.scene_index
        )
    
    def batch_enhance_prompts(
        self,
        prompts: List[ImagePrompt]
    ) -> List[ImagePrompt]:
        """Apply consistency checks and enhancements to a batch of prompts.
        
        Args:
            prompts: List of ImagePrompt objects
            
        Returns:
            List of enhanced ImagePrompt objects
        """
        logger.info(f"Batch enhancing {len(prompts)} prompts")
        
        # For now, return as-is (could add cross-prompt consistency checks)
        return prompts
