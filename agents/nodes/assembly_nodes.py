"""Comic assembly node for LangGraph workflow."""

import io
from pathlib import Path
from typing import TYPE_CHECKING, List
from PIL import Image, ImageDraw
from utils import get_logger

if TYPE_CHECKING:
    from agents.langgraph_workflow import ComicState

logger = get_logger(__name__)


def assemble_comic_node(state: "ComicState") -> "ComicState":
    """Node: Assemble final comic from images and layouts.
    
    Creates comic pages with up to 5 panels per page, arranged in a grid layout.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with assembly status
    """
    logger.info("📚 Node: Assemble Comic")
    try:
        # Create output directory using absolute path
        output_dir = Path("examples/output").absolute()
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"  Output directory: {output_dir}")
        logger.info(f"  Number of images: {len(state['images'])}")
        
        # Convert image bytes to PIL Images
        panel_images: List[Image.Image] = []
        for idx, image_data in enumerate(state["images"]):
            if image_data is not None:
                image = Image.open(io.BytesIO(image_data))
                panel_images.append(image)
                logger.info(f"  Loaded panel {idx + 1} ({image.size[0]}x{image.size[1]})")
            else:
                logger.warning(f"  ✗ Panel {idx + 1} has no image data")
        
        if not panel_images:
            raise ValueError("No valid images to assemble")
        
        # Create comic pages with max 5 panels per page
        MAX_PANELS_PER_PAGE = 5
        pages_created = 0
        
        for page_num in range(0, len(panel_images), MAX_PANELS_PER_PAGE):
            page_panels = panel_images[page_num:page_num + MAX_PANELS_PER_PAGE]
            page_image = _create_comic_page(page_panels)
            
            # Save page
            page_path = output_dir / f"comic_page_{pages_created + 1}.png"
            page_image.save(page_path, "PNG")
            pages_created += 1
            
            logger.info(f"  ✓ Created page {pages_created} with {len(page_panels)} panels: {page_path}")
        
        state["current_step"] = "assemble_comic"
        state["output_path"] = str(output_dir)
        state["success"] = True
        logger.info(f"✓ Comic assembled successfully - {pages_created} page(s) saved to {output_dir}")
    except Exception as e:
        logger.error(f"✗ Error assembling comic: {e}")
        import traceback
        traceback.print_exc()
        state["errors"].append(f"Comic assembly failed: {str(e)}")
        state["success"] = False
    
    return state


