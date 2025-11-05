"""
Ensemble retriever combining dense and sparse methods.

This module implements hybrid search by combining vector similarity (dense)
and keyword matching (sparse) with weighted scoring.
"""

from typing import List, Dict, Any, Optional, Union
from langchain_core.documents import Document
import logging

from app.retrievers.base import BaseRetriever
from app.retrievers.dense import DenseRetriever
from app.retrievers.sparse import SparseRetriever
from app.retrievers.parent_document import ParentDocumentRetriever
from app.retrievers.query_builder import QueryTerms, bm25_query_from_sparse

logger = logging.getLogger(__name__)


class EnsembleRetriever(BaseRetriever):
    """
    Ensemble retriever combining dense/parent and sparse retrieval methods.

    Combines vector similarity search (semantic) with BM25 keyword search (lexical)
    using weighted scoring to get the best of both worlds.

    Supports two semantic retrieval strategies:
    - DenseRetriever: Direct vector similarity search
    - ParentDocumentRetriever: Small-to-big strategy (search on child chunks, return parents)
    """

    def __init__(
        self,
        semantic_retriever: Union[DenseRetriever, ParentDocumentRetriever],
        sparse_retriever: SparseRetriever,
        semantic_weight: float = 0.5,
        sparse_weight: float = 0.5,
    ):
        """
        Initialize ensemble retriever.

        Args:
            semantic_retriever: Dense or ParentDocument retriever for semantic search
            sparse_retriever: Sparse BM25 retriever for keyword search
            semantic_weight: Weight for semantic scores (0-1)
            sparse_weight: Weight for sparse scores (0-1)
        """
        self.semantic_retriever = semantic_retriever
        self.sparse_retriever = sparse_retriever
        self.semantic_weight = semantic_weight
        self.sparse_weight = sparse_weight

        # Normalize weights
        total_weight = semantic_weight + sparse_weight
        if total_weight > 0:
            self.semantic_weight = semantic_weight / total_weight
            self.sparse_weight = sparse_weight / total_weight

        retriever_type = type(semantic_retriever).__name__
        logger.info(
            f"Initialized EnsembleRetriever with {retriever_type} + SparseRetriever, "
            f"weights: semantic={self.semantic_weight:.2f}, sparse={self.sparse_weight:.2f}"
        )

    async def retrieve(
        self,
        query: Union[str, QueryTerms],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """
        Retrieve documents using ensemble of semantic and sparse methods.

        Args:
            query: Query string or QueryTerms object with dense and sparse representations
            top_k: Number of documents to retrieve
            filters: Optional filters

        Returns:
            List of Document objects with combined scores
        """
        try:
            # Handle both string and QueryTerms input
            if isinstance(query, str):
                semantic_query = query
                sparse_query = query
                logger.debug(f"Ensemble retrieval with string query: '{query[:50]}...'")
            elif isinstance(query, QueryTerms):
                semantic_query = query.dense
                sparse_query = bm25_query_from_sparse(query.sparse)
                logger.debug(
                    f"Ensemble retrieval with QueryTerms: "
                    f"semantic='{semantic_query[:50]}...', sparse='{sparse_query[:50]}...'"
                )
            else:
                raise ValueError(f"Invalid query type: {type(query)}")

            self._validate_query(semantic_query)
            self._validate_top_k(top_k)

            # Retrieve from both methods (get more initially for better fusion)
            retrieve_k = top_k * 2

            semantic_docs = await self.semantic_retriever.retrieve(
                semantic_query, retrieve_k, filters
            )
            sparse_docs = await self.sparse_retriever.retrieve(sparse_query, retrieve_k, filters)

            logger.debug(
                f"Retrieved {len(semantic_docs)} semantic docs, {len(sparse_docs)} sparse docs"
            )

            # Combine and score documents
            doc_scores: Dict[str, Dict[str, Any]] = {}

            # Add semantic retrieval scores
            for doc in semantic_docs:
                chunk_id = doc.metadata.get("chunk_id", "")
                if not chunk_id:
                    continue

                score = doc.metadata.get("relevance_score", 0.0) * self.semantic_weight
                doc_scores[chunk_id] = {
                    "doc": doc,
                    "score": score,
                    "semantic_score": doc.metadata.get("relevance_score", 0.0),
                    "sparse_score": 0.0,
                }

            # Add sparse retrieval scores
            for doc in sparse_docs:
                chunk_id = doc.metadata.get("chunk_id", "")
                if not chunk_id:
                    continue

                score = doc.metadata.get("relevance_score", 0.0) * self.sparse_weight

                if chunk_id in doc_scores:
                    # Document found by both methods - add scores
                    doc_scores[chunk_id]["score"] += score
                    doc_scores[chunk_id]["sparse_score"] = doc.metadata.get("relevance_score", 0.0)
                else:
                    # Document only found by sparse method
                    doc_scores[chunk_id] = {
                        "doc": doc,
                        "score": score,
                        "semantic_score": 0.0,
                        "sparse_score": doc.metadata.get("relevance_score", 0.0),
                    }

            # Sort by combined score
            sorted_docs = sorted(doc_scores.values(), key=lambda x: x["score"], reverse=True)[
                :top_k
            ]

            # Build result documents with updated metadata
            result_docs = []
            for item in sorted_docs:
                doc = item["doc"]
                result_doc = Document(
                    page_content=doc.page_content,
                    metadata={
                        **doc.metadata,
                        "relevance_score": item["score"],
                        "semantic_score": item["semantic_score"],
                        "sparse_score": item["sparse_score"],
                        "retrieval_method": "ensemble",
                    },
                )
                result_docs.append(result_doc)

            logger.info(
                f"Ensemble retrieval: retrieved {len(result_docs)} documents "
                f"(combined from {len(doc_scores)} unique chunks)"
            )
            return result_docs

        except Exception as e:
            logger.error(f"Ensemble retrieval failed: {e}", exc_info=True)
            return []
