"""Configuration management for ComicCrafter."""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config(BaseModel):
    """Configuration class for ComicCrafter.
    
    Attributes:
        groq_api_key: API key for Groq (Llama 3.3)
        google_api_key: API key for Google Gemini
        huggingface_token: Token for HuggingFace Inference API
        default_llm_model: Default language model to use
        default_image_model: Default image generation model
        gemini_model: Gemini model version
        chromadb_path: Path to ChromaDB storage
        chromadb_collection: ChromaDB collection name
        output_dir: Directory for output files
        max_panels_per_page: Maximum panels per comic page
        image_width: Generated image width
        image_height: Generated image height
    """
    
    # API Keys
    groq_api_key: str = Field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    google_api_key: str = Field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    huggingface_token: str = Field(default_factory=lambda: os.getenv("HUGGINGFACE_TOKEN", ""))
    
    # Model Configuration
    default_llm_model: str = Field(
        default_factory=lambda: os.getenv("DEFAULT_LLM_MODEL", "llama-3.3-70b-versatile")
    )
    default_image_model: str = Field(
        default_factory=lambda: os.getenv("DEFAULT_IMAGE_MODEL", "black-forest-labs/FLUX.1-dev")
    )
    gemini_model: str = Field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
    )
    
    # ChromaDB Configuration
    chromadb_path: Path = Field(
        default_factory=lambda: Path(os.getenv("CHROMADB_PATH", "./data/chroma_db"))
    )
    chromadb_collection: str = Field(
        default_factory=lambda: os.getenv("CHROMADB_COLLECTION", "comic_characters")
    )
    
    # Output Configuration
    output_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("OUTPUT_DIR", "./output"))
    )
    max_panels_per_page: int = Field(
        default_factory=lambda: int(os.getenv("MAX_PANELS_PER_PAGE", "6"))
    )
    image_width: int = Field(
        default_factory=lambda: int(os.getenv("IMAGE_WIDTH", "512"))
    )
    image_height: int = Field(
        default_factory=lambda: int(os.getenv("IMAGE_HEIGHT", "512"))
    )
    
    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True
    
    def validate_api_keys(self) -> bool:
        """Validate that required API keys are set.
        
        Returns:
            True if at least one API key is configured
        
        Raises:
            ValueError: If no API keys are configured
        """
        has_key = bool(self.groq_api_key or self.google_api_key or self.huggingface_token)
        if not has_key:
            raise ValueError(
                "No API keys configured. Please set at least one of: "
                "GROQ_API_KEY, GOOGLE_API_KEY, or HUGGINGFACE_TOKEN"
            )
        return True
    
    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.chromadb_path.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create the global configuration instance.
    
    Returns:
        Config: The global configuration object
    """
    global _config
    if _config is None:
        _config = Config()
        _config.ensure_directories()
    return _config
