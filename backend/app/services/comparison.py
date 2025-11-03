"""
Comparison service for spec-to-submittal comparison.

This module orchestrates the comparison workflow using retrievers and LangGraph agents.
"""

from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from qdrant_client import QdrantClient
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

from app.retrievers import (
    DenseRetriever,
    SparseRetriever,
    EnsembleRetriever,
    build_query_terms_from_fact,
)
from app.agents.comparison_graph import create_comparison_graph, ComparisonState
from app.db.mongodb import get_document_chunks
from app.utils.exceptions import NotFoundError, ComparisonError

logger = logging.getLogger(__name__)


async def compare_spec_to_submittal(
    spec_fact: Dict[str, Any],
    submittal_document_id: str,
    db: AsyncIOMotorDatabase,
    qdrant_client: QdrantClient,
    llm_client: ChatOpenAI,
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
        logger.debug(f"Built query: dense='{query_terms.dense[:100]}...'")

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

        # Run comparison
        initial_state: ComparisonState = {
            "spec_fact": spec_fact,
            "query": query_terms.dense,
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
    llm_client: ChatOpenAI,
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
    Create retriever based on strategy.

    Args:
        strategy: "dense", "sparse", or "ensemble"
        submittal_document_id: Document ID to retrieve from
        db: MongoDB database instance
        qdrant_client: Qdrant client instance

    Returns:
        Retriever instance

    Raises:
        NotFoundError: If document not found
        ValueError: If invalid strategy
    """
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
                "section_path": " > ".join(chunk.section_path) if chunk.section_path else "",
            },
        )
        for chunk in chunks
    ]

    # Create retriever based on strategy
    if strategy == "dense":
        return DenseRetriever(qdrant_client=qdrant_client, collection_name="construction_docs")
    elif strategy == "sparse":
        return SparseRetriever(corpus=documents)
    elif strategy == "ensemble":
        dense_retriever = DenseRetriever(
            qdrant_client=qdrant_client, collection_name="construction_docs"
        )
        sparse_retriever = SparseRetriever(corpus=documents)
        return EnsembleRetriever(
            dense_retriever=dense_retriever,
            sparse_retriever=sparse_retriever,
            dense_weight=0.5,
            sparse_weight=0.5,
        )
    else:
        raise ValueError(f"Invalid retrieval strategy: {strategy}")


async def compare_document_to_submittal(
    spec_document_id: str,
    submittal_document_id: str,
    db: AsyncIOMotorDatabase,
    qdrant_client: QdrantClient,
    llm_client: ChatOpenAI,
    retrieval_strategy: str = "ensemble",
    top_k: int = 5,
    limit: int = 100,
    offset: int = 0,
    verdict_filter: str = None,
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

        # Compare each fact against the submittal
        all_comparisons = []
        summary = {"consistent": 0, "inconsistent": 0, "unclear": 0}

        for fact in facts:
            try:
                # Convert Fact model to dict for comparison
                spec_fact = {
                    "entity": fact.entity,
                    "attribute": fact.attribute,
                    "value": fact.value,
                    "operator": fact.operator if hasattr(fact, "operator") else "=",
                }

                # Perform comparison
                comparison_result = await compare_spec_to_submittal(
                    spec_fact=spec_fact,
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

            except Exception as e:
                logger.error(f"Failed to compare fact {fact.fact_id}: {str(e)}")
                # Continue with other facts even if one fails
                summary["unclear"] += 1
                all_comparisons.append(
                    {
                        "comparison_id": str(uuid.uuid4()),
                        "spec_fact": {
                            "entity": fact.entity,
                            "attribute": fact.attribute,
                            "value": fact.value,
                        },
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