def _create_comic_page(panels: List[Image.Image]) -> Image.Image:
    """Create a comic page with multiple panels arranged in a grid.
    
    Layout patterns based on panel count:
    - 1 panel: Full page
    - 2 panels: 2x1 grid (vertical stack)
    - 3 panels: 2x2 grid with last row having 1 centered panel
    - 4 panels: 2x2 grid
    - 5 panels: 3x2 grid with last row having 1 centered panel
    
    Args:
        panels: List of panel images to arrange
        
    Returns:
        Composite image with all panels arranged
    """
    if not panels:
        raise ValueError("No panels to create page from")
    
    # Page settings
    PAGE_WIDTH = 2480
    PAGE_HEIGHT = 3508  # A4 size at 300 DPI
    MARGIN = 100
    GUTTER = 40  # Space between panels
    BACKGROUND_COLOR = (255, 255, 255)  # White
    BORDER_COLOR = (0, 0, 0)  # Black
    BORDER_WIDTH = 3
    
    # Create blank page
    page = Image.new('RGB', (PAGE_WIDTH, PAGE_HEIGHT), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(page)
    
    # Calculate usable area
    usable_width = PAGE_WIDTH - (2 * MARGIN)
    usable_height = PAGE_HEIGHT - (2 * MARGIN)
    
    num_panels = len(panels)
    
    # Determine grid layout and calculate panel dimensions
    if num_panels == 1:
        # Full page single panel
        rows, cols = 1, 1
        panel_width = usable_width
        panel_height = usable_height
    elif num_panels == 2:
        # 2 panels stacked vertically
        rows, cols = 2, 1
        panel_width = usable_width
        panel_height = (usable_height - GUTTER) // 2
    elif num_panels == 3:
        # 2 on top row, 1 full-width on bottom
        rows = 2
        top_panel_width = (usable_width - GUTTER) // 2
        top_panel_height = (usable_height - GUTTER) // 2
        bottom_panel_width = usable_width
        bottom_panel_height = (usable_height - GUTTER) // 2
    elif num_panels == 4:
        # 2x2 grid
        rows, cols = 2, 2
        panel_width = (usable_width - GUTTER) // 2
        panel_height = (usable_height - GUTTER) // 2
    elif num_panels == 5:
        # 2 on top, 2 in middle, 1 full-width on bottom
        rows = 3
        top_panel_width = (usable_width - GUTTER) // 2
        top_panel_height = (usable_height - (GUTTER * 2)) // 3
        bottom_panel_width = usable_width
        bottom_panel_height = (usable_height - (GUTTER * 2)) // 3
    else:
        rows, cols = 3, 2
        panel_width = (usable_width - GUTTER) // 2
        panel_height = (usable_height - (GUTTER * 2)) // 3
    
    logger.info(f"    Creating page: {num_panels} panels")
    
    # Place panels with specific layouts
    for idx, panel_img in enumerate(panels):
        if num_panels == 3:
            # Custom layout for 3 panels: 2 on top, 1 full-width on bottom
            if idx < 2:
                # Top row panels
                x = MARGIN + (idx * (top_panel_width + GUTTER))
                y = MARGIN
                w, h = top_panel_width, top_panel_height
            else:
                # Bottom full-width panel
                x = MARGIN
                y = MARGIN + top_panel_height + GUTTER
                w, h = bottom_panel_width, bottom_panel_height
        elif num_panels == 5:
            # Custom layout for 5 panels: 2, 2, 1 (full-width)
            if idx < 4:
                row = idx // 2
                col = idx % 2
                x = MARGIN + (col * (top_panel_width + GUTTER))
                y = MARGIN + (row * (top_panel_height + GUTTER))
                w, h = top_panel_width, top_panel_height
            else:
                # Bottom full-width panel
                x = MARGIN
                y = MARGIN + (2 * (top_panel_height + GUTTER))
                w, h = bottom_panel_width, bottom_panel_height
        elif num_panels == 2:
            # Vertical stack
            x = MARGIN
            y = MARGIN + (idx * (panel_height + GUTTER))
            w, h = panel_width, panel_height
        elif num_panels == 4:
            # 2x2 grid
            row = idx // 2
            col = idx % 2
            x = MARGIN + (col * (panel_width + GUTTER))
            y = MARGIN + (row * (panel_height + GUTTER))
            w, h = panel_width, panel_height
        else:
            # Default grid layout
            row = idx // cols
            col = idx % cols
            x = MARGIN + (col * (panel_width + GUTTER))
            y = MARGIN + (row * (panel_height + GUTTER))
            w, h = panel_width, panel_height
        
        # Resize panel to fit while maintaining aspect ratio
        panel_aspect = panel_img.width / panel_img.height
        target_aspect = w / h
        
        if panel_aspect > target_aspect:
            # Image is wider - fit to width
            new_width = w
            new_height = int(w / panel_aspect)
        else:
            # Image is taller - fit to height
            new_height = h
            new_width = int(h * panel_aspect)
        
        panel_resized = panel_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Center the image in the allocated space
        paste_x = x + (w - new_width) // 2
        paste_y = y + (h - new_height) // 2
        
        # Fill background with white
        draw.rectangle([x, y, x + w, y + h], fill=BACKGROUND_COLOR)
        
        # Paste panel
        page.paste(panel_resized, (paste_x, paste_y))
        
        # Draw border around the allocated space
        draw.rectangle(
            [x, y, x + w, y + h],
            outline=BORDER_COLOR,
            width=BORDER_WIDTH
        )
    
    return page
