"""Panel layout and comic page composition."""

from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from PIL import Image, ImageDraw
import numpy as np

from utils import get_config, get_logger

logger = get_logger(__name__)


class LayoutType(Enum):
    """Comic page layout types."""
    GRID_2X2 = "grid_2x2"
    GRID_2X3 = "grid_2x3"
    GRID_3X2 = "grid_3x2"
    GRID_3X3 = "grid_3x3"
    VERTICAL_STRIP = "vertical_strip"
    HORIZONTAL_STRIP = "horizontal_strip"
    CUSTOM = "custom"


@dataclass
class PanelLayout:
    """Defines the layout of a comic panel.
    
    Attributes:
        x: X-coordinate of panel (pixels)
        y: Y-coordinate of panel (pixels)
        width: Panel width (pixels)
        height: Panel height (pixels)
        border_width: Width of panel border
        padding: Internal padding
    """
    x: int
    y: int
    width: int
    height: int
    border_width: int = 3
    padding: int = 10
    
    def get_content_area(self) -> Tuple[int, int, int, int]:
        """Get the content area inside borders and padding.
        
        Returns:
            Tuple of (x, y, width, height) for content
        """
        content_x = self.x + self.border_width + self.padding
        content_y = self.y + self.border_width + self.padding
        content_width = self.width - 2 * (self.border_width + self.padding)
        content_height = self.height - 2 * (self.border_width + self.padding)
        return content_x, content_y, content_width, content_height


