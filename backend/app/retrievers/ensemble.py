"""
Ensemble retriever combining dense and sparse methods.

This module implements hybrid search by combining vector similarity (dense)
and keyword matching (sparse) with weighted scoring.
"""

from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
import logging

from app.retrievers.base import BaseRetriever
from app.retrievers.dense import DenseRetriever
from app.retrievers.sparse import SparseRetriever

logger = logging.getLogger(__name__)


class EnsembleRetriever(BaseRetriever):
    """
    Ensemble retriever combining dense and sparse retrieval methods.

    Combines vector similarity search (semantic) with BM25 keyword search (lexical)
    using weighted scoring to get the best of both worlds.
    """

    def __init__(
        self,
        dense_retriever: DenseRetriever,
        sparse_retriever: SparseRetriever,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5,
    ):
        """
        Initialize ensemble retriever.

        Args:
            dense_retriever: Dense vector retriever
            sparse_retriever: Sparse BM25 retriever
            dense_weight: Weight for dense scores (0-1)
            sparse_weight: Weight for sparse scores (0-1)
        """
        self.dense_retriever = dense_retriever
        self.sparse_retriever = sparse_retriever
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight

        # Normalize weights
        total_weight = dense_weight + sparse_weight
        if total_weight > 0:
            self.dense_weight = dense_weight / total_weight
            self.sparse_weight = sparse_weight / total_weight

        logger.info(
            f"Initialized EnsembleRetriever with weights: "
            f"dense={self.dense_weight:.2f}, sparse={self.sparse_weight:.2f}"
        )

    async def retrieve(
        self, query: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Retrieve documents using ensemble of dense and sparse methods.

        Args:
            query: Query string
            top_k: Number of documents to retrieve
            filters: Optional filters

        Returns:
            List of Document objects with combined scores
        """
        try:
            self._validate_query(query)
            self._validate_top_k(top_k)

            logger.debug(f"Ensemble retrieval: query='{query[:50]}...', top_k={top_k}")

            # Retrieve from both methods (get more initially for better fusion)
            retrieve_k = top_k * 2

            dense_docs = await self.dense_retriever.retrieve(query, retrieve_k, filters)
            sparse_docs = await self.sparse_retriever.retrieve(query, retrieve_k, filters)

            logger.debug(f"Retrieved {len(dense_docs)} dense docs, {len(sparse_docs)} sparse docs")

            # Combine and score documents
            doc_scores: Dict[str, Dict[str, Any]] = {}

            # Add dense retrieval scores
            for doc in dense_docs:
                chunk_id = doc.metadata.get("chunk_id", "")
                if not chunk_id:
                    continue

                score = doc.metadata.get("relevance_score", 0.0) * self.dense_weight
                doc_scores[chunk_id] = {
                    "doc": doc,
                    "score": score,
                    "dense_score": doc.metadata.get("relevance_score", 0.0),
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
                        "dense_score": 0.0,
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
                        "dense_score": item["dense_score"],
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
