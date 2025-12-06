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
        style: str = "comic book style",
        add_dialogue: bool = False
    ) -> List[ImagePrompt]:
        """Generate image prompts from scenes.
        
        Args:
            scenes: List of Scene objects
            style: Visual style description
            add_dialogue: If True, includes dialogue boxes in the image generation
            
        Returns:
            List of ImagePrompt objects
        """
        logger.info(f"Generating image prompts for {len(scenes)} scenes (dialogue={'in-image' if add_dialogue else 'post-overlay'})")
        
        prompts = []
        for i, scene in enumerate(scenes):
            prompt = self._generate_scene_prompt(scene, i, style, add_dialogue)
            prompts.append(prompt)
        
        logger.info(f"Generated {len(prompts)} image prompts")
        return prompts
    
    def _generate_scene_prompt(
        self,
        scene: Scene,
        scene_index: int,
        style: str,
        add_dialogue: bool = False
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
        
        # Get character contexts FIRST for consistency
        character_contexts = []
        character_descriptions = []
        
        logger.info(f"Scene {scene_index} characters: {scene.characters}")
        
        for char_name in scene.characters:
            # Normalize character name (case-insensitive, strip whitespace)
            normalized_name = char_name.strip()
            
            character = self.character_memory.get_character(normalized_name)
            if character:
                # Extract detailed visual features for consistency
                char_desc = f"{normalized_name}: {character.appearance} - MAINTAIN EXACT SAME APPEARANCE"
                character_descriptions.append(char_desc)
                logger.info(f"  Using stored description for {normalized_name}: {character.appearance[:80]}...")
                
                context = self.character_memory.get_character_context(
                    normalized_name,
                    scene.description
                )
                if context:
                    character_contexts.append(context)
            else:
                # First appearance - use generic description
                logger.info(f"  No stored character for '{normalized_name}' (first appearance)")
                character_descriptions.append(f"{normalized_name} (new character)")
        
        # Add character descriptions at the START for emphasis
        if character_descriptions:
            prompt_parts.append(f"Characters: {', '.join(character_descriptions)}")
        
        # Add setting/location
        if scene.setting:
            prompt_parts.append(f"Setting: {scene.setting}")
        
        # Add action
        if scene.action:
            prompt_parts.append(f"Action: {scene.action}")
        else:
            prompt_parts.append(f"Scene: {scene.description}")
        
        # Add dialogue if requested (for in-image speech bubbles)
        if add_dialogue and scene.dialogue:
            # Handle both string lists and dialogue objects
            dialogue_texts = []
            for d in scene.dialogue:
                if isinstance(d, str):
                    dialogue_texts.append(d)
                elif hasattr(d, 'text'):
                    dialogue_texts.append(d.text)
            
            if dialogue_texts:
                dialogue_instruction = f"MUST INCLUDE VISIBLE SPEECH BUBBLES with clear readable text: {' | '.join(dialogue_texts)} - white bubbles with black text, positioned near character faces"
                prompt_parts.insert(0, dialogue_instruction)  # Put at the beginning for emphasis
                logger.info(f"  Adding dialogue to image prompt: {len(dialogue_texts)} bubbles: {dialogue_texts}")
        
        # Combine character contexts
        character_context = ", ".join(character_contexts) if character_contexts else ""
        
        # Use LLM to enhance prompt
        base_prompt = ", ".join(prompt_parts)
        enhanced_prompt = self._enhance_prompt(base_prompt, scene, style, character_descriptions, add_dialogue)
        
        # Create negative prompt with consistency enforcements
        negative_prompt = self._create_negative_prompt(allow_speech_bubbles=add_dialogue)
        
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
        style: str,
        character_descriptions: List[str] = None,
        add_dialogue: bool = False
    ) -> str:
        """Enhance prompt using LLM.
        
        Args:
            base_prompt: Base prompt text
            scene: Scene object
            style: Visual style
            character_descriptions: List of detailed character descriptions
            add_dialogue: If True, emphasizes speech bubble rendering
            
        Returns:
            Enhanced prompt
        """
        char_emphasis = ""
        if character_descriptions:
            char_emphasis = f"\n\nCRITICAL - Character Consistency (maintain EXACT appearance):\n" + "\n".join(character_descriptions)
        
        dialogue_instruction = ""
        if add_dialogue and scene.dialogue:
            dialogue_instruction = "\n7. **CRITICAL**: Include white comic-style speech bubbles with clear, legible black text showing the EXACT dialogue (use comic sans or similar readable font). Position bubbles near the speaking character's head without covering their face. The text must be clearly visible and readable."
        
        enhancement_prompt = f"""You are an expert at creating image generation prompts for comic books with consistent character appearance.

Scene Description: {scene.description}
Setting: {scene.setting}
Action: {scene.action}
Characters: {', '.join(scene.characters)}{char_emphasis}

Base prompt: {base_prompt}
Style: {style}

Create a detailed, vivid image generation prompt that:
1. MAINTAINS EXACT character appearance descriptions (hair, face, clothing, body type)
2. Describes the visual composition and scene
3. Captures the mood and atmosphere
4. Specifies camera angle and framing
5. Includes the style "{style}"
6. Uses phrases like "same character as before" or "consistent appearance"{dialogue_instruction}

IMPORTANT: Keep character visual descriptions IDENTICAL across all scenes.
Keep it under 200 words. Respond with only the prompt, no additional text."""
        
        try:
            enhanced = self.llm.generate_text(
                enhancement_prompt,
                max_tokens=256,
                temperature=0.7  # Lower temperature for more consistency
            )
            return enhanced.strip()
        except Exception as e:
            logger.warning(f"Failed to enhance prompt: {e}")
            return f"{base_prompt}, {style}"
    
    def _create_negative_prompt(self, allow_speech_bubbles: bool = False) -> str:
        """Create a standard negative prompt with character consistency enforcement.
        
        Args:
            allow_speech_bubbles: If True, removes 'speech bubbles' from negative prompt
        
        Returns:
            Negative prompt string
        """
        negative_items = [
            "blurry", "low quality", "distorted", "deformed", "ugly", "bad anatomy",
            "bad proportions", "watermark", "signature", "out of frame",
            "multiple panels",
            "different face", "inconsistent appearance", "changing features",
            "multiple different people", "varying character design"
        ]
        
        # Only exclude speech bubbles if we're NOT generating them in-image
        if not allow_speech_bubbles:
            negative_items.insert(10, "speech bubbles")
            negative_items.insert(10, "text")
        
        return ", ".join(negative_items)
    
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
