"""Image generation orchestrator for comic panels."""

from typing import Optional, List, Dict, Any
from pathlib import Path
from io import BytesIO
from PIL import Image
import numpy as np

from generation.api_clients import HuggingFaceClient
from utils import get_config, get_logger

logger = get_logger(__name__)


class ImageGenerator:
    """Orchestrates image generation for comic panels."""
    
    def __init__(
        self,
        image_client: Optional[HuggingFaceClient] = None,
        width: Optional[int] = None,
        height: Optional[int] = None
    ):
        """Initialize ImageGenerator.
        
        Args:
            image_client: HuggingFace client for image generation
            width: Image width in pixels
            height: Image height in pixels
        """
        config = get_config()
        self.client = image_client or HuggingFaceClient()
        self.width = width or config.image_width
        self.height = height or config.image_height
        logger.info(f"Initialized ImageGenerator ({self.width}x{self.height})")
    
    def generate_panel(
        self,
        prompt: str,
        character_context: Optional[str] = None,
        style_tags: Optional[List[str]] = None,
        negative_prompt: Optional[str] = None,
        **kwargs
    ) -> Image.Image:
        """Generate a single comic panel image.
        
        Args:
            prompt: Base image generation prompt
            character_context: Additional character consistency context
            style_tags: Style tags to append to prompt
            negative_prompt: Negative prompt for guidance
            **kwargs: Additional generation parameters
            
        Returns:
            Generated PIL Image
        """
        # Build enhanced prompt
        enhanced_prompt = self._build_prompt(prompt, character_context, style_tags)
        
        # Set default negative prompt if not provided
        if not negative_prompt:
            negative_prompt = (
                "blurry, low quality, distorted, deformed, ugly, bad anatomy, "
                "watermark, signature, text"
            )
        
        logger.info(f"Generating panel with prompt: {enhanced_prompt[:100]}...")
        
        try:
            # Generate image
            image_bytes = self.client.generate_image(
                prompt=enhanced_prompt,
                negative_prompt=negative_prompt,
                **kwargs
            )
            
            # Convert to PIL Image
            image = Image.open(BytesIO(image_bytes))
            
            # Resize to target dimensions
            image = image.resize((self.width, self.height), Image.Resampling.LANCZOS)
            
            logger.info("Panel generated successfully")
            return image
            
        except Exception as e:
            logger.error(f"Failed to generate panel: {e}")
            # Return placeholder image on failure
            return self._create_placeholder()
    
    def generate_panels(
        self,
        prompts: List[str],
        character_contexts: Optional[List[str]] = None,
        style_tags: Optional[List[str]] = None,
        **kwargs
    ) -> List[Image.Image]:
        """Generate multiple comic panels.
        
        Args:
            prompts: List of image generation prompts
            character_contexts: List of character contexts (one per prompt)
            style_tags: Style tags to apply to all prompts
            **kwargs: Additional generation parameters
            
        Returns:
            List of generated PIL Images
        """
        if character_contexts is None:
            character_contexts = [None] * len(prompts)
        
        if len(character_contexts) != len(prompts):
            raise ValueError(
                f"Number of character contexts ({len(character_contexts)}) "
                f"must match number of prompts ({len(prompts)})"
            )
        
        panels = []
        for i, (prompt, context) in enumerate(zip(prompts, character_contexts)):
            logger.info(f"Generating panel {i+1}/{len(prompts)}")
            panel = self.generate_panel(
                prompt=prompt,
                character_context=context,
                style_tags=style_tags,
                **kwargs
            )
            panels.append(panel)
        
        return panels
    
    def _build_prompt(
        self,
        base_prompt: str,
        character_context: Optional[str],
        style_tags: Optional[List[str]]
    ) -> str:
        """Build enhanced prompt with context and style.
        
        Args:
            base_prompt: Base prompt text
            character_context: Character consistency context
            style_tags: Style tags to add
            
        Returns:
            Enhanced prompt string
        """
        prompt_parts = []
        
        # Add base prompt
        prompt_parts.append(base_prompt)
        
        # Add character context
        if character_context:
            prompt_parts.append(character_context)
        
        # Add comic book style by default
        prompt_parts.append("comic book style, graphic novel art")
        
        # Add custom style tags
        if style_tags:
            prompt_parts.extend(style_tags)
        
        # Add quality tags
        prompt_parts.append("high quality, detailed, professional")
        
        return ", ".join(prompt_parts)
    
    def _create_placeholder(self) -> Image.Image:
        """Create a placeholder image when generation fails.
        
        Returns:
            Placeholder PIL Image
        """
        # Create a gray placeholder with text
        image = Image.new("RGB", (self.width, self.height), color=(200, 200, 200))
        logger.warning("Created placeholder image")
        return image
    
    def save_panel(self, panel: Image.Image, output_path: Path) -> None:
        """Save a panel image to disk.
        
        Args:
            panel: PIL Image to save
            output_path: Path to save the image
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        panel.save(output_path, format="PNG", optimize=True)
        logger.info(f"Saved panel to {output_path}")
    
    def save_panels(
        self,
        panels: List[Image.Image],
        output_dir: Path,
        prefix: str = "panel"
    ) -> List[Path]:
        """Save multiple panels to disk.
        
        Args:
            panels: List of PIL Images to save
            output_dir: Directory to save images
            prefix: Filename prefix
            
        Returns:
            List of saved file paths
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        paths = []
        for i, panel in enumerate(panels):
            path = output_dir / f"{prefix}_{i+1:03d}.png"
            self.save_panel(panel, path)
            paths.append(path)
        
        return paths