class LayoutManager:
    """Manages comic page layouts and composition."""
    
    def __init__(
        self,
        page_width: int = 2480,
        page_height: int = 3508,
        margin: int = 100,
        gutter: int = 20
    ):
        """Initialize LayoutManager.
        
        Args:
            page_width: Page width in pixels (default: A4 at 300dpi)
            page_height: Page height in pixels (default: A4 at 300dpi)
            margin: Margin around page edges
            gutter: Space between panels
        """
        self.page_width = page_width
        self.page_height = page_height
        self.margin = margin
        self.gutter = gutter
        
        logger.info(
            f"Initialized LayoutManager: {page_width}x{page_height}px, "
            f"margin={margin}px, gutter={gutter}px"
        )
    
    def create_layout(
        self,
        layout_type: LayoutType,
        num_panels: Optional[int] = None
    ) -> List[PanelLayout]:
        """Create a panel layout for a page.
        
        Args:
            layout_type: Type of layout to create
            num_panels: Number of panels (for custom layouts)
            
        Returns:
            List of PanelLayout objects
        """
        if layout_type == LayoutType.GRID_2X2:
            return self._create_grid_layout(2, 2)
        elif layout_type == LayoutType.GRID_2X3:
            return self._create_grid_layout(2, 3)
        elif layout_type == LayoutType.GRID_3X2:
            return self._create_grid_layout(3, 2)
        elif layout_type == LayoutType.GRID_3X3:
            return self._create_grid_layout(3, 3)
        elif layout_type == LayoutType.VERTICAL_STRIP:
            return self._create_strip_layout(num_panels or 4, vertical=True)
        elif layout_type == LayoutType.HORIZONTAL_STRIP:
            return self._create_strip_layout(num_panels or 3, vertical=False)
        else:
            logger.warning(f"Unknown layout type: {layout_type}, using 2x3 grid")
            return self._create_grid_layout(2, 3)
    
    def _create_grid_layout(self, cols: int, rows: int) -> List[PanelLayout]:
        """Create a uniform grid layout.
        
        Args:
            cols: Number of columns
            rows: Number of rows
            
        Returns:
            List of PanelLayout objects
        """
        content_width = self.page_width - 2 * self.margin
        content_height = self.page_height - 2 * self.margin
        
        panel_width = (content_width - (cols - 1) * self.gutter) // cols
        panel_height = (content_height - (rows - 1) * self.gutter) // rows
        
        panels = []
        for row in range(rows):
            for col in range(cols):
                x = self.margin + col * (panel_width + self.gutter)
                y = self.margin + row * (panel_height + self.gutter)
                
                panel = PanelLayout(x=x, y=y, width=panel_width, height=panel_height)
                panels.append(panel)
        
        logger.debug(f"Created {cols}x{rows} grid layout with {len(panels)} panels")
        return panels
    
    def _create_strip_layout(
        self,
        num_panels: int,
        vertical: bool = True
    ) -> List[PanelLayout]:
        """Create a strip layout (vertical or horizontal).
        
        Args:
            num_panels: Number of panels
            vertical: True for vertical strip, False for horizontal
            
        Returns:
            List of PanelLayout objects
        """
        content_width = self.page_width - 2 * self.margin
        content_height = self.page_height - 2 * self.margin
        
        panels = []
        
        if vertical:
            panel_width = content_width
            panel_height = (content_height - (num_panels - 1) * self.gutter) // num_panels
            
            for i in range(num_panels):
                x = self.margin
                y = self.margin + i * (panel_height + self.gutter)
                panel = PanelLayout(x=x, y=y, width=panel_width, height=panel_height)
                panels.append(panel)
        else:
            panel_width = (content_width - (num_panels - 1) * self.gutter) // num_panels
            panel_height = content_height
            
            for i in range(num_panels):
                x = self.margin + i * (panel_width + self.gutter)
                y = self.margin
                panel = PanelLayout(x=x, y=y, width=panel_width, height=panel_height)
                panels.append(panel)
        
        orientation = "vertical" if vertical else "horizontal"
        logger.debug(f"Created {orientation} strip layout with {num_panels} panels")
        return panels
    
    def compose_page(
        self,
        panels: List[Image.Image],
        layout: List[PanelLayout],
        background_color: Tuple[int, int, int] = (255, 255, 255)
    ) -> Image.Image:
        """Compose panel images into a comic page.
        
        Args:
            panels: List of panel images
            layout: List of panel layouts
            background_color: Background color for the page
            
        Returns:
            Composed page image
        """
        if len(panels) != len(layout):
            logger.warning(
                f"Panel count mismatch: {len(panels)} panels, {len(layout)} layouts. "
                "Using minimum count."
            )
        
        # Create page canvas
        page = Image.new("RGB", (self.page_width, self.page_height), background_color)
        draw = ImageDraw.Draw(page)
        
        # Place each panel
        for i, (panel_img, panel_layout) in enumerate(zip(panels, layout)):
            # Draw panel border
            draw.rectangle(
                [
                    panel_layout.x,
                    panel_layout.y,
                    panel_layout.x + panel_layout.width,
                    panel_layout.y + panel_layout.height
                ],
                outline=(0, 0, 0),
                width=panel_layout.border_width
            )
            
            # Get content area
            cx, cy, cw, ch = panel_layout.get_content_area()
            
            # Resize panel to fit content area while maintaining aspect ratio
            panel_resized = self._resize_panel_fit(panel_img, cw, ch)
            
            # Center the panel in the content area
            paste_x = cx + (cw - panel_resized.width) // 2
            paste_y = cy + (ch - panel_resized.height) // 2
            
            # Paste panel
            page.paste(panel_resized, (paste_x, paste_y))
            
            logger.debug(f"Placed panel {i+1} at ({cx}, {cy})")
        
        logger.info(f"Composed page with {len(panels)} panels")
        return page
    
    def _resize_panel_fit(
        self,
        image: Image.Image,
        target_width: int,
        target_height: int
    ) -> Image.Image:
        """Resize image to fit within target dimensions while maintaining aspect ratio.
        
        Args:
            image: Image to resize
            target_width: Maximum width
            target_height: Maximum height
            
        Returns:
            Resized image
        """
        # Calculate aspect ratios
        img_aspect = image.width / image.height
        target_aspect = target_width / target_height
        
        # Determine new dimensions based on aspect ratio
        if img_aspect > target_aspect:
            # Image is wider - fit to width
            new_width = target_width
            new_height = int(target_width / img_aspect)
        else:
            # Image is taller - fit to height
            new_height = target_height
            new_width = int(target_height * img_aspect)
        
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    def auto_layout(self, num_panels: int) -> LayoutType:
        """Automatically select the best layout for a number of panels.
        
        Args:
            num_panels: Number of panels
            
        Returns:
            Recommended LayoutType
        """
        config = get_config()
        max_panels = config.max_panels_per_page
        
        if num_panels > max_panels:
            logger.warning(
                f"Number of panels ({num_panels}) exceeds maximum ({max_panels}). "
                "Consider splitting into multiple pages."
            )
        
        # Layout selection logic
        layout_map = {
            1: LayoutType.VERTICAL_STRIP,
            2: LayoutType.GRID_2X2,
            3: LayoutType.VERTICAL_STRIP,
            4: LayoutType.GRID_2X2,
            5: LayoutType.GRID_2X3,
            6: LayoutType.GRID_2X3,
            7: LayoutType.GRID_3X3,
            8: LayoutType.GRID_3X3,
            9: LayoutType.GRID_3X3,
        }
        
        layout = layout_map.get(num_panels, LayoutType.GRID_3X3)
        logger.debug(f"Auto-selected layout {layout.value} for {num_panels} panels")
        return layout
