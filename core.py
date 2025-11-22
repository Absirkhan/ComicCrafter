"""Core ComicCrafter orchestrator."""

from typing import Optional, List, Dict, Any
from pathlib import Path
from PIL import Image

from agents.story_agent import StoryAgent, Scene
from agents.prompt_agent import PromptAgent, ImagePrompt
from agents.layout_agent import LayoutAgent, PageLayout
from generation.image_generator import ImageGenerator
from generation.api_clients import GroqClient, GeminiClient, HuggingFaceClient
from layout.panel_layout import LayoutManager
from layout.text_overlay import TextOverlay, TextBox, TextType
from rag.character_memory import CharacterMemory
from utils import get_config, get_logger

logger = get_logger(__name__)


class ComicCrafter:
    """Main orchestrator for comic generation."""
    
    def __init__(
        self,
        llm_provider: str = "groq",
        image_provider: str = "huggingface",
        output_dir: Optional[Path] = None
    ):
        """Initialize ComicCrafter.
        
        Args:
            llm_provider: LLM provider ("groq" or "gemini")
            image_provider: Image generation provider ("huggingface")
            output_dir: Directory for output files
        """
        self.config = get_config()
        self.output_dir = output_dir or self.config.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize LLM client
        if llm_provider.lower() == "groq":
            self.llm_client = GroqClient()
        elif llm_provider.lower() == "gemini":
            self.llm_client = GeminiClient()
        else:
            raise ValueError(f"Unknown LLM provider: {llm_provider}")
        
        # Initialize image client
        if image_provider.lower() == "huggingface":
            self.image_client = HuggingFaceClient()
        else:
            raise ValueError(f"Unknown image provider: {image_provider}")
        
        # Initialize components
        self.character_memory = CharacterMemory()
        self.story_agent = StoryAgent(self.llm_client, self.character_memory)
        self.prompt_agent = PromptAgent(self.llm_client, self.character_memory)
        self.layout_agent = LayoutAgent()
        self.image_generator = ImageGenerator(self.image_client)
        self.layout_manager = LayoutManager()
        self.text_overlay = TextOverlay()
        
        logger.info(
            f"Initialized ComicCrafter: LLM={llm_provider}, Image={image_provider}"
        )
    
    def generate_comic(
        self,
        story_text: str,
        style: str = "comic book style",
        max_scenes: Optional[int] = None,
        add_dialogue: bool = True,
        output_name: str = "comic"
    ) -> List[Path]:
        """Generate a complete comic from story text.
        
        Args:
            story_text: Input story text
            style: Visual style for the comic
            max_scenes: Maximum number of scenes (panels)
            add_dialogue: Whether to add dialogue overlays
            output_name: Base name for output files
            
        Returns:
            List of paths to generated comic pages
        """
        logger.info("Starting comic generation")
        
        # Step 1: Decompose story into scenes
        logger.info("Step 1: Decomposing story into scenes")
        scenes = self.story_agent.decompose_story(
            story_text,
            max_scenes=max_scenes or self.config.max_panels_per_page
        )
        
        if not scenes:
            logger.error("No scenes generated from story")
            return []
        
        # Step 2: Extract and store characters
        logger.info("Step 2: Extracting characters")
        characters = self.story_agent.extract_characters(scenes)
        logger.info(f"Extracted {len(characters)} characters")
        
        # Step 3: Generate image prompts
        logger.info("Step 3: Generating image prompts")
        prompts = self.prompt_agent.generate_prompts(scenes, style=style)
        
        # Step 4: Plan layouts
        logger.info("Step 4: Planning page layouts")
        page_layouts = self.layout_agent.plan_adaptive_layout(scenes)
        
        # Step 5: Generate images and compose pages
        logger.info("Step 5: Generating images and composing pages")
        output_paths = self._generate_pages(
            scenes, prompts, page_layouts, add_dialogue, output_name
        )
        
        logger.info(f"Comic generation complete. Created {len(output_paths)} pages")
        return output_paths
    
    def _generate_pages(
        self,
        scenes: List[Scene],
        prompts: List[ImagePrompt],
        page_layouts: List[PageLayout],
        add_dialogue: bool,
        output_name: str
    ) -> List[Path]:
        """Generate and compose comic pages.
        
        Args:
            scenes: List of Scene objects
            prompts: List of ImagePrompt objects
            page_layouts: List of PageLayout objects
            add_dialogue: Whether to add dialogue
            output_name: Base name for output files
            
        Returns:
            List of paths to generated pages
        """
        output_paths = []
        
        for page_num, page_layout in enumerate(page_layouts):
            logger.info(f"Generating page {page_num + 1}/{len(page_layouts)}")
            
            # Get prompts for this page
            page_prompts = [prompts[i] for i in page_layout.scene_indices]
            page_scenes = [scenes[i] for i in page_layout.scene_indices]
            
            # Generate panel images
            panel_images = []
            for prompt in page_prompts:
                panel = self.image_generator.generate_panel(
                    prompt=prompt.prompt,
                    character_context=prompt.character_context,
                    negative_prompt=prompt.negative_prompt
                )
                panel_images.append(panel)
            
            # Add dialogue overlays if requested
            if add_dialogue:
                panel_images = self._add_dialogue_to_panels(
                    panel_images, page_scenes
                )
            
            # Create layout and compose page
            layout = self.layout_manager.create_layout(
                page_layout.layout_type,
                num_panels=page_layout.num_panels
            )
            
            page_image = self.layout_manager.compose_page(
                panels=panel_images,
                layout=layout
            )
            
            # Save page
            page_path = self.output_dir / f"{output_name}_page_{page_num + 1:03d}.png"
            page_image.save(page_path, format="PNG", optimize=True)
            output_paths.append(page_path)
            
            logger.info(f"Saved page to {page_path}")
        
        return output_paths
    
    def _add_dialogue_to_panels(
        self,
        panels: List[Image.Image],
        scenes: List[Scene]
    ) -> List[Image.Image]:
        """Add dialogue overlays to panels.
        
        Args:
            panels: List of panel images
            scenes: List of Scene objects
            
        Returns:
            List of panels with dialogue overlays
        """
        result_panels = []
        
        for panel, scene in zip(panels, scenes):
            if scene.dialogue:
                # Create text boxes for dialogue
                text_boxes = []
                panel_width = panel.width
                panel_height = panel.height
                
                # Position text boxes
                num_lines = len(scene.dialogue)
                for i, line in enumerate(scene.dialogue):
                    # Alternate positions for multiple dialogue lines
                    if num_lines == 1:
                        x = panel_width // 2
                        y = panel_height - 60
                    elif i % 2 == 0:
                        x = panel_width // 3
                        y = panel_height - 60 - (i // 2) * 80
                    else:
                        x = 2 * panel_width // 3
                        y = panel_height - 60 - (i // 2) * 80
                    
                    text_box = TextBox(
                        text=line,
                        x=x,
                        y=y,
                        text_type=TextType.SPEECH_BUBBLE,
                        max_width=min(200, panel_width - 40)
                    )
                    text_boxes.append(text_box)
                
                # Add text overlays
                panel_with_text = self.text_overlay.add_text_to_panel(
                    panel, text_boxes
                )
                result_panels.append(panel_with_text)
            else:
                result_panels.append(panel)
        
        return result_panels
    
    def generate_from_scenes(
        self,
        scenes: List[Scene],
        style: str = "comic book style",
        add_dialogue: bool = True,
        output_name: str = "comic"
    ) -> List[Path]:
        """Generate comic from pre-defined scenes.
        
        Args:
            scenes: List of Scene objects
            style: Visual style
            add_dialogue: Whether to add dialogue overlays
            output_name: Base name for output files
            
        Returns:
            List of paths to generated comic pages
        """
        logger.info(f"Generating comic from {len(scenes)} scenes")
        
        # Extract characters
        characters = self.story_agent.extract_characters(scenes)
        
        # Generate prompts
        prompts = self.prompt_agent.generate_prompts(scenes, style=style)
        
        # Plan layouts
        page_layouts = self.layout_agent.plan_adaptive_layout(scenes)
        
        # Generate pages
        output_paths = self._generate_pages(
            scenes, prompts, page_layouts, add_dialogue, output_name
        )
        
        return output_paths
    
    def clear_character_memory(self) -> None:
        """Clear all character data from memory."""
        self.character_memory.clear_memory()
        logger.info("Cleared character memory")


def main():
    """Main entry point for CLI."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: comiccrafter <story_file>")
        sys.exit(1)
    
    story_file = Path(sys.argv[1])
    if not story_file.exists():
        print(f"Error: Story file not found: {story_file}")
        sys.exit(1)
    
    story_text = story_file.read_text(encoding="utf-8")
    
    crafter = ComicCrafter()
    output_paths = crafter.generate_comic(story_text)
    
    print(f"\nGenerated {len(output_paths)} comic pages:")
    for path in output_paths:
        print(f"  - {path}")


if __name__ == "__main__":
    main()
