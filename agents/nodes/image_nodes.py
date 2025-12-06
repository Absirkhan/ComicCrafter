"""Image generation nodes for LangGraph workflow."""

from typing import TYPE_CHECKING
from PIL import Image
import io
from utils import get_logger

if TYPE_CHECKING:
    from agents.graph_orchestrator import ComicState

logger = get_logger(__name__)


def generate_images_node(state: "ComicState", image_generator, character_memory=None) -> "ComicState":
    """Node: Generate images for all prompts.
    
    Args:
        state: Current workflow state
        image_generator: ImageGenerator instance
        character_memory: CharacterMemory instance for storing generated images
        
    Returns:
        Updated state with generated images
    """
    logger.info("🎨 Node: Generate Images")
    state["images"] = []
    state["failed_images"] = []
    
    for idx, prompt in enumerate(state["prompts"]):
        try:
            logger.info(f"  Generating image {idx + 1}/{len(state['prompts'])}")
            
            # Get character names from the corresponding scene
            scene = state["scenes"][idx] if idx < len(state["scenes"]) else None
            characters = scene.characters if scene else []
            
            logger.info(f"    Scene: {scene.description[:60] if scene else 'None'}...")
            logger.info(f"    Characters in scene: {characters}")
            
            # Retrieve previous images for character consistency (RAG retrieval)
            if character_memory and characters:
                for char_name in characters:
                    logger.info(f"    Looking for reference images for '{char_name}'...")
                    ref_images = character_memory.get_character_reference_images(char_name, n_results=2)
                    if ref_images:
                        logger.info(f"    ✓ Retrieved {len(ref_images)} reference images for '{char_name}'")
                        # Set the most recent reference image
                        image_generator.set_character_reference(char_name, ref_images[0]["image"])
                    else:
                        logger.info(f"    ✗ No reference images found for '{char_name}' (first appearance)")
            
            # ImageGenerator returns PIL Image, convert to bytes
            image = image_generator.generate_panel(
                prompt=prompt.prompt,
                negative_prompt=prompt.negative_prompt,
                characters=characters
            )
            
            # Store generated image in RAG for future consistency
            if character_memory and characters and scene:
                for char_name in characters:
                    try:
                        character_memory.add_character_image(
                            character_name=char_name,
                            image=image,
                            scene_description=scene.description,
                            panel_number=idx + 1
                        )
                        logger.info(f"    Stored image reference for {char_name} in RAG")
                    except Exception as e:
                        logger.warning(f"    Failed to store image reference: {e}")
            
            # Convert PIL Image to bytes
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            image_data = buffer.getvalue()
            state["images"].append(image_data)
        except Exception as e:
            logger.warning(f"  ✗ Failed to generate image {idx + 1}: {e}")
            state["images"].append(None)
            state["failed_images"].append(idx)
    
    state["current_step"] = "generate_images"
    logger.info(f"✓ Generated {len(state['images']) - len(state['failed_images'])}/{len(state['prompts'])} images")
    
    return state


def retry_failed_images_node(state: "ComicState", image_generator) -> "ComicState":
    """Node: Retry generating failed images with modified prompts.
    
    Args:
        state: Current workflow state
        image_generator: ImageGenerator instance
        
    Returns:
        Updated state with retried images
    """
    logger.info("🔄 Node: Retry Failed Images")
    
    for idx in state["failed_images"][:]:  # Copy list to modify during iteration
        if state["retry_count"] >= 2:  # Max 2 retries
            logger.warning(f"  Max retries reached for image {idx + 1}, using placeholder")
            state["images"][idx] = _create_placeholder_image()
            continue
        
        try:
            # Simplify prompt for retry
            original_prompt = state["prompts"][idx].prompt
            simplified_prompt = original_prompt.split(",")[0]  # Take first part only
            
            logger.info(f"  Retry {state['retry_count'] + 1}/2 for image {idx + 1}")
            # ImageGenerator returns PIL Image, convert to bytes
            image = image_generator.generate_panel(prompt=simplified_prompt)
            # Convert PIL Image to bytes
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            image_data = buffer.getvalue()
            state["images"][idx] = image_data
            state["failed_images"].remove(idx)
        except Exception as e:
            logger.warning(f"  ✗ Retry failed for image {idx + 1}: {e}")
    
    state["retry_count"] += 1
    state["current_step"] = "retry_failed_images"
    
    return state


def _create_placeholder_image() -> bytes:
    """Create a placeholder image for failed generations.
    
    Returns:
        PNG image as bytes
    """
    img = Image.new('RGB', (512, 512), color='lightgray')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()
