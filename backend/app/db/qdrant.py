"""
Qdrant vector database operations.

This module provides functions for indexing and searching document chunks
using Qdrant vector database with FastEmbed for embeddings.
"""

import asyncio
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from fastembed import TextEmbedding

from app.models.document import DocumentChunk, ChunkSearchResult
from app.utils.logging import get_logger
from app.utils.exceptions import DatabaseError

logger = get_logger(__name__)

# Thread pool for running synchronous FastEmbed operations
_executor = ThreadPoolExecutor(max_workers=2)

# Global embedding model (lazy loaded)
_embedding_model: Optional[TextEmbedding] = None


def get_embedding_model() -> TextEmbedding:
    """Get or create FastEmbed model (singleton)."""
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading FastEmbed model...")
        _embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        logger.info("FastEmbed model loaded")
    return _embedding_model


def _generate_embeddings_sync(texts: List[str]) -> List[List[float]]:
    """Generate embeddings synchronously (runs in thread pool)."""
    model = get_embedding_model()
    embeddings = list(model.embed(texts))
    return [emb.tolist() for emb in embeddings]


async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings asynchronously."""
    loop = asyncio.get_event_loop()
    embeddings = await loop.run_in_executor(_executor, _generate_embeddings_sync, texts)
    return embeddings


async def ensure_collection_exists(
    client: QdrantClient,
    collection_name: str = "document_chunks",
    vector_size: int = 384
) -> bool:
    """
    Ensure Qdrant collection exists.
    
    Args:
        client: Qdrant client
        collection_name: Collection name
        vector_size: Vector dimension (384 for bge-small-en-v1.5)
    
    Returns:
        True if collection exists or was created
    """
    try:
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if collection_name not in collection_names:
            logger.info(f"Creating collection: {collection_name}")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
            )
            logger.info(f"Collection created: {collection_name}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to ensure collection exists: {str(e)}")
        raise DatabaseError(f"Failed to ensure collection exists: {str(e)}")


async def index_chunks_in_qdrant(
    client: QdrantClient,
    chunks: List[DocumentChunk],
    collection_name: str = "document_chunks"
) -> int:
    """
    Index document chunks in Qdrant.
    
    Args:
        client: Qdrant client
        chunks: Chunks to index
        collection_name: Collection name
    
    Returns:
        Number of chunks indexed
    
    Raises:
        DatabaseError: If indexing fails
    """
    try:
        if not chunks:
            return 0
        
        # Ensure collection exists
        await ensure_collection_exists(client, collection_name)
        
        # Generate embeddings
        texts = [chunk.content for chunk in chunks]
        embeddings = await generate_embeddings(texts)
        
        # Create points
        points = []
        for chunk, embedding in zip(chunks, embeddings):
            point = PointStruct(
                id=chunk.chunk_id,
                vector=embedding,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "section_id": chunk.section_id,
                    "section_title": chunk.section_title,
                    "section_number": chunk.section_number,
                    "section_level": chunk.section_level,
                    "content": chunk.content,
                    "token_count": chunk.token_count,
                    "chunk_index": chunk.chunk_index,
                    "total_chunks": chunk.total_chunks
                }
            )
            points.append(point)
        
        # Upsert points
        client.upsert(collection_name=collection_name, points=points)
        
        logger.info(f"Indexed {len(points)} chunks in Qdrant")
        return len(points)
        
    except Exception as e:
        logger.error(f"Failed to index chunks: {str(e)}")
        raise DatabaseError(f"Failed to index chunks: {str(e)}")


async def search_similar_chunks(
    client: QdrantClient,
    query: str,
    top_k: int = 10,
    document_id: Optional[str] = None,
    min_score: float = 0.0,
    collection_name: str = "document_chunks"
) -> List[ChunkSearchResult]:
    """
    Search for similar chunks using vector similarity.
    
    Args:
        client: Qdrant client
        query: Search query
        top_k: Number of results to return
        document_id: Filter by document ID
        min_score: Minimum similarity score
        collection_name: Collection name
    
    Returns:
        List of search results
    """
    try:
        # Generate query embedding
        query_embeddings = await generate_embeddings([query])
        query_vector = query_embeddings[0]
        
        # Build filter
        query_filter = None
        if document_id:
            query_filter = Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
            )
        
        # Search
        search_results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=query_filter,
            score_threshold=min_score
        )
        
        # Convert to ChunkSearchResult
        results = []
        for result in search_results:
            chunk_result = ChunkSearchResult(
                chunk_id=result.payload["chunk_id"],
                document_id=result.payload["document_id"],
                section_title=result.payload["section_title"],
                content=result.payload["content"],
                score=result.score,
                metadata={
                    "section_number": result.payload.get("section_number"),
                    "section_level": result.payload.get("section_level"),
                    "chunk_index": result.payload.get("chunk_index"),
                    "total_chunks": result.payload.get("total_chunks")
                }
            )
            results.append(chunk_result)
        
        logger.info(f"Found {len(results)} similar chunks for query")
        return results
        
    except Exception as e:
        logger.error(f"Failed to search chunks: {str(e)}")
        raise DatabaseError(f"Failed to search chunks: {str(e)}")


async def delete_document_chunks(
    client: QdrantClient,
    document_id: str,
    collection_name: str = "document_chunks"
) -> bool:
    """
    Delete all chunks for a document from Qdrant.
    
    Args:
        client: Qdrant client
        document_id: Document ID
        collection_name: Collection name
    
    Returns:
        True if deleted
    """
    try:
        client.delete(
            collection_name=collection_name,
            points_selector=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
            )
        )
        
        logger.info(f"Deleted chunks for document: {document_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete chunks: {str(e)}")
        raise DatabaseError(f"Failed to delete chunks: {str(e)}")


def get_collection_info(client: QdrantClient, collection_name: str = "document_chunks") -> Dict[str, Any]:
    """Get collection information."""
    try:
        info = client.get_collection(collection_name=collection_name)
        return {
            "name": collection_name,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status
        }
    except Exception as e:
        logger.error(f"Failed to get collection info: {str(e)}")
        return {}

