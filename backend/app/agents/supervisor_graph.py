"""
LangGraph Supervisor Agent for parallel fact comparison.

This module implements a Supervisor Agent pattern that orchestrates parallel
execution of fact comparisons using LangGraph's state machine architecture.
"""

import asyncio
import logging
from typing import TypedDict, List, Dict, Any, Union, Optional
from datetime import datetime
import uuid

from langchain_openai import ChatOpenAI
from langchain_together import ChatTogether
from langgraph.graph import StateGraph, END
from motor.motor_asyncio import AsyncIOMotorDatabase
from qdrant_client import QdrantClient

from app.agents.comparison_graph import create_comparison_graph
from app.retrievers.cache import get_retriever_cache

logger = logging.getLogger(__name__)


class SupervisorState(TypedDict):
    """State for the Supervisor Agent workflow."""

    # Input
    facts: List[Dict[str, Any]]  # List of spec facts to compare
    submittal_document_id: str  # Submittal document ID
    retrieval_strategy: str  # "dense", "sparse", or "ensemble"
    top_k: int  # Number of documents to retrieve per fact
    max_concurrency: int  # Maximum concurrent comparisons

    # Dependencies (passed through)
    db: AsyncIOMotorDatabase
    qdrant_client: QdrantClient
    llm_client: Union[ChatOpenAI, ChatTogether]

    # Output
    results: List[Dict[str, Any]]  # Comparison results
    summary: Dict[str, int]  # Summary statistics
    completed: int  # Number of completed comparisons
    total: int  # Total number of facts
    errors: List[Dict[str, Any]]  # List of errors encountered

    # Progress tracking
    progress_callback: Optional[callable]  # Progress callback function


async def supervisor_node(state: SupervisorState) -> SupervisorState:
    """
    Supervisor node that orchestrates parallel fact comparisons.

    This node:
    1. Creates a shared retriever and comparison graph (once for all facts)
    2. Creates a semaphore for concurrency control
    3. Spawns sub-agent tasks for each fact
    4. Aggregates results and updates summary
    5. Handles errors gracefully

    Args:
        state: Current supervisor state

    Returns:
        Updated state with results and summary
    """
    facts = state["facts"]
    max_concurrency = state["max_concurrency"]
    submittal_document_id = state["submittal_document_id"]
    retrieval_strategy = state["retrieval_strategy"]
    top_k = state["top_k"]
    db = state["db"]
    qdrant_client = state["qdrant_client"]
    llm_client = state["llm_client"]
    progress_callback = state.get("progress_callback")

    total_facts = len(facts)
    logger.info(
        f"Supervisor starting parallel comparison: {total_facts} facts, "
        f"max_concurrency={max_concurrency}"
    )

    # Initialize result containers
    results = []
    summary = {"consistent": 0, "inconsistent": 0, "unclear": 0}
    errors = []
    completed = 0

    # Create semaphore for concurrency control
    semaphore = asyncio.Semaphore(max_concurrency)

    # Get retriever cache
    retriever_cache = get_retriever_cache()

    # ✅ OPTIMIZATION: Create retriever and comparison graph ONCE for all facts
    logger.info(
        f"Creating shared retriever and comparison graph for {total_facts} facts "
        f"(strategy={retrieval_strategy})"
    )

    try:
        # Import dependencies
        from app.services.comparison import _create_retriever
        from app.agents.comparison_graph import create_comparison_graph, ComparisonState
        from app.retrievers.query_builder import build_query_terms_from_fact

        # Create shared retriever
        retriever = await _create_retriever(
            strategy=retrieval_strategy,
            submittal_document_id=submittal_document_id,
            db=db,
            qdrant_client=qdrant_client,
        )

        # Create shared comparison graph
        filters = {"document_id": submittal_document_id}
        comparison_graph = create_comparison_graph(
            retriever=retriever, llm_client=llm_client, top_k=top_k, filters=filters
        )

        logger.info("Shared retriever and comparison graph created successfully")

    except Exception as e:
        logger.error(f"Failed to create shared retriever/graph: {e}", exc_info=True)
        # Return error state
        state["results"] = []
        state["summary"] = summary
        state["completed"] = 0
        state["total"] = total_facts
        state["errors"] = [{"error": f"Failed to initialize: {str(e)}"}]
        return state

    async def process_fact(fact: Dict[str, Any], fact_index: int) -> Dict[str, Any]:
        """
        Process a single fact using the shared comparison graph.

        Args:
            fact: Spec fact to compare
            fact_index: Index of the fact (for logging)

        Returns:
            Comparison result dict
        """
        nonlocal completed

        async with semaphore:
            try:
                logger.debug(
                    f"Sub-agent {fact_index + 1}/{total_facts} starting: "
                    f"fact_id={fact.get('fact_id', 'unknown')}"
                )

                # ✅ Build query terms from fact
                query_terms = build_query_terms_from_fact(fact)

                # ✅ Use the SHARED comparison graph
                initial_state: ComparisonState = {
                    "spec_fact": fact,
                    "query": query_terms,
                    "retrieved_docs": [],
                    "result": {},
                    "error": "",
                }

                # Run comparison through the shared graph
                final_state = await comparison_graph.ainvoke(initial_state)

                # Check for errors
                if final_state.get("error"):
                    raise Exception(final_state["error"])

                # Extract result
                comparison_result = final_state.get("result", {})

                # Build full result dict (matching compare_spec_to_submittal output)
                result = {
                    "comparison_id": str(uuid.uuid4()),
                    "spec_fact": fact,
                    "submittal_document_id": submittal_document_id,
                    "verdict": comparison_result.get("verdict", "unclear"),
                    "confidence": comparison_result.get("confidence", 0.0),
                    "submittal_evidence": comparison_result.get("submittal_evidence", ""),
                    "reasoning": comparison_result.get("reasoning", ""),
                    "retrieved_chunks": [
                        {
                            "content": doc.page_content,
                            "metadata": doc.metadata,
                            "relevance_score": doc.metadata.get("relevance_score", 0.0),
                        }
                        for doc in final_state.get("retrieved_docs", [])
                    ],
                    "retrieval_strategy": retrieval_strategy,
                    "compared_at": datetime.utcnow(),
                }

                # Update summary
                verdict = result.get("verdict", "unclear")
                if verdict in summary:
                    summary[verdict] += 1

                # Update progress
                completed += 1
                if progress_callback:
                    percentage = int((completed / total_facts) * 100)
                    await progress_callback(completed, total_facts, percentage)

                logger.debug(
                    f"Sub-agent {fact_index + 1}/{total_facts} completed: "
                    f"verdict={verdict}, confidence={result.get('confidence', 0.0):.2f}"
                )

                return result

            except Exception as e:
                logger.error(
                    f"Sub-agent {fact_index + 1}/{total_facts} failed: {str(e)}",
                    exc_info=True,
                )

                # Record error
                error_info = {
                    "fact_index": fact_index,
                    "fact_id": fact.get("fact_id", "unknown"),
                    "error": str(e),
                }
                errors.append(error_info)

                # Update summary (count as unclear)
                summary["unclear"] += 1

                # Update progress even on error
                completed += 1
                if progress_callback:
                    percentage = int((completed / total_facts) * 100)
                    await progress_callback(completed, total_facts, percentage)

                # Return error result
                return {
                    "comparison_id": str(uuid.uuid4()),
                    "spec_fact": fact,
                    "submittal_document_id": submittal_document_id,
                    "verdict": "unclear",
                    "confidence": 0.0,
                    "submittal_evidence": "",
                    "reasoning": f"Comparison failed: {str(e)}",
                    "retrieved_chunks": [],
                    "retrieval_strategy": retrieval_strategy,
                    "compared_at": datetime.utcnow(),
                }

    # Create tasks for all facts
    tasks = [process_fact(fact, i) for i, fact in enumerate(facts)]

    # Execute all tasks concurrently with semaphore control
    logger.info(f"Supervisor executing {len(tasks)} comparison tasks...")
    results = await asyncio.gather(*tasks, return_exceptions=False)

    logger.info(
        f"Supervisor completed: {completed}/{total_facts} facts processed, "
        f"summary={summary}, errors={len(errors)}"
    )

    # Update state
    state["results"] = results
    state["summary"] = summary
    state["completed"] = completed
    state["total"] = total_facts
    state["errors"] = errors

    return state


