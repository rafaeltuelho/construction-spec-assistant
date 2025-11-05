"""
Retrievers for RAG (Retrieval-Augmented Generation).

This package provides various retrieval strategies for hybrid search:
- Dense retrieval (vector similarity)
- Sparse retrieval (BM25 keyword matching)
- Parent document retrieval (small-to-big strategy)
- Ensemble retrieval (combining semantic and sparse)
"""

from app.retrievers.base import BaseRetriever
from app.retrievers.query_builder import (
    QueryTerms,
    build_query_terms_from_fact,
    bm25_query_from_sparse,
)
from app.retrievers.dense import DenseRetriever
from app.retrievers.sparse import SparseRetriever
from app.retrievers.parent_document import ParentDocumentRetriever
from app.retrievers.ensemble import EnsembleRetriever
from app.retrievers.cache import (
    RetrieverCache,
    get_retriever_cache,
    clear_retriever_cache,
)

__all__ = [
    "BaseRetriever",
    "QueryTerms",
    "build_query_terms_from_fact",
    "bm25_query_from_sparse",
    "DenseRetriever",
    "SparseRetriever",
    "ParentDocumentRetriever",
    "EnsembleRetriever",
    "RetrieverCache",
    "get_retriever_cache",
    "clear_retriever_cache",
]
