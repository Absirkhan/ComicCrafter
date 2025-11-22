"""Layout Agent for determining optimal panel layouts."""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from layout.panel_layout import LayoutType, LayoutManager
from agents.story_agent import Scene
from utils import get_config, get_logger

logger = get_logger(__name__)


@dataclass
class PageLayout:
    """Defines layout for a comic page.
    
    Attributes:
        layout_type: Type of layout
        num_panels: Number of panels on the page
        scene_indices: Indices of scenes on this page
    """
    layout_type: LayoutType
    num_panels: int
    scene_indices: List[int]


class LayoutAgent:
    """Agent responsible for determining panel layouts."""
    
    def __init__(self, layout_manager: Optional[LayoutManager] = None):
        """Initialize LayoutAgent.
        
        Args:
            layout_manager: LayoutManager for creating layouts
        """
        self.layout_manager = layout_manager or LayoutManager()
        self.config = get_config()
        logger.info("Initialized LayoutAgent")
    
    def plan_layouts(
        self,
        scenes: List[Scene],
        max_panels_per_page: Optional[int] = None
    ) -> List[PageLayout]:
        """Plan page layouts for a list of scenes.
        
        Args:
            scenes: List of Scene objects
            max_panels_per_page: Maximum panels per page
            
        Returns:
            List of PageLayout objects
        """
        if max_panels_per_page is None:
            max_panels_per_page = self.config.max_panels_per_page
        
        logger.info(
            f"Planning layouts for {len(scenes)} scenes, "
            f"max {max_panels_per_page} panels per page"
        )
        
        # Group scenes into pages
        page_layouts = []
        current_page_scenes = []
        
        for i, scene in enumerate(scenes):
            current_page_scenes.append(i)
            
            # Check if we should start a new page
            if len(current_page_scenes) >= max_panels_per_page:
                page_layout = self._create_page_layout(current_page_scenes)
                page_layouts.append(page_layout)
                current_page_scenes = []
        
        # Handle remaining scenes
        if current_page_scenes:
            page_layout = self._create_page_layout(current_page_scenes)
            page_layouts.append(page_layout)
        
        logger.info(f"Created {len(page_layouts)} page layouts")
        return page_layouts
    
    def _create_page_layout(self, scene_indices: List[int]) -> PageLayout:
        """Create a page layout for a set of scenes.
        
        Args:
            scene_indices: Indices of scenes on this page
            
        Returns:
            PageLayout object
        """
        num_panels = len(scene_indices)
        layout_type = self.layout_manager.auto_layout(num_panels)
        
        return PageLayout(
            layout_type=layout_type,
            num_panels=num_panels,
            scene_indices=scene_indices
        )
    
    def plan_adaptive_layout(
        self,
        scenes: List[Scene]
    ) -> List[PageLayout]:
        """Plan layouts adaptively based on scene complexity.
        
        Args:
            scenes: List of Scene objects
            
        Returns:
            List of PageLayout objects
        """
        logger.info(f"Planning adaptive layouts for {len(scenes)} scenes")
        
        page_layouts = []
        current_page_scenes = []
        current_complexity = 0
        max_complexity = 10  # Threshold for complexity
        
        for i, scene in enumerate(scenes):
            # Estimate scene complexity
            complexity = self._estimate_scene_complexity(scene)
            
            # Check if adding this scene would exceed threshold
            if current_page_scenes and (
                current_complexity + complexity > max_complexity or
                len(current_page_scenes) >= self.config.max_panels_per_page
            ):
                # Create page and start new one
                page_layout = self._create_page_layout(current_page_scenes)
                page_layouts.append(page_layout)
                current_page_scenes = []
                current_complexity = 0
            
            current_page_scenes.append(i)
            current_complexity += complexity
        
        # Handle remaining scenes
        if current_page_scenes:
            page_layout = self._create_page_layout(current_page_scenes)
            page_layouts.append(page_layout)
        
        logger.info(f"Created {len(page_layouts)} adaptive page layouts")
        return page_layouts
    
    def _estimate_scene_complexity(self, scene: Scene) -> int:
        """Estimate the complexity of a scene.
        
        Args:
            scene: Scene object
            
        Returns:
            Complexity score (1-5)
        """
        complexity = 1
        
        # More characters = more complex
        complexity += min(len(scene.characters), 2)
        
        # Dialogue increases complexity
        if scene.dialogue and len(scene.dialogue) > 2:
            complexity += 1
        
        # Long action descriptions = more complex
        if len(scene.action) > 100:
            complexity += 1
        
        return min(complexity, 5)
    
    def suggest_layout_for_scene(self, scene: Scene) -> LayoutType:
        """Suggest a layout type for a single scene.
        
        Args:
            scene: Scene object
            
        Returns:
            Recommended LayoutType
        """
        # Simple heuristic based on scene properties
        num_characters = len(scene.characters)
        has_dialogue = bool(scene.dialogue)
        
        if num_characters == 1 and not has_dialogue:
            return LayoutType.VERTICAL_STRIP
        elif num_characters <= 2:
            return LayoutType.GRID_2X2
        else:
            return LayoutType.GRID_2X3
    
    def create_custom_layout(
        self,
        scene_indices: List[int],
        layout_type: LayoutType
    ) -> PageLayout:
        """Create a custom page layout.
        
        Args:
            scene_indices: Indices of scenes for this page
            layout_type: Desired layout type
            
        Returns:
            PageLayout object
        """
        return PageLayout(
            layout_type=layout_type,
            num_panels=len(scene_indices),
            scene_indices=scene_indices
        )
