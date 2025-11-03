"""
Retrievers for RAG (Retrieval-Augmented Generation).

This package provides various retrieval strategies for hybrid search:
- Dense retrieval (vector similarity)
- Sparse retrieval (BM25 keyword matching)
- Ensemble retrieval (combining dense and sparse)
"""

from app.retrievers.base import BaseRetriever
from app.retrievers.query_builder import (
    QueryTerms,
    build_query_terms_from_fact,
    bm25_query_from_sparse,
)
from app.retrievers.dense import DenseRetriever
from app.retrievers.sparse import SparseRetriever
from app.retrievers.ensemble import EnsembleRetriever

__all__ = [
    "BaseRetriever",
    "QueryTerms",
    "build_query_terms_from_fact",
    "bm25_query_from_sparse",
    "DenseRetriever",
    "SparseRetriever",
    "EnsembleRetriever",
]
