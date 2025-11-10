"""
LangGraph comparison agent for spec-to-submittal comparison.

This module implements a state machine workflow for comparing specification
facts against submittal documents using RAG retrieval and LLM comparison.
"""

from typing import TypedDict, List, Dict, Any, Union
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langchain_together import ChatTogether
from langgraph.graph import StateGraph, END
import json
import logging

from app.retrievers.base import BaseRetriever
from app.retrievers.query_builder import QueryTerms
from app.agents.prompts import (
    COMPARISON_SYSTEM_PROMPT,
    COMPARISON_PROMPT_TEMPLATE,
    RE_EVALUATION_SYSTEM_PROMPT,
    RE_EVALUATION_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)


class ComparisonState(TypedDict):
    """
    State for comparison workflow with optional web search enhancement.

    Web search fields are optional and only used when web_search_enabled=True
    and the initial verdict is "unclear".
    """

    # Core fields (always present)
    spec_fact: Dict[str, Any]  # Input specification fact
    query: Union[str, QueryTerms]  # Query for retrieval (string or QueryTerms object)
    retrieved_docs: List[Document]  # Retrieved submittal chunks
    result: Dict[str, Any]  # Final comparison result
    error: str  # Error message if any

    # Web search fields (optional, used when web_search_enabled=True)
    web_search_enabled: bool  # Enable web search for unclear verdicts
    web_search_results: List[Dict[str, Any]]  # Web search results
    enriched_context: str  # Combined submittal + web context
    retry_count: int  # Number of re-evaluation attempts
    max_retries: int  # Maximum retry limit (default: 1)
    web_search_query: str  # Query used for web search
    web_search_error: str  # Error during web search (if any)


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

        # Log query information
        if isinstance(query, QueryTerms):
            from app.retrievers.query_builder import bm25_query_from_sparse

            bm25_query = bm25_query_from_sparse(query.sparse)
            logger.info(
                f"Retrieving documents with QueryTerms:\n"
                f"  - Dense (semantic): '{query.dense[:100]}...'\n"
                f"  - Sparse (BM25): '{bm25_query[:100]}...'"
            )
        else:
            logger.info(f"Retrieving documents for query: {query[:100]}...")

        # Pass query to retriever (supports both string and QueryTerms)
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

        # Call LLM with LangSmith metadata
        messages = [SystemMessage(content=COMPARISON_SYSTEM_PROMPT), HumanMessage(content=prompt)]

        # Add LangSmith metadata for tracing
        config = RunnableConfig(
            tags=[
                "comparison-agent",
                f"spec:{spec_fact.get('fact_id', spec_fact.get('id', 'unknown'))}",
                "verdict-check",
            ],
            metadata={
                "operation": "spec_comparison",
                "spec_fact_id": spec_fact.get("fact_id", spec_fact.get("id")),
                "entity_type": entity.get("type"),
                "entity_name": entity.get("name"),
                "attribute": attribute_str,
                "operator": operator,
                "expected_value": value_str,
                "num_retrieved_chunks": len(retrieved_docs),
                "avg_relevance_score": sum(
                    doc.metadata.get("relevance_score", 0) for doc in retrieved_docs
                )
                / len(retrieved_docs)
                if retrieved_docs
                else 0,
            },
        )

        response = await llm_client.ainvoke(messages, config=config)

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


# ============================================================================
# Web Search Helper Functions
# ============================================================================


