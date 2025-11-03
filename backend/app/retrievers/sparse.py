"""
Sparse retriever using BM25 algorithm.

This module implements keyword-based BM25 search for lexical matching.
"""

from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
import logging

from backend.app.retrievers.base import BaseRetriever

logger = logging.getLogger(__name__)


class SparseRetriever(BaseRetriever):
    """
    Sparse retriever using BM25 algorithm for keyword-based search.

    BM25 is a probabilistic ranking function that scores documents based on
    term frequency and inverse document frequency.
    """

    def __init__(self, corpus: List[Document]):
        """
        Initialize BM25 retriever.

        Args:
            corpus: List of all documents to search
        """
        self.corpus = corpus

        # Tokenize corpus (simple whitespace tokenization)
        tokenized_corpus = [doc.page_content.lower().split() for doc in corpus]

        # Initialize BM25
        self.bm25 = BM25Okapi(tokenized_corpus)

        logger.info(f"Initialized SparseRetriever with {len(corpus)} documents")

    async def retrieve(
        self, query: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Retrieve documents using BM25 keyword search.

        Args:
            query: Keyword query
            top_k: Number of documents to retrieve
            filters: Optional filters (e.g., {"document_id": "doc_123"})

        Returns:
            List of Document objects with BM25 scores
        """
        try:
            self._validate_query(query)
            self._validate_top_k(top_k)

            logger.debug(f"Sparse retrieval: query='{query[:50]}...', top_k={top_k}")

            # Tokenize query
            tokenized_query = query.lower().split()

            # Get BM25 scores for all documents
            scores = self.bm25.get_scores(tokenized_query)

            # Get top-k indices sorted by score
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[
                : top_k * 2
            ]  # Get more initially for filtering

            # Apply filters if provided
            if filters and "document_id" in filters:
                target_doc_id = filters["document_id"]
                filtered_indices = [
                    i
                    for i in top_indices
                    if self.corpus[i].metadata.get("document_id") == target_doc_id
                ]
                top_indices = filtered_indices[:top_k]
                logger.debug(f"Filtered to document_id={target_doc_id}: {len(top_indices)} results")
            else:
                top_indices = top_indices[:top_k]

            # Build result documents
            documents = []
            for idx in top_indices:
                doc = self.corpus[idx]
                # Create a copy with updated metadata
                result_doc = Document(
                    page_content=doc.page_content,
                    metadata={
                        **doc.metadata,
                        "relevance_score": float(scores[idx]),
                        "retrieval_method": "sparse",
                    },
                )
                documents.append(result_doc)

            logger.info(f"Sparse retrieval: retrieved {len(documents)} documents")
            return documents

        except Exception as e:
            logger.error(f"Sparse retrieval failed: {e}", exc_info=True)
            return []

    def enforce_must_phrases(
        self, documents: List[Document], must_phrases: List[str]
    ) -> List[Document]:
        """
        Filter documents to only include those containing all must phrases.

        Args:
            documents: List of documents to filter
            must_phrases: List of phrases that must appear in the document

        Returns:
            Filtered list of documents
        """
        if not must_phrases:
            return documents

        filtered = []
        for doc in documents:
            content_lower = doc.page_content.lower()
            if all(phrase.lower() in content_lower for phrase in must_phrases):
                filtered.append(doc)

        logger.debug(f"Enforced must phrases: {len(filtered)}/{len(documents)} documents passed")
        return filtered
