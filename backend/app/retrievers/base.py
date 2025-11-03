"""
Base retriever interface for RAG retrieval.

This module defines the abstract base class for all retriever implementations.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
import logging

logger = logging.getLogger(__name__)


class BaseRetriever(ABC):
    """
    Abstract base class for all retrievers.

    All retriever implementations must inherit from this class and implement
    the retrieve method.
    """

    @abstractmethod
    async def retrieve(
        self, query: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Retrieve relevant documents based on the query.

        Args:
            query: Query string (natural language or keywords)
            top_k: Number of documents to retrieve
            filters: Optional filters (e.g., {"document_id": "doc_123"})

        Returns:
            List of Document objects with relevance scores in metadata

        Raises:
            Exception: If retrieval fails
        """
        pass

    def _validate_query(self, query: str) -> None:
        """
        Validate query string.

        Args:
            query: Query string to validate

        Raises:
            ValueError: If query is invalid
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

    def _validate_top_k(self, top_k: int) -> None:
        """
        Validate top_k parameter.

        Args:
            top_k: Number of documents to retrieve

        Raises:
            ValueError: If top_k is invalid
        """
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if top_k > 100:
            logger.warning(f"top_k={top_k} is very large, consider reducing it")
