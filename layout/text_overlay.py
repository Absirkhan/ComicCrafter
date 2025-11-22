"""Text overlay for speech bubbles and captions."""

from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from PIL import Image, ImageDraw, ImageFont
import textwrap

from utils import get_logger

logger = get_logger(__name__)


class TextType(Enum):
    """Types of text overlays."""
    SPEECH_BUBBLE = "speech_bubble"
    THOUGHT_BUBBLE = "thought_bubble"
    CAPTION = "caption"
    SOUND_EFFECT = "sound_effect"


@dataclass
class TextBox:
    """Defines a text box overlay.
    
    Attributes:
        text: Text content
        x: X-coordinate (center of text box)
        y: Y-coordinate (center of text box)
        text_type: Type of text overlay
        max_width: Maximum width of text box
        font_size: Font size in points
    """
    text: str
    x: int
    y: int
    text_type: TextType = TextType.SPEECH_BUBBLE
    max_width: int = 200
    font_size: int = 24


class TextOverlay:
    """Manages text overlays on comic panels."""
    
    def __init__(
        self,
        default_font_size: int = 24,
        bubble_padding: int = 20,
        bubble_color: Tuple[int, int, int] = (255, 255, 255),
        text_color: Tuple[int, int, int] = (0, 0, 0)
    ):
        """Initialize TextOverlay.
        
        Args:
            default_font_size: Default font size in points
            bubble_padding: Padding inside speech bubbles
            bubble_color: Background color for bubbles
            text_color: Text color
        """
        self.default_font_size = default_font_size
        self.bubble_padding = bubble_padding
        self.bubble_color = bubble_color
        self.text_color = text_color
        
        # Try to load a better font, fall back to default
        self.font = self._load_font(default_font_size)
        
        logger.info(f"Initialized TextOverlay with font size {default_font_size}")
    
    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Load a font for text rendering.
        
        Args:
            size: Font size in points
            
        Returns:
            ImageFont object
        """
        try:
            # Try common comic fonts
            font_options = [
                "arial.ttf",
                "Arial.ttf",
                "DejaVuSans.ttf",
                "LiberationSans-Regular.ttf"
            ]
            
            for font_name in font_options:
                try:
                    return ImageFont.truetype(font_name, size)
                except OSError:
                    continue
            
            # Fallback to default
            logger.warning("Could not load TrueType font, using default")
            return ImageFont.load_default()
            
        except Exception as e:
            logger.error(f"Error loading font: {e}")
            return ImageFont.load_default()
    
    def add_text_to_panel(
        self,
        panel: Image.Image,
        text_boxes: List[TextBox]
    ) -> Image.Image:
        """Add text overlays to a panel image.
        
        Args:
            panel: Panel image
            text_boxes: List of text boxes to add
            
        Returns:
            Panel image with text overlays
        """
        # Create a copy to avoid modifying original
        panel_copy = panel.copy()
        draw = ImageDraw.Draw(panel_copy)
        
        for text_box in text_boxes:
            self._draw_text_box(draw, panel_copy, text_box)
        
        logger.debug(f"Added {len(text_boxes)} text overlays to panel")
        return panel_copy
    
    def _draw_text_box(
        self,
        draw: ImageDraw.ImageDraw,
        image: Image.Image,
        text_box: TextBox
    ) -> None:
        """Draw a single text box on the image.
        
        Args:
            draw: ImageDraw object
            image: Panel image
            text_box: TextBox to draw
        """
        # Load font with appropriate size
        font = self._load_font(text_box.font_size)
        
        # Wrap text to fit max width
        wrapped_text = self._wrap_text(text_box.text, text_box.max_width, font, draw)
        
        # Calculate text dimensions
        bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Calculate bubble dimensions
        bubble_width = text_width + 2 * self.bubble_padding
        bubble_height = text_height + 2 * self.bubble_padding
        
        # Calculate bubble position (centered on x, y)
        bubble_x = text_box.x - bubble_width // 2
        bubble_y = text_box.y - bubble_height // 2
        
        # Ensure bubble stays within image bounds
        bubble_x = max(5, min(bubble_x, image.width - bubble_width - 5))
        bubble_y = max(5, min(bubble_y, image.height - bubble_height - 5))
        
        # Draw based on text type
        if text_box.text_type == TextType.SPEECH_BUBBLE:
            self._draw_speech_bubble(
                draw, bubble_x, bubble_y, bubble_width, bubble_height
            )
        elif text_box.text_type == TextType.THOUGHT_BUBBLE:
            self._draw_thought_bubble(
                draw, bubble_x, bubble_y, bubble_width, bubble_height
            )
        elif text_box.text_type == TextType.CAPTION:
            self._draw_caption_box(
                draw, bubble_x, bubble_y, bubble_width, bubble_height
            )
        elif text_box.text_type == TextType.SOUND_EFFECT:
            # Sound effects don't need bubbles
            pass
        
        # Draw text
        text_x = bubble_x + self.bubble_padding
        text_y = bubble_y + self.bubble_padding
        
        draw.multiline_text(
            (text_x, text_y),
            wrapped_text,
            font=font,
            fill=self.text_color,
            align="center"
        )
    
    def _wrap_text(
        self,
        text: str,
        max_width: int,
        font: ImageFont.FreeTypeFont,
        draw: ImageDraw.ImageDraw
    ) -> str:
        """Wrap text to fit within max width.
        
        Args:
            text: Text to wrap
            max_width: Maximum width in pixels
            font: Font to use
            draw: ImageDraw object for measuring
            
        Returns:
            Wrapped text with newlines
        """
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]
            
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return '\n'.join(lines)
    
    def _draw_speech_bubble(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        width: int,
        height: int
    ) -> None:
        """Draw a speech bubble background.
        
        Args:
            draw: ImageDraw object
            x, y: Top-left coordinates
            width, height: Bubble dimensions
        """
        # Draw rounded rectangle
        draw.rounded_rectangle(
            [x, y, x + width, y + height],
            radius=15,
            fill=self.bubble_color,
            outline=(0, 0, 0),
            width=2
        )
    
    def _draw_thought_bubble(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        width: int,
        height: int
    ) -> None:
        """Draw a thought bubble background.
        
        Args:
            draw: ImageDraw object
            x, y: Top-left coordinates
            width, height: Bubble dimensions
        """
        # Draw cloud-like shape (simplified as rounded rectangle)
        draw.rounded_rectangle(
            [x, y, x + width, y + height],
            radius=25,
            fill=self.bubble_color,
            outline=(0, 0, 0),
            width=2
        )
        
        # Add small circles for thought bubble effect
        circle_x = x + 10
        circle_y = y + height + 5
        draw.ellipse([circle_x-5, circle_y-5, circle_x+5, circle_y+5], 
                     fill=self.bubble_color, outline=(0, 0, 0))
        
        circle_x = x + 5
        circle_y = y + height + 15
        draw.ellipse([circle_x-3, circle_y-3, circle_x+3, circle_y+3], 
                     fill=self.bubble_color, outline=(0, 0, 0))
    
    def _draw_caption_box(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        width: int,
        height: int
    ) -> None:
        """Draw a caption box background.
        
        Args:
            draw: ImageDraw object
            x, y: Top-left coordinates
            width, height: Box dimensions
        """
        # Draw rectangular caption box
        draw.rectangle(
            [x, y, x + width, y + height],
            fill=(240, 240, 200),  # Slightly yellow tint
            outline=(0, 0, 0),
            width=2
        )