def create_supervisor_graph() -> StateGraph:
    """
    Create and compile the Supervisor Agent graph.

    The graph has a simple structure:
    - START → supervisor_node → END

    The supervisor node handles all the parallel orchestration internally.

    Returns:
        Compiled StateGraph ready for execution
    """
    # Create graph
    workflow = StateGraph(SupervisorState)

    # Add supervisor node
    workflow.add_node("supervisor", supervisor_node)

    # Set entry point
    workflow.set_entry_point("supervisor")

    # Add edge to END
    workflow.add_edge("supervisor", END)

    # Compile graph
    graph = workflow.compile()

    logger.debug("Supervisor graph compiled successfully")

    return graph


async def run_supervisor_comparison(
    facts: List[Dict[str, Any]],
    submittal_document_id: str,
    db: AsyncIOMotorDatabase,
    qdrant_client: QdrantClient,
    llm_client: Union[ChatOpenAI, ChatTogether],
    retrieval_strategy: str = "ensemble",
    top_k: int = 5,
    max_concurrency: int = 5,
    progress_callback: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    Run parallel fact comparison using the Supervisor Agent.

    This is a convenience function that creates the graph, prepares the initial
    state, and executes the workflow.

    Args:
        facts: List of spec facts to compare
        submittal_document_id: Submittal document ID
        db: MongoDB database instance
        qdrant_client: Qdrant client instance
        llm_client: LLM client (OpenAI or Together)
        retrieval_strategy: "dense", "sparse", or "ensemble"
        top_k: Number of documents to retrieve per fact
        max_concurrency: Maximum concurrent comparisons (default: 5)
        progress_callback: Optional progress callback function

    Returns:
        Dict with results, summary, and metadata
    """
    logger.info(
        f"Starting supervisor comparison: {len(facts)} facts, max_concurrency={max_concurrency}"
    )

    # Create graph
    graph = create_supervisor_graph()

    # Prepare initial state
    initial_state: SupervisorState = {
        "facts": facts,
        "submittal_document_id": submittal_document_id,
        "retrieval_strategy": retrieval_strategy,
        "top_k": top_k,
        "max_concurrency": max_concurrency,
        "db": db,
        "qdrant_client": qdrant_client,
        "llm_client": llm_client,
        "results": [],
        "summary": {"consistent": 0, "inconsistent": 0, "unclear": 0},
        "completed": 0,
        "total": len(facts),
        "errors": [],
        "progress_callback": progress_callback,
    }

    # Execute graph
    final_state = await graph.ainvoke(initial_state)

    logger.info(
        f"Supervisor comparison completed: {final_state['completed']}/{final_state['total']} facts"
    )

    return {
        "results": final_state["results"],
        "summary": final_state["summary"],
        "completed": final_state["completed"],
        "total": final_state["total"],
        "errors": final_state["errors"],
    }