def build_web_search_query(spec_fact: Dict[str, Any]) -> str:
    """
    Build web search query from spec fact with manufacturer information.

    This function constructs an optimized search query for finding technical
    specifications and documentation. It prioritizes manufacturer information
    (when available) to make queries more specific and relevant.

    Strategy:
    1. Extract entity (product/component name)
    2. Extract manufacturer (if present, enriched by manufacturer extraction)
    3. Extract attribute (property being compared)
    4. Handle "or equivalent" manufacturers (extract primary manufacturer)
    5. Combine into focused query with "specifications" keyword

    Manufacturer Handling:
    - If manufacturer is present: Use "manufacturer + entity_type" (highest priority)
    - If "or equivalent" suffix: Extract primary manufacturer before "or equivalent"
    - Example: "ThyssenKrupp or equivalent" → "ThyssenKrupp"
    - This provides specificity while acknowledging multiple acceptable manufacturers

    Query Examples:
    - With manufacturer: "Otis elevator emergency callback service response time specifications"
    - With standard: "ASME A17.1 CSA B44 elevator safety code requirements"
    - With capacity: "Thyssenkrupp elevator capacity 3500 lbs specifications"
    - Generic: "elevator door reopening device specifications"

    Args:
        spec_fact: Specification fact dictionary with entity, attribute, and value fields
            Expected structure:
            {
                "entity": {
                    "type": "elevator",
                    "name": "door-reopening device",
                    "manufacturer": "ThyssenKrupp or equivalent"  # Optional, enriched by manufacturer extraction
                },
                "attribute": {
                    "raw": "infrared light beams",
                    "canonical": "infrared_light_beams"
                },
                ...
            }

    Returns:
        Search query string (max 200 chars, truncated at word boundary)

    Note:
        - Manufacturer information is populated by the manufacturer extraction enhancement
          (see backend/app/services/fact_extraction.py: extract_manufacturer_mappings)
        - Without manufacturer info, queries fall back to entity_name or entity_type
        - Query length is limited to 200 chars for optimal search performance
    """
    entity = spec_fact.get("entity", {})
    attribute = spec_fact.get("attribute", {})

    # Extract components
    entity_type = entity.get("type", "")
    entity_name = entity.get("name", "")
    manufacturer = entity.get("manufacturer", "")
    attribute_raw = attribute.get("raw", "")
    attribute_canonical = attribute.get("canonical", "")

    # Build query parts
    query_parts = []

    # Add manufacturer + entity (highest priority)
    if manufacturer and entity_type:
        # Handle "or equivalent" manufacturers - extract primary manufacturer
        # Example: "ThyssenKrupp or equivalent" → "ThyssenKrupp"
        if "or equivalent" in manufacturer.lower():
            manufacturer = manufacturer.split("or equivalent")[0].strip()
        query_parts.append(f"{manufacturer} {entity_type}")
    elif entity_name:
        query_parts.append(entity_name)
    elif entity_type:
        query_parts.append(entity_type)

    # Add attribute
    if attribute_canonical:
        query_parts.append(attribute_canonical)
    elif attribute_raw:
        query_parts.append(attribute_raw)

    # Add context keywords
    query_parts.append("specifications")

    # Join and clean
    query = " ".join(query_parts)
    query = query.strip()

    # Limit length (Tavily max: 400 chars, we use 200 for safety)
    if len(query) > 200:
        query = query[:200].rsplit(" ", 1)[0]  # Cut at word boundary

    return query


