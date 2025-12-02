"""Character memory system for maintaining consistency across comic panels."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import json

from rag.vector_store import VectorStore
from utils import get_logger

logger = get_logger(__name__)


@dataclass
class Character:
    """Character information for comic generation.
    
    Attributes:
        name: Character name
        appearance: Physical appearance description
        personality: Personality traits
        role: Role in the story
        tags: Additional tags for retrieval
    """
    name: str
    appearance: str
    personality: str = ""
    role: str = ""
    tags: List[str] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert character to dictionary.
        
        Returns:
            Dictionary representation
        """
        return asdict(self)
    
    def to_description(self) -> str:
        """Generate a full text description of the character.
        
        Returns:
            Text description
        """
        parts = [f"Character: {self.name}"]
        parts.append(f"Appearance: {self.appearance}")
        
        if self.personality:
            parts.append(f"Personality: {self.personality}")
        
        if self.role:
            parts.append(f"Role: {self.role}")
        
        if self.tags:
            parts.append(f"Tags: {', '.join(self.tags)}")
        
        return ". ".join(parts)


class CharacterMemory:
    """Manages character information using RAG for consistency."""
    
    def __init__(self, vector_store: Optional[VectorStore] = None):
        """Initialize CharacterMemory.
        
        Args:
            vector_store: VectorStore instance for character storage
        """
        self.vector_store = vector_store or VectorStore()
        logger.info("Initialized CharacterMemory")
    
    def add_character(self, character: Character) -> str:
        """Add a character to memory.
        
        Args:
            character: Character to add
            
        Returns:
            Character ID
        """
        character_id = f"char_{character.name.lower().replace(' ', '_')}"
        
        # Store character description as document
        description = character.to_description()
        metadata = character.to_dict()
        metadata["character_id"] = character_id
        
        # Convert all list/dict fields to strings for ChromaDB compatibility
        for key, value in list(metadata.items()):
            if isinstance(value, list):
                metadata[key] = ", ".join(str(v) for v in value) if value else ""
            elif isinstance(value, dict):
                metadata[key] = json.dumps(value)
            elif value is None:
                metadata[key] = ""
        
        self.vector_store.add_documents(
            documents=[description],
            metadatas=[metadata],
            ids=[character_id]
        )
        
        logger.info(f"Added character: {character.name} (ID: {character_id})")
        return character_id
    
    def get_character(self, character_name: str) -> Optional[Character]:
        """Retrieve a character by name.
        
        Args:
            character_name: Name of the character
            
        Returns:
            Character object if found, None otherwise
        """
        character_id = f"char_{character_name.lower().replace(' ', '_')}"
        
        try:
            results = self.vector_store.get_by_ids([character_id])
            
            if results["ids"]:
                metadata = results["metadatas"][0]
                # Convert tags back to list from string
                tags = metadata.get("tags", "")
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",")] if tags else []
                
                character = Character(
                    name=metadata["name"],
                    appearance=metadata["appearance"],
                    personality=metadata.get("personality", ""),
                    role=metadata.get("role", ""),
                    tags=tags
                )
                logger.debug(f"Retrieved character: {character_name}")
                return character
        except Exception as e:
            logger.warning(f"Character not found: {character_name} - {e}")
        
        return None
    
    def search_characters(
        self,
        query: str,
        n_results: int = 3
    ) -> List[Character]:
        """Search for characters using semantic similarity.
        
        Args:
            query: Search query text
            n_results: Number of results to return
            
        Returns:
            List of matching characters
        """
        results = self.vector_store.query(
            query_texts=[query],
            n_results=n_results
        )
        
        characters = []
        if results["ids"] and results["ids"][0]:
            for metadata in results["metadatas"][0]:
                # Convert tags back to list from string
                tags = metadata.get("tags", "")
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",")] if tags else []
                
                character = Character(
                    name=metadata["name"],
                    appearance=metadata["appearance"],
                    personality=metadata.get("personality", ""),
                    role=metadata.get("role", ""),
                    tags=tags
                )
                characters.append(character)
        
        logger.debug(f"Found {len(characters)} characters for query: {query[:50]}")
        return characters
    
    def get_character_context(
        self,
        character_name: str,
        scene_description: Optional[str] = None
    ) -> str:
        """Get character context for image generation prompts.
        
        Args:
            character_name: Name of the character
            scene_description: Optional scene description for context
            
        Returns:
            Character context string for prompts
        """
        character = self.get_character(character_name)
        
        if not character:
            logger.warning(f"Character not found: {character_name}")
            return ""
        
        # Build context focused on visual consistency with more detail
        context_parts = [
            f"SAME {character_name} from previous panels",
            f"consistent appearance: {character.appearance}"
        ]
        
        if character.role:
            context_parts.append(f"role: {character.role}")
        
        if scene_description:
            # Search for relevant character traits based on scene
            relevant_chars = self.search_characters(scene_description, n_results=1)
            if relevant_chars and relevant_chars[0].name == character_name:
                if relevant_chars[0].personality:
                    context_parts.append(f"expressing {relevant_chars[0].personality}")
        
        context = ", ".join(context_parts)
        logger.debug(f"Generated context for {character_name}: {context[:100]}")
        return context
    
    def update_character(
        self,
        character_name: str,
        **updates
    ) -> bool:
        """Update character information.
        
        Args:
            character_name: Name of the character to update
            **updates: Fields to update
            
        Returns:
            True if successful, False otherwise
        """
        character = self.get_character(character_name)
        
        if not character:
            logger.error(f"Cannot update non-existent character: {character_name}")
            return False
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(character, key):
                setattr(character, key, value)
        
        # Update in vector store
        character_id = f"char_{character_name.lower().replace(' ', '_')}"
        metadata = character.to_dict()
        
        # Convert list fields to strings for ChromaDB compatibility
        if "tags" in metadata and isinstance(metadata["tags"], list):
            metadata["tags"] = ", ".join(metadata["tags"]) if metadata["tags"] else ""
        
        self.vector_store.update_document(
            id=character_id,
            document=character.to_description(),
            metadata=metadata
        )
        
        logger.info(f"Updated character: {character_name}")
        return True
    
    def list_characters(self) -> List[str]:
        """List all character names in memory.
        
        Returns:
            List of character names
        """
        count = self.vector_store.count()
        if count == 0:
            return []
        
        # Get all documents (limited query)
        results = self.vector_store.query(
            query_texts=["character"],
            n_results=count
        )
        
        names = []
        if results["metadatas"] and results["metadatas"][0]:
            names = [meta["name"] for meta in results["metadatas"][0]]
        
        logger.debug(f"Listed {len(names)} characters")
        return names
    
    def clear_memory(self) -> None:
        """Clear all character data from memory."""
        self.vector_store.reset()
        logger.warning("Cleared all character memory")
