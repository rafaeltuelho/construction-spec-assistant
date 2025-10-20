"""Retrieval agent using LangGraph for multi-strategy document retrieval."""

import logging
from typing import List, Dict, Any, Tuple
from langchain_core.documents import Document
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableLambda

from .graph_definitions import RetrievalState
from ..models.enums import RetrievalStrategy
from ..services.vectorstore import VectorStoreManager

logger = logging.getLogger(__name__)


class RetrievalAgent:
    """Agent for multi-strategy document retrieval using LangGraph."""
    
    def __init__(self, vectorstore_manager: VectorStoreManager):
        """
        Initialize the retrieval agent.
        
        Args:
            vectorstore_manager: VectorStoreManager instance
        """
        self.vectorstore_manager = vectorstore_manager
        self.graph = self._create_retrieval_graph()
    
    def _create_retrieval_graph(self) -> StateGraph:
        """Create the LangGraph for retrieval operations."""
        graph = StateGraph(RetrievalState)
        
        # Add nodes
        graph.add_node("dense_retrieval", self._dense_retrieval_node)
        graph.add_node("sparse_retrieval", self._sparse_retrieval_node)
        graph.add_node("hybrid_retrieval", self._hybrid_retrieval_node)
        graph.add_node("combine_results", self._combine_results_node)
        
        # Set entry point
        graph.set_entry_point("dense_retrieval")
        
        # Add edges based on strategy
        graph.add_conditional_edges(
            "dense_retrieval",
            self._route_strategy,
            {
                "dense": END,
                "sparse": "sparse_retrieval",
                "hybrid": "sparse_retrieval"
            }
        )
        
        graph.add_conditional_edges(
            "sparse_retrieval",
            self._route_strategy,
            {
                "sparse": END,
                "hybrid": "hybrid_retrieval"
            }
        )
        
        graph.add_edge("hybrid_retrieval", "combine_results")
        graph.add_edge("combine_results", END)
        
        return graph.compile()
    
    def _route_strategy(self, state: RetrievalState) -> str:
        """Route based on retrieval strategy."""
        strategy = state.get("strategy", RetrievalStrategy.DENSE)
        return strategy.value
    
    def _dense_retrieval_node(self, state: RetrievalState) -> RetrievalState:
        """Perform dense vector retrieval."""
        try:
            query = state["query"]
            collection_name = state["collection_name"]
            top_k = state.get("top_k", 5)
            
            results = self.vectorstore_manager.dense_search(
                collection_name=collection_name,
                query=query,
                limit=top_k
            )
            
            state["dense_results"] = results
            logger.debug(f"Dense retrieval found {len(results)} results")
            
        except Exception as e:
            logger.error(f"Dense retrieval failed: {e}")
            state["dense_results"] = []
        
        return state
    
    def _sparse_retrieval_node(self, state: RetrievalState) -> RetrievalState:
        """Perform sparse vector (BM25) retrieval."""
        try:
            query = state["query"]
            collection_name = state["collection_name"]
            top_k = state.get("top_k", 5)
            
            results = self.vectorstore_manager.bm25_search(
                collection_name=collection_name,
                query=query,
                limit=top_k
            )
            
            state["sparse_results"] = results
            logger.debug(f"Sparse retrieval found {len(results)} results")
            
        except Exception as e:
            logger.error(f"Sparse retrieval failed: {e}")
            state["sparse_results"] = []
        
        return state
    
    def _hybrid_retrieval_node(self, state: RetrievalState) -> RetrievalState:
        """Perform hybrid retrieval combining dense and sparse."""
        try:
            query = state["query"]
            collection_name = state["collection_name"]
            top_k = state.get("top_k", 5)
            alpha = state.get("alpha", 0.7)
            
            results = self.vectorstore_manager.hybrid_search(
                collection_name=collection_name,
                query=query,
                limit=top_k,
                alpha=alpha
            )
            
            state["hybrid_results"] = results
            logger.debug(f"Hybrid retrieval found {len(results)} results")
            
        except Exception as e:
            logger.error(f"Hybrid retrieval failed: {e}")
            state["hybrid_results"] = []
        
        return state
    
    def _combine_results_node(self, state: RetrievalState) -> RetrievalState:
        """Combine results from different retrieval strategies."""
        try:
            strategy = state.get("strategy", RetrievalStrategy.DENSE)
            top_k = state.get("top_k", 5)
            
            if strategy == RetrievalStrategy.DENSE:
                candidates = [doc for doc, _ in state.get("dense_results", [])]
            elif strategy == RetrievalStrategy.SPARSE:
                candidates = [doc for doc, _ in state.get("sparse_results", [])]
            elif strategy == RetrievalStrategy.HYBRID:
                # Convert hybrid results to Document objects
                candidates = []
                for result in state.get("hybrid_results", []):
                    doc = Document(
                        page_content=result["content"],
                        metadata=result["payload"]
                    )
                    candidates.append(doc)
            else:
                candidates = []
            
            # Limit to top_k results
            state["final_candidates"] = candidates[:top_k]
            logger.debug(f"Final candidates: {len(candidates)}")
            
        except Exception as e:
            logger.error(f"Failed to combine results: {e}")
            state["final_candidates"] = []
        
        return state
    
    def retrieve(
        self,
        query: str,
        collection_name: str,
        strategy: RetrievalStrategy = RetrievalStrategy.HYBRID,
        top_k: int = 5,
        alpha: float = 0.7
    ) -> List[Document]:
        """
        Retrieve documents using specified strategy.
        
        Args:
            query: Search query
            collection_name: Name of the collection to search
            strategy: Retrieval strategy to use
            top_k: Number of results to return
            alpha: Weight for hybrid search (dense vs sparse)
            
        Returns:
            List of retrieved documents
        """
        try:
            initial_state = RetrievalState(
                query=query,
                strategy=strategy,
                collection_name=collection_name,
                vectorstore_manager=self.vectorstore_manager,
                top_k=top_k,
                alpha=alpha,
                dense_results=[],
                sparse_results=[],
                hybrid_results=[],
                final_candidates=[]
            )
            
            result_state = self.graph.invoke(initial_state)
            return result_state.get("final_candidates", [])
            
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return []