def filter_search_results(
    search_results: List[Dict[str, Any]],
    spec_fact: Dict[str, Any],
    min_relevance_score: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Filter and rank web search results for relevance.

    Filtering criteria:
    1. Relevance score >= threshold
    2. Content length >= 100 chars
    3. Prioritize manufacturer sites, technical docs, standards
    4. Exclude forums, social media, ads

    Args:
        search_results: Raw search results from Tavily
        spec_fact: Specification fact for context
        min_relevance_score: Minimum relevance threshold

    Returns:
        Filtered and ranked results
    """
    filtered = []

    # Extract entity info for domain matching
    entity = spec_fact.get("entity", {})
    manufacturer = entity.get("manufacturer", "").lower()

    for result in search_results:
        url = result.get("url", "").lower()
        title = result.get("title", "").lower()
        content = result.get("content", "")
        score = result.get("score", 0.0)

        # Skip low-relevance results
        if score < min_relevance_score:
            continue

        # Skip short content
        if len(content) < 100:
            continue

        # Skip unwanted domains
        excluded_domains = [
            "reddit.com",
            "facebook.com",
            "twitter.com",
            "instagram.com",
            "pinterest.com",
            "youtube.com",
            "tiktok.com",
        ]
        if any(domain in url for domain in excluded_domains):
            continue

        # Boost manufacturer sites
        boost = 0.0
        if manufacturer and manufacturer in url:
            boost += 0.3

        # Boost technical domains
        technical_domains = [
            ".gov",
            ".edu",
            "standards",
            "specifications",
            "technical",
            "datasheet",
            "manual",
        ]
        if any(domain in url or domain in title for domain in technical_domains):
            boost += 0.2

        # Apply boost
        adjusted_score = min(1.0, score + boost)

        filtered.append(
            {
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": content,
                "score": adjusted_score,
                "raw_score": score,
            }
        )

    # Sort by adjusted score
    filtered.sort(key=lambda x: x["score"], reverse=True)

    return filtered


def build_enriched_context(
    submittal_docs: List[Document],
    web_results: List[Dict[str, Any]],
    max_web_content_length: int = 1000,
) -> str:
    """
    Build enriched context combining submittal and web search results.

    Format:
    ```
    === SUBMITTAL INFORMATION ===
    [Chunk 1] ...
    [Chunk 2] ...

    === ADDITIONAL CONTEXT FROM WEB SEARCH ===
    [Source 1: Title]
    URL: https://...
    Content: ...

    [Source 2: Title]
    URL: https://...
    Content: ...
    ```

    Args:
        submittal_docs: Retrieved submittal documents
        web_results: Filtered web search results
        max_web_content_length: Max chars per web result

    Returns:
        Enriched context string
    """
    context_parts = []

    # Add submittal information
    context_parts.append("=== SUBMITTAL INFORMATION ===\n")
    for i, doc in enumerate(submittal_docs):
        context_parts.append(
            f"[Chunk {i + 1}] (Score: {doc.metadata.get('relevance_score', 0):.3f})\n"
            f"{doc.page_content}\n"
        )

    # Add web search results
    if web_results:
        context_parts.append("\n=== ADDITIONAL CONTEXT FROM WEB SEARCH ===\n")
        for i, result in enumerate(web_results):
            title = result["title"]
            url = result["url"]
            content = result["content"]

            # Truncate long content
            if len(content) > max_web_content_length:
                content = content[:max_web_content_length] + "..."

            context_parts.append(f"\n[Source {i + 1}: {title}]\nURL: {url}\nContent: {content}\n")

    return "\n".join(context_parts)


# ============================================================================
# Web Search Node
# ============================================================================


async def web_search_node(
    state: ComparisonState,
    search_tool: Any,  # TavilySearch from langchain-tavily
    max_results: int = 3,
    min_relevance_score: float = 0.5,
) -> ComparisonState:
    """
    Search the web for additional context about the spec fact.

    This node is triggered when the initial comparison verdict is "unclear"
    and web_search_enabled=True. It searches for relevant information from
    manufacturer sites, technical documentation, and standards.

    Args:
        state: Current state with "unclear" verdict
        search_tool: TavilySearch tool from langchain-tavily package
        max_results: Maximum number of search results to retrieve
        min_relevance_score: Minimum relevance score for filtering

    Returns:
        Updated state with web_search_results and enriched_context
    """
    try:
        spec_fact = state.get("spec_fact", {})

        # Build search query from spec fact
        search_query = build_web_search_query(spec_fact)
        state["web_search_query"] = search_query

        logger.info(f"Performing web search: {search_query}")

        # Execute web search using TavilySearch.ainvoke()
        # Returns a dict with 'results' key containing list of search results
        search_response = await search_tool.ainvoke(search_query)

        # Extract results list from response
        search_results = search_response.get("results", [])

        # Filter and rank results
        filtered_results = filter_search_results(
            search_results, spec_fact, min_relevance_score=min_relevance_score
        )
        state["web_search_results"] = filtered_results

        # Build enriched context
        enriched_context = build_enriched_context(
            submittal_docs=state.get("retrieved_docs", []),
            web_results=filtered_results,
        )
        state["enriched_context"] = enriched_context

        logger.info(f"Web search complete: {len(filtered_results)} relevant results")

        return state

    except Exception as e:
        logger.error(f"Web search failed: {e}", exc_info=True)
        state["web_search_error"] = str(e)
        state["web_search_results"] = []
        state["enriched_context"] = ""
        return state


# ============================================================================
# Re-Evaluation Node
# ============================================================================


async def re_evaluate_node(
    state: ComparisonState,
    llm_client: Union[ChatOpenAI, ChatTogether],
) -> ComparisonState:
    """
    Re-evaluate comparison using enriched context from web search.

    This node is triggered after web_search_node when the initial verdict
    was "unclear". It performs a second LLM pass using the enriched context
    (submittal + web search results) to attempt to resolve the uncertainty.

    Args:
        state: Current state with enriched_context from web search
        llm_client: LLM client for re-evaluation

    Returns:
        Updated state with new result (verdict, confidence, evidence, reasoning)
    """
    try:
        spec_fact = state.get("spec_fact", {})
        enriched_context = state.get("enriched_context", "")
        original_result = state.get("result", {})
        web_results = state.get("web_search_results", [])

        # Extract spec fact components
        entity = spec_fact.get("entity", {})
        attribute = spec_fact.get("attribute", {})
        value = spec_fact.get("value", {})
        operator = spec_fact.get("op", "=")

        # Format entity
        entity_str = entity.get("name") or entity.get("type") or "Unknown"
        if entity.get("manufacturer"):
            entity_str = f"{entity.get('manufacturer')} {entity_str}"

        # Format attribute
        attribute_str = attribute.get("canonical") or attribute.get("raw") or "Unknown"

        # Format value
        value_str = value.get("raw", "Unknown")

        # Format web sources
        web_sources_str = ""
        if web_results:
            web_sources_list = []
            for i, result in enumerate(web_results):
                web_sources_list.append(
                    f"{i + 1}. {result['title']}\n   URL: {result['url']}\n   Relevance: {result['score']:.2f}"
                )
            web_sources_str = "\n".join(web_sources_list)
        else:
            web_sources_str = "No web sources found"

        # Build re-evaluation prompt
        prompt = RE_EVALUATION_PROMPT_TEMPLATE.format(
            entity=entity_str,
            attribute=attribute_str,
            operator=operator,
            value=value_str,
            original_verdict=original_result.get("verdict", "unclear"),
            original_reasoning=original_result.get("reasoning", "No reasoning provided"),
            enriched_context=enriched_context,
            web_sources=web_sources_str,
        )

        # Prepare messages
        messages = [
            SystemMessage(content=RE_EVALUATION_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        # Add LangSmith metadata
        config = RunnableConfig(
            metadata={
                "task": "re_evaluation",
                "spec_fact_id": spec_fact.get("id"),
                "entity": entity_str,
                "attribute": attribute_str,
                "original_verdict": original_result.get("verdict"),
                "web_sources_count": len(web_results),
            },
        )

        logger.debug(f"Re-evaluating with enriched context (web sources: {len(web_results)})")

        # Call LLM
        response = await llm_client.ainvoke(messages, config=config)

        # Parse JSON response
        try:
            result = json.loads(response.content)

            # Validate required fields
            required_fields = ["verdict", "confidence", "reasoning"]
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")

            # Increment retry count
            state["retry_count"] = state.get("retry_count", 0) + 1

            # Update result
            state["result"] = result

            logger.info(
                f"Re-evaluation complete: verdict={result['verdict']}, "
                f"confidence={result['confidence']:.2f}, "
                f"primary_source={result.get('primary_source', 'unknown')}"
            )

            return state

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse re-evaluation JSON: {e}")
            logger.error(f"Raw response: {response.content}")
            # Keep original "unclear" verdict
            state["error"] = f"Re-evaluation JSON parse error: {str(e)}"
            return state

    except Exception as e:
        logger.error(f"Re-evaluation failed: {e}", exc_info=True)
        # Keep original "unclear" verdict
        state["error"] = f"Re-evaluation failed: {str(e)}"
        return state


# ============================================================================
# Conditional Routing
# ============================================================================


def should_web_search(state: ComparisonState) -> str:
    """
    Determine if web search should be performed based on verdict and configuration.

    Routing logic:
    - If verdict is "unclear" AND web_search_enabled=True AND retry_count < max_retries:
      → Route to "web_search"
    - Otherwise:
      → Route to END

    Args:
        state: Current comparison state

    Returns:
        Next node name: "web_search" or END
    """
    result = state.get("result", {})
    verdict = result.get("verdict", "")
    web_search_enabled = state.get("web_search_enabled", False)
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 1)

    # Check if web search should be triggered
    if verdict == "unclear" and web_search_enabled and retry_count < max_retries:
        logger.info(
            f"Verdict is 'unclear' and web search enabled. Routing to web_search "
            f"(retry {retry_count + 1}/{max_retries})"
        )
        return "web_search"
    else:
        logger.info(f"Routing to END (verdict={verdict}, web_search_enabled={web_search_enabled})")
        return END


def create_comparison_graph(
    retriever: BaseRetriever,
    llm_client: Union[ChatOpenAI, ChatTogether],
    top_k: int = 5,
    filters: Dict[str, Any] = None,
    search_tool: Any = None,
    web_search_config: Dict[str, Any] = None,
) -> StateGraph:
    """
    Create LangGraph state machine for comparison workflow with optional web search.

    Workflow (without web search):
    1. retrieve_node: Retrieve relevant submittal chunks
    2. compare_node: Compare spec fact against retrieved chunks
    3. END: Return verdict and evidence

    Workflow (with web search enabled):
    1. retrieve_node: Retrieve relevant submittal chunks
    2. compare_node: Compare spec fact against retrieved chunks
    3. should_web_search: Check if verdict is "unclear" and web search enabled
       - If yes → web_search_node → re_evaluate_node → END
       - If no → END

    Args:
        retriever: Retriever instance (ensemble recommended)
        llm_client: LLM client (OpenAI, Together, etc.)
        top_k: Number of documents to retrieve
        filters: Optional filters (e.g., {"document_id": "doc_123"})
        search_tool: Optional Tavily search tool (required if web search enabled)
        web_search_config: Optional web search configuration:
            - max_results: Maximum web search results (default: 3)
            - min_relevance_score: Minimum relevance score (default: 0.5)

    Returns:
        Compiled StateGraph
    """
    logger.info("Creating comparison graph (web_search_enabled=%s)", search_tool is not None)

    # Default web search config
    if web_search_config is None:
        web_search_config = {"max_results": 3, "min_relevance_score": 0.5}

    # Create wrapper functions with bound parameters
    async def retrieve_wrapper(state: ComparisonState) -> ComparisonState:
        return await retrieve_node(state, retriever, top_k, filters)

    async def compare_wrapper(state: ComparisonState) -> ComparisonState:
        return await compare_node(state, llm_client)

    # Build graph
    workflow = StateGraph(ComparisonState)

    # Add core nodes
    workflow.add_node("retrieve", retrieve_wrapper)
    workflow.add_node("compare", compare_wrapper)

    # Add web search nodes if enabled
    if search_tool is not None:

        async def web_search_wrapper(state: ComparisonState) -> ComparisonState:
            return await web_search_node(
                state,
                search_tool,
                max_results=web_search_config.get("max_results", 3),
                min_relevance_score=web_search_config.get("min_relevance_score", 0.5),
            )

        async def re_evaluate_wrapper(state: ComparisonState) -> ComparisonState:
            return await re_evaluate_node(state, llm_client)

        workflow.add_node("web_search", web_search_wrapper)
        workflow.add_node("re_evaluate", re_evaluate_wrapper)

        # Add edges with conditional routing
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "compare")
        workflow.add_conditional_edges(
            "compare",
            should_web_search,
            {
                "web_search": "web_search",
                END: END,
            },
        )
        workflow.add_edge("web_search", "re_evaluate")
        workflow.add_edge("re_evaluate", END)

        logger.info("Web search nodes added to comparison graph")

    else:
        # Simple workflow without web search
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "compare")
        workflow.add_edge("compare", END)

    # Compile
    compiled_graph = workflow.compile()
    logger.info("Comparison graph compiled successfully")

    return compiled_graph
