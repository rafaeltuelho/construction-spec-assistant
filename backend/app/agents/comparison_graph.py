"""
LangGraph comparison agent for spec-to-submittal comparison.

This module implements a state machine workflow for comparing specification
facts against submittal documents using RAG retrieval and LLM comparison.
"""

from typing import TypedDict, List, Dict, Any, Union
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_together import ChatTogether
from langgraph.graph import StateGraph, END
import json
import logging

from app.retrievers.base import BaseRetriever
from app.agents.prompts import COMPARISON_SYSTEM_PROMPT, COMPARISON_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


class ComparisonState(TypedDict):
    """State for comparison workflow."""

    spec_fact: Dict[str, Any]  # Input specification fact
    query: str  # Generated query for retrieval
    retrieved_docs: List[Document]  # Retrieved submittal chunks
    result: Dict[str, Any]  # Final comparison result
    error: str  # Error message if any


async def retrieve_node(
    state: ComparisonState, retriever: BaseRetriever, top_k: int = 5, filters: Dict[str, Any] = None
) -> ComparisonState:
    """
    Retrieve relevant submittal chunks.

    Args:
        state: Current state
        retriever: Retriever instance
        top_k: Number of documents to retrieve
        filters: Optional filters (e.g., document_id)

    Returns:
        Updated state with retrieved documents
    """
    try:
        query = state.get("query", "")
        logger.info(f"Retrieving documents for query: {query[:100]}...")

        docs = await retriever.retrieve(query=query, top_k=top_k, filters=filters)

        state["retrieved_docs"] = docs
        logger.info(f"Retrieved {len(docs)} documents")

        return state

    except Exception as e:
        logger.error(f"Retrieval failed: {e}", exc_info=True)
        state["error"] = f"Retrieval failed: {str(e)}"
        state["retrieved_docs"] = []
        return state


async def compare_node(
    state: ComparisonState, llm_client: Union[ChatOpenAI, ChatTogether]
) -> ComparisonState:
    """
    Compare spec fact against retrieved chunks using LLM.

    Args:
        state: Current state with retrieved documents
        llm_client: OpenAI LLM client

    Returns:
        Updated state with comparison result
    """
    try:
        spec_fact = state.get("spec_fact", {})
        retrieved_docs = state.get("retrieved_docs", [])

        if not retrieved_docs:
            logger.warning("No documents retrieved, returning unclear verdict")
            state["result"] = {
                "verdict": "unclear",
                "confidence": 0.0,
                "submittal_evidence": "No relevant information found in submittal",
                "reasoning": "No documents were retrieved that match the specification requirement",
            }
            return state

        logger.info("Comparing spec fact against submittal")

        # Extract fact components
        entity = spec_fact.get("entity", {})
        attribute = spec_fact.get("attribute", {})
        value = spec_fact.get("value", {})
        operator = spec_fact.get("op", "=")

        # Format entity
        entity_str = entity.get("type", "") or entity.get("name", "") or "Unknown"
        if entity.get("manufacturer"):
            entity_str += f" (Manufacturer: {entity['manufacturer']})"

        # Format attribute
        attribute_str = attribute.get("raw", "") or attribute.get("canonical", "") or "Unknown"

        # Format value
        value_str = value.get("raw", "") or str(value.get("num", "")) + " " + str(
            value.get("unit", "")
        )

        # Build context from retrieved documents
        context = "\n\n".join(
            [
                f"[Chunk {i + 1}] (Score: {doc.metadata.get('relevance_score', 0):.3f})\n{doc.page_content}"
                for i, doc in enumerate(retrieved_docs)
            ]
        )

        # Build comparison prompt
        prompt = COMPARISON_PROMPT_TEMPLATE.format(
            entity=entity_str,
            attribute=attribute_str,
            operator=operator,
            value=value_str,
            context=context,
        )

        # Call LLM
        messages = [SystemMessage(content=COMPARISON_SYSTEM_PROMPT), HumanMessage(content=prompt)]

        response = await llm_client.ainvoke(messages)

        # Parse JSON response
        try:
            result = json.loads(response.content)

            # Validate result structure
            required_fields = ["verdict", "confidence", "submittal_evidence", "reasoning"]
            if not all(field in result for field in required_fields):
                raise ValueError(f"Missing required fields in LLM response: {result}")

            # Validate verdict
            if result["verdict"] not in ["consistent", "inconsistent", "unclear"]:
                logger.warning(f"Invalid verdict: {result['verdict']}, defaulting to 'unclear'")
                result["verdict"] = "unclear"

            # Validate confidence
            if not isinstance(result["confidence"], (int, float)) or not (
                0 <= result["confidence"] <= 1
            ):
                logger.warning(f"Invalid confidence: {result['confidence']}, defaulting to 0.5")
                result["confidence"] = 0.5

            state["result"] = result
            logger.info(
                f"Comparison complete: verdict={result['verdict']}, confidence={result['confidence']:.2f}"
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"LLM response: {response.content}")
            state["result"] = {
                "verdict": "unclear",
                "confidence": 0.0,
                "submittal_evidence": "Error parsing LLM response",
                "reasoning": f"Failed to parse comparison result: {str(e)}",
            }

        return state

    except Exception as e:
        logger.error(f"Comparison failed: {e}", exc_info=True)
        state["error"] = f"Comparison failed: {str(e)}"
        state["result"] = {
            "verdict": "unclear",
            "confidence": 0.0,
            "submittal_evidence": "Error during comparison",
            "reasoning": f"Comparison failed: {str(e)}",
        }
        return state


def create_comparison_graph(
    retriever: BaseRetriever,
    llm_client: Union[ChatOpenAI, ChatTogether],
    top_k: int = 5,
    filters: Dict[str, Any] = None,
) -> StateGraph:
    """
    Create LangGraph state machine for comparison workflow.

    Workflow:
    1. retrieve_node: Retrieve relevant submittal chunks
    2. compare_node: Compare spec fact against retrieved chunks
    3. END: Return verdict and evidence

    Args:
        retriever: Retriever instance (ensemble recommended)
        llm_client: OpenAI LLM client
        top_k: Number of documents to retrieve
        filters: Optional filters (e.g., {"document_id": "doc_123"})

    Returns:
        Compiled StateGraph
    """
    logger.info("Creating comparison graph")

    # Create wrapper functions with bound parameters
    async def retrieve_wrapper(state: ComparisonState) -> ComparisonState:
        return await retrieve_node(state, retriever, top_k, filters)

    async def compare_wrapper(state: ComparisonState) -> ComparisonState:
        return await compare_node(state, llm_client)

    # Build graph
    workflow = StateGraph(ComparisonState)

    # Add nodes
    workflow.add_node("retrieve", retrieve_wrapper)
    workflow.add_node("compare", compare_wrapper)

    # Add edges
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "compare")
    workflow.add_edge("compare", END)

    # Compile
    compiled_graph = workflow.compile()
    logger.info("Comparison graph compiled successfully")

    return compiled_graph
