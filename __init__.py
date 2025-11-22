"""ComicCrafter: Zero-cost multi-agent AI system for automatic comic generation."""

__version__ = "0.1.0"
__author__ = "ComicCrafter Team"

from core import ComicCrafter
from agents import StoryAgent, PromptAgent, LayoutAgent
from rag import CharacterMemory, VectorStore
from generation import ImageGenerator
from layout import LayoutManager, TextOverlay

__all__ = [
    "ComicCrafter",
    "StoryAgent",
    "PromptAgent",
    "LayoutAgent",
    "CharacterMemory",
    "VectorStore",
    "ImageGenerator",
    "LayoutManager",
    "TextOverlay",
]
