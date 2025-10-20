"""LangGraph state and node definitions for the Construction Spec Assistant."""

from typing import List, Dict, Any, Optional, TypedDict, Tuple
from langchain_core.documents import Document

from ..models.enums import RetrievalStrategy, ComparisonVerdict


class State(TypedDict):
    """State for retrieval operations."""
    spec_fact: Dict[str, Any]
    catalog: Dict[str, Any]
    top_k: int
    query: str
    candidates: List[Document]
    result: Dict[str, Any]


class ComparisonState(TypedDict):
    """State for comparison operations."""
    spec_fact: Dict[str, Any]
    catalog: Dict[str, Any]
    submittal_documents: List[str]
    submittal_metadatas: List[Dict[str, Any]]
    vectorstore_manager: Any  # VectorStoreManager instance
    collection_name: str
    top_k: int
    query: str
    candidates: List[Document]
    comparison_results: List[Dict[str, Any]]
    final_result: Dict[str, Any]


class RetrievalState(TypedDict):
    """State for multi-strategy retrieval."""
    query: str
    strategy: RetrievalStrategy
    collection_name: str
    vectorstore_manager: Any  # VectorStoreManager instance
    dense_results: List[Tuple[Document, float]]
    sparse_results: List[Tuple[Document, float]]
    hybrid_results: List[Dict[str, Any]]
    final_candidates: List[Document]
