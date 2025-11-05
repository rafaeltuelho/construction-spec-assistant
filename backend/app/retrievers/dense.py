"""
Dense retriever using vector embeddings.

This module implements dense vector similarity search using Qdrant.
"""

from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from fastembed import TextEmbedding
import logging

from app.retrievers.base import BaseRetriever

logger = logging.getLogger(__name__)


class DenseRetriever(BaseRetriever):
    """
    Dense retriever using vector embeddings for semantic search.

    Uses FastEmbed for embedding generation and Qdrant for vector search.
    """

    def __init__(
        self,
        qdrant_client: QdrantClient,
        collection_name: str = "construction_docs",
        embedding_model: str = "BAAI/bge-small-en-v1.5",
    ):
        """
        Initialize dense retriever.

        Args:
            qdrant_client: Qdrant client instance
            collection_name: Name of the Qdrant collection
            embedding_model: FastEmbed model name
        """
        self.client = qdrant_client
        self.collection_name = collection_name
        self.embedding_model = TextEmbedding(model_name=embedding_model)
        logger.info(f"Initialized DenseRetriever with model {embedding_model}")

    async def retrieve(
        self, query: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Retrieve documents using dense vector search.

        Args:
            query: Natural language query
            top_k: Number of documents to retrieve
            filters: Optional filters (e.g., {"document_id": "doc_123"})

        Returns:
            List of Document objects with relevance scores
        """
        try:
            self._validate_query(query)
            self._validate_top_k(top_k)

            logger.debug(f"Dense retrieval: query='{query[:50]}...', top_k={top_k}")

            # Generate query embedding
            query_embedding = list(self.embedding_model.embed([query]))[0]
            logger.debug(f"Generated embedding with {len(query_embedding)} dimensions")

            # Build Qdrant filter
            qdrant_filter = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
                qdrant_filter = Filter(must=conditions)
                logger.debug(f"Applied filters: {filters}")

            # Search Qdrant
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k,
                query_filter=qdrant_filter,
            )

            # Convert to LangChain Documents
            documents = []
            for result in results:
                doc = Document(
                    page_content=result.payload.get("content", ""),
                    metadata={
                        "chunk_id": str(result.id),
                        "document_id": result.payload.get("document_id", ""),
                        "section_path": result.payload.get("section_path", ""),
                        "relevance_score": float(result.score),
                        "retrieval_method": "dense",
                        # Page number tracking (from Docling provenance)
                        "page_start": result.payload.get("page_start"),
                        "page_end": result.payload.get("page_end"),
                    },
                )
                documents.append(doc)

            logger.info(f"Dense retrieval: retrieved {len(documents)} documents")
            return documents

        except Exception as e:
            logger.error(f"Dense retrieval failed: {e}", exc_info=True)
            return []
