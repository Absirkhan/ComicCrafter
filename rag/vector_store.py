"""Vector store implementation using ChromaDB."""

from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from pathlib import Path

from utils import get_config, get_logger

logger = get_logger(__name__)


class VectorStore:
    """ChromaDB-based vector store for embeddings."""
    
    def __init__(
        self,
        collection_name: Optional[str] = None,
        persist_directory: Optional[Path] = None
    ):
        """Initialize VectorStore with ChromaDB.
        
        Args:
            collection_name: Name of the ChromaDB collection
            persist_directory: Directory to persist the database
        """
        config = get_config()
        self.collection_name = collection_name or config.chromadb_collection
        self.persist_directory = persist_directory or config.chromadb_path
        
        # Ensure directory exists
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Comic character embeddings"}
        )
        
        logger.info(
            f"Initialized VectorStore: collection='{self.collection_name}', "
            f"path='{self.persist_directory}'"
        )
    
    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> None:
        """Add documents to the vector store.
        
        Args:
            documents: List of text documents to add
            metadatas: Optional metadata for each document
            ids: Optional IDs for each document (auto-generated if not provided)
        """
        if not documents:
            logger.warning("No documents to add")
            return
        
        # Generate IDs if not provided
        if ids is None:
            existing_count = self.collection.count()
            ids = [f"doc_{existing_count + i}" for i in range(len(documents))]
        
        # Add to collection
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        logger.info(f"Added {len(documents)} documents to vector store")
    
    def query(
        self,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Query the vector store for similar documents.
        
        Args:
            query_texts: List of query texts
            n_results: Number of results to return per query
            where: Metadata filter criteria
            where_document: Document content filter criteria
            
        Returns:
            Dictionary containing query results
        """
        results = self.collection.query(
            query_texts=query_texts,
            n_results=n_results,
            where=where,
            where_document=where_document
        )
        
        logger.debug(f"Query returned {len(results.get('ids', [[]])[0])} results")
        return results
    
    def get_by_id(self, ids: List[str]) -> Dict[str, Any]:
        """Retrieve documents by their IDs.
        
        Args:
            ids: List of document IDs to retrieve
            
        Returns:
            Dictionary containing the requested documents
        """
        results = self.collection.get(ids=ids)
        logger.debug(f"Retrieved {len(results.get('ids', []))} documents by ID")
        return results
    
    def update_document(
        self,
        id: str,
        document: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update a document in the vector store.
        
        Args:
            id: Document ID to update
            document: New document text (optional)
            metadata: New metadata (optional)
        """
        update_kwargs = {"ids": [id]}
        
        if document is not None:
            update_kwargs["documents"] = [document]
        
        if metadata is not None:
            update_kwargs["metadatas"] = [metadata]
        
        self.collection.update(**update_kwargs)
        logger.info(f"Updated document: {id}")
    
    def delete_documents(self, ids: List[str]) -> None:
        """Delete documents from the vector store.
        
        Args:
            ids: List of document IDs to delete
        """
        self.collection.delete(ids=ids)
        logger.info(f"Deleted {len(ids)} documents from vector store")
    
    def count(self) -> int:
        """Get the number of documents in the collection.
        
        Returns:
            Number of documents
        """
        return self.collection.count()
    
    def reset(self) -> None:
        """Clear all documents from the collection."""
        # Delete and recreate collection
        self.client.delete_collection(name=self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"description": "Comic character embeddings"}
        )
        logger.warning(f"Reset collection: {self.collection_name}")
