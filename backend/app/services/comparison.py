"""
Comparison service for spec-to-submittal comparison.

This module orchestrates the comparison workflow using retrievers and LangGraph agents.
"""

import uuid
from typing import Dict, Any, List, Optional, Union
from langchain_openai import ChatOpenAI
from langchain_together import ChatTogether
from qdrant_client import QdrantClient
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

from app.retrievers import (
    DenseRetriever,
    SparseRetriever,
    ParentDocumentRetriever,
    EnsembleRetriever,
    build_query_terms_from_fact,
    get_retriever_cache,
)
from app.agents.comparison_graph import create_comparison_graph, ComparisonState
from app.db.mongodb import get_document_chunks
from app.db.qdrant import cleanup_parent_document_collections
from app.utils.exceptions import NotFoundError, ComparisonError

logger = logging.getLogger(__name__)


async def compare_spec_to_submittal(
    spec_fact: Dict[str, Any],
    submittal_document_id: str,
    db: AsyncIOMotorDatabase,
    qdrant_client: QdrantClient,
    llm_client: Union[ChatOpenAI, ChatTogether],
    retrieval_strategy: str = "ensemble",
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Compare a specification fact against a submittal document.

    Args:
        spec_fact: Specification fact dict with entity, attribute, value, operator
        submittal_document_id: Submittal document ID to compare against
        db: MongoDB database instance
        qdrant_client: Qdrant client instance
        llm_client: OpenAI LLM client
        retrieval_strategy: "dense", "sparse", or "ensemble" (default)
        top_k: Number of documents to retrieve

    Returns:
        Comparison result dict with verdict, confidence, evidence, reasoning

    Raises:
        NotFoundError: If submittal document not found
        ComparisonError: If comparison fails
    """
    try:
        logger.info(
            f"Starting comparison: submittal_document_id={submittal_document_id}, "
            f"strategy={retrieval_strategy}, top_k={top_k}"
        )

        # Build query from spec fact
        query_terms = build_query_terms_from_fact(spec_fact)
        logger.debug(
            f"Built query: dense='{query_terms.dense[:100]}...', "
            f"sparse_must={query_terms.sparse.get('must', [])}"
        )

        # Create retriever based on strategy
        retriever = await _create_retriever(
            strategy=retrieval_strategy,
            submittal_document_id=submittal_document_id,
            db=db,
            qdrant_client=qdrant_client,
        )

        # Create comparison graph
        filters = {"document_id": submittal_document_id}
        graph = create_comparison_graph(
            retriever=retriever, llm_client=llm_client, top_k=top_k, filters=filters
        )

        # Run comparison - pass QueryTerms object to support different query formats
        initial_state: ComparisonState = {
            "spec_fact": spec_fact,
            "query": query_terms,  # Pass QueryTerms object instead of just dense query
            "retrieved_docs": [],
            "result": {},
            "error": "",
        }

        final_state = await graph.ainvoke(initial_state)

        # Check for errors
        if final_state.get("error"):
            raise ComparisonError(final_state["error"])

        result = final_state.get("result", {})

        # Add metadata
        result["comparison_id"] = str(uuid.uuid4())
        result["spec_fact"] = spec_fact
        result["submittal_document_id"] = submittal_document_id
        result["retrieval_strategy"] = retrieval_strategy
        result["retrieved_chunks"] = [
            {
                "chunk_id": doc.metadata.get("chunk_id", ""),
                "content": doc.page_content[:200] + "..."
                if len(doc.page_content) > 200
                else doc.page_content,
                "relevance_score": doc.metadata.get("relevance_score", 0.0),
                # Page number tracking (from Docling provenance)
                "page_start": doc.metadata.get("page_start"),
                "page_end": doc.metadata.get("page_end"),
            }
            for doc in final_state.get("retrieved_docs", [])
        ]

        logger.info(
            f"Comparison complete: verdict={result.get('verdict')}, "
            f"confidence={result.get('confidence', 0):.2f}"
        )

        return result

    except NotFoundError:
        raise
    except ComparisonError:
        raise
    except Exception as e:
        logger.error(f"Comparison failed: {e}", exc_info=True)
        raise ComparisonError(f"Comparison failed: {str(e)}")


async def compare_batch(
    spec_facts: List[Dict[str, Any]],
    submittal_document_id: str,
    db: AsyncIOMotorDatabase,
    qdrant_client: QdrantClient,
    llm_client: Union[ChatOpenAI, ChatTogether],
    retrieval_strategy: str = "ensemble",
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Compare multiple specification facts against a submittal document.

    Args:
        spec_facts: List of specification fact dicts
        submittal_document_id: Submittal document ID to compare against
        db: MongoDB database instance
        qdrant_client: Qdrant client instance
        llm_client: OpenAI LLM client
        retrieval_strategy: "dense", "sparse", or "ensemble" (default)
        top_k: Number of documents to retrieve per fact

    Returns:
        List of comparison result dicts

    Raises:
        NotFoundError: If submittal document not found
        ComparisonError: If comparison fails
    """
    logger.info(f"Starting batch comparison: {len(spec_facts)} facts")

    results = []
    for i, spec_fact in enumerate(spec_facts):
        try:
            logger.info(f"Processing fact {i + 1}/{len(spec_facts)}")
            result = await compare_spec_to_submittal(
                spec_fact=spec_fact,
                submittal_document_id=submittal_document_id,
                db=db,
                qdrant_client=qdrant_client,
                llm_client=llm_client,
                retrieval_strategy=retrieval_strategy,
                top_k=top_k,
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to compare fact {i + 1}: {e}")
            # Add error result
            results.append(
                {
                    "spec_fact": spec_fact,
                    "submittal_document_id": submittal_document_id,
                    "verdict": "unclear",
                    "confidence": 0.0,
                    "submittal_evidence": "Error during comparison",
                    "reasoning": f"Comparison failed: {str(e)}",
                    "error": str(e),
                }
            )

    logger.info(f"Batch comparison complete: {len(results)} results")
    return results


async def _create_retriever(
    strategy: str, submittal_document_id: str, db: AsyncIOMotorDatabase, qdrant_client: QdrantClient
):
    """
    Create retriever based on strategy with caching.

    Args:
        strategy: "dense", "sparse", "parent_document", or "ensemble"
        submittal_document_id: Document ID to retrieve from
        db: MongoDB database instance
        qdrant_client: Qdrant client instance

    Returns:
        Retriever instance

    Raises:
        NotFoundError: If document not found
        ValueError: If invalid strategy
    """
    # Get cache
    cache = get_retriever_cache()

    # Check cache for sparse and ensemble retrievers
    cache_key = f"{strategy}_{submittal_document_id}"
    if strategy in ["sparse", "ensemble"]:
        cached_retriever = cache.get(cache_key)
        if cached_retriever is not None:
            logger.info(f"Using cached retriever: {cache_key}")
            return cached_retriever

    # Get document chunks from MongoDB
    chunks = await get_document_chunks(db, submittal_document_id)

    if not chunks:
        raise NotFoundError(f"No chunks found for document {submittal_document_id}")

    logger.info(f"Loaded {len(chunks)} chunks for document {submittal_document_id}")

    # Convert to LangChain Documents
    from langchain_core.documents import Document

    documents = [
        Document(
            page_content=chunk.content,
            metadata={
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "section_title": chunk.section_title,
                "section_number": chunk.section_number or "",
                # Page number tracking (from Docling provenance)
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
            },
        )
        for chunk in chunks
    ]

    # Create retriever based on strategy
    if strategy == "dense":
        # Dense retriever uses pre-indexed Qdrant collection (no caching needed)
        return DenseRetriever(qdrant_client=qdrant_client, collection_name="construction_docs")

    elif strategy == "sparse":
        # Create and cache sparse retriever
        retriever = SparseRetriever(corpus=documents)
        cache.set(cache_key, retriever)
        logger.info(f"Cached sparse retriever: {cache_key}")
        return retriever

    elif strategy == "parent_document":
        # Use ParentDocument retriever with small-to-big strategy
        # Note: ParentDocument creates its own Qdrant collection
        return ParentDocumentRetriever(
            qdrant_client=qdrant_client,
            parent_documents=documents,
            collection_name=f"construction_docs_parent_{submittal_document_id}",
            child_chunk_size=750,
            child_chunk_overlap=75,
        )

    elif strategy == "ensemble":
        # Use ParentDocument + BM25 ensemble (optimal approach from notebook)
        parent_retriever = ParentDocumentRetriever(
            qdrant_client=qdrant_client,
            parent_documents=documents,
            collection_name=f"construction_docs_parent_{submittal_document_id}",
            child_chunk_size=750,
            child_chunk_overlap=75,
        )
        sparse_retriever = SparseRetriever(corpus=documents)

        # Create ensemble retriever
        retriever = EnsembleRetriever(
            semantic_retriever=parent_retriever,
            sparse_retriever=sparse_retriever,
            semantic_weight=0.5,
            sparse_weight=0.5,
        )

        # Cache the ensemble retriever
        cache.set(cache_key, retriever)
        logger.info(f"Cached ensemble retriever: {cache_key}")
        return retriever

    else:
        raise ValueError(f"Invalid retrieval strategy: {strategy}")


async def compare_document_to_submittal(
    spec_document_id: str,
    submittal_document_id: str,
    db: AsyncIOMotorDatabase,
    qdrant_client: QdrantClient,
    llm_client: Union[ChatOpenAI, ChatTogether],
    retrieval_strategy: str = "ensemble",
    top_k: int = 5,
    limit: int = 100,
    offset: int = 0,
    verdict_filter: str = None,
    max_concurrency: int = 5,
    enable_parallel: bool = True,
    progress_callback: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    Compare all facts from a specification document against a submittal document.

    Args:
        spec_document_id: Specification document ID containing facts
        submittal_document_id: Submittal document ID to compare against
        db: MongoDB database instance
        qdrant_client: Qdrant client instance
        llm_client: OpenAI LLM client
        retrieval_strategy: "dense", "sparse", or "ensemble" (default)
        top_k: Number of documents to retrieve per fact
        limit: Maximum number of comparisons to return
        offset: Pagination offset
        verdict_filter: Optional filter by verdict ('consistent', 'inconsistent', 'unclear')
        max_concurrency: Maximum concurrent comparisons (default: 5)
        enable_parallel: Enable parallel execution using Supervisor Agent (default: True)
        progress_callback: Optional callback for progress updates

    Returns:
        Document comparison result dict with summary and individual comparisons

    Raises:
        NotFoundError: If specification or submittal document not found
        ComparisonError: If comparison fails
    """
    try:
        logger.info(
            f"Starting document comparison: spec_document_id={spec_document_id}, "
            f"submittal_document_id={submittal_document_id}, strategy={retrieval_strategy}"
        )

        # Import get_facts_by_document
        from app.db.mongodb import get_facts_by_document, get_document
        import uuid
        from datetime import datetime

        # Verify both documents exist
        spec_doc = await get_document(db, spec_document_id)
        if not spec_doc:
            raise NotFoundError(f"Specification document not found: {spec_document_id}")

        submittal_doc = await get_document(db, submittal_document_id)
        if not submittal_doc:
            raise NotFoundError(f"Submittal document not found: {submittal_document_id}")

        # Retrieve all facts from the specification document
        facts = await get_facts_by_document(db, spec_document_id, limit=1000, offset=0)

        if not facts:
            logger.warning(f"No facts found for document {spec_document_id}")
            return {
                "comparison_id": str(uuid.uuid4()),
                "spec_document_id": spec_document_id,
                "submittal_document_id": submittal_document_id,
                "total_facts": 0,
                "status": "completed",
                "summary": {"consistent": 0, "inconsistent": 0, "unclear": 0},
                "comparisons": [],
                "compared_at": datetime.utcnow(),
            }

        logger.info(f"Retrieved {len(facts)} facts from document {spec_document_id}")

        # Convert Fact models to dicts for comparison
        facts_dicts = []
        for fact in facts:
            spec_fact = {
                "fact_id": fact.id,  # Add fact_id for context retrieval
                "entity": fact.entity.model_dump(),
                "attribute": fact.attribute.model_dump(),
                "value": fact.value.model_dump(),
                "op": fact.op,
            }
            facts_dicts.append(spec_fact)

        # Choose execution strategy based on enable_parallel flag
        if enable_parallel:
            logger.info(
                f"Using parallel execution with Supervisor Agent: max_concurrency={max_concurrency}"
            )

            # Import supervisor agent
            from app.agents.supervisor_graph import run_supervisor_comparison

            # Run parallel comparison using Supervisor Agent
            supervisor_result = await run_supervisor_comparison(
                facts=facts_dicts,
                submittal_document_id=submittal_document_id,
                db=db,
                qdrant_client=qdrant_client,
                llm_client=llm_client,
                retrieval_strategy=retrieval_strategy,
                top_k=top_k,
                max_concurrency=max_concurrency,
                progress_callback=progress_callback,
            )

            all_comparisons = supervisor_result["results"]
            summary = supervisor_result["summary"]

        else:
            logger.info("Using sequential execution (parallel disabled)")

            # Sequential execution (original implementation)
            all_comparisons = []
            summary = {"consistent": 0, "inconsistent": 0, "unclear": 0}
            total_facts = len(facts_dicts)
            completed_facts = 0

            for fact in facts_dicts:
                try:
                    # Perform comparison
                    comparison_result = await compare_spec_to_submittal(
                        spec_fact=fact,
                        submittal_document_id=submittal_document_id,
                        db=db,
                        qdrant_client=qdrant_client,
                        llm_client=llm_client,
                        retrieval_strategy=retrieval_strategy,
                        top_k=top_k,
                    )

                    # Update summary
                    verdict = comparison_result.get("verdict", "unclear")
                    if verdict in summary:
                        summary[verdict] += 1

                    all_comparisons.append(comparison_result)

                    # Update progress
                    completed_facts += 1
                    if progress_callback:
                        percentage = int((completed_facts / total_facts) * 100)
                        await progress_callback(completed_facts, total_facts, percentage)

                except Exception as e:
                    logger.error(
                        f"Failed to compare fact {fact.get('fact_id', 'unknown')}: {str(e)}"
                    )
                    # Continue with other facts even if one fails
                    summary["unclear"] += 1
                    all_comparisons.append(
                        {
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
                    )

                    # Update progress even on error
                    completed_facts += 1
                    if progress_callback:
                        percentage = int((completed_facts / total_facts) * 100)
                        await progress_callback(completed_facts, total_facts, percentage)

        # Apply verdict filter if specified
        if verdict_filter:
            all_comparisons = [c for c in all_comparisons if c.get("verdict") == verdict_filter]

        # Apply pagination
        total_comparisons = len(all_comparisons)
        paginated_comparisons = all_comparisons[offset : offset + limit]

        logger.info(
            f"Document comparison completed: {total_comparisons} total comparisons, "
            f"returning {len(paginated_comparisons)} (offset={offset}, limit={limit})"
        )

        return {
            "comparison_id": str(uuid.uuid4()),
            "spec_document_id": spec_document_id,
            "submittal_document_id": submittal_document_id,
            "total_facts": len(facts),
            "status": "completed",
            "summary": summary,
            "comparisons": paginated_comparisons,
            "compared_at": datetime.utcnow(),
        }

    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Document comparison failed: {str(e)}", exc_info=True)
        raise ComparisonError(f"Document comparison failed: {str(e)}")


async def cleanup_retriever_resources(
    qdrant_client: QdrantClient, submittal_document_id: str
) -> Dict[str, int]:
    """
    Clean up retriever resources for a document.

    This function:
    1. Deletes ParentDocument Qdrant collections
    2. Invalidates retriever cache entries

    Should be called when:
    - A document is deleted
    - A document is updated (to force re-indexing)
    - Periodic cleanup of old resources

    Args:
        qdrant_client: Qdrant client instance
        submittal_document_id: Document ID to clean up

    Returns:
        Dict with cleanup statistics
    """
    try:
        logger.info(f"Cleaning up retriever resources for document {submittal_document_id}")

        # Clean up ParentDocument collections
        collections_deleted = cleanup_parent_document_collections(
            qdrant_client, submittal_document_id
        )

        # Invalidate cache entries
        cache = get_retriever_cache()
        cache.invalidate(f"sparse_{submittal_document_id}")
        cache.invalidate(f"ensemble_{submittal_document_id}")
        cache.invalidate(f"parent_document_{submittal_document_id}")

        logger.info(
            f"Cleanup complete: {collections_deleted} collections deleted, cache invalidated"
        )

        return {
            "collections_deleted": collections_deleted,
            "cache_invalidated": True,
        }

    except Exception as e:
        logger.error(f"Failed to cleanup retriever resources: {str(e)}", exc_info=True)
        return {
            "collections_deleted": 0,
            "cache_invalidated": False,
            "error": str(e),
        }
