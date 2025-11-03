"""
Comparison API endpoints for spec-to-submittal comparison.

This module provides REST API endpoints for comparing specification facts
against submittal documents using hybrid search and LLM comparison.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI
from typing import Dict, Any
import uuid
import logging
from datetime import datetime

from app.api.schemas.comparison import (
    CompareRequest,
    ComparisonResult,
    CompareDocumentRequest,
    DocumentComparisonResult,
    DocumentComparisonResponse,
    DocumentComparisonStatus,
    BatchCompareRequest,
    BatchComparisonResponse,
    BatchComparisonStatus,
    RetrievedChunk,
)
from app.services.comparison import (
    compare_spec_to_submittal,
    compare_document_to_submittal,
    compare_batch,
)
from app.dependencies import get_mongodb, get_qdrant, get_llm_client
from app.utils.exceptions import NotFoundError, ComparisonError

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage for jobs (in production, use Redis or database)
_batch_jobs: Dict[str, BatchComparisonStatus] = {}
_document_jobs: Dict[str, DocumentComparisonStatus] = {}


@router.post(
    "/compare",
    response_model=ComparisonResult,
    status_code=status.HTTP_200_OK,
    summary="Compare specification fact against submittal",
    description="""
    Compare a single specification fact against a submittal document.
    
    The comparison workflow:
    1. Build query from spec fact (dense + sparse representations)
    2. Retrieve relevant submittal chunks using hybrid search
    3. Compare spec requirement against retrieved evidence using LLM
    4. Return verdict (consistent/inconsistent/unclear) with confidence and reasoning
    
    **Retrieval Strategies**:
    - `dense`: Vector similarity search (semantic)
    - `sparse`: BM25 keyword search (lexical)
    - `ensemble`: Weighted combination of dense + sparse (recommended)
    """,
)
async def compare_spec_to_submittal_endpoint(
    request: CompareRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
    qdrant_client: QdrantClient = Depends(get_qdrant),
    llm_client: ChatOpenAI = Depends(get_llm_client),
) -> ComparisonResult:
    """
    Compare a specification fact against a submittal document.

    Args:
        request: Comparison request with spec fact and submittal document ID
        db: MongoDB database instance
        qdrant_client: Qdrant client instance
        llm_client: OpenAI LLM client

    Returns:
        Comparison result with verdict, confidence, evidence, and reasoning

    Raises:
        HTTPException: If comparison fails or document not found
    """
    try:
        logger.info(
            f"Comparison request: submittal_document_id={request.submittal_document_id}, "
            f"strategy={request.retrieval_strategy}, top_k={request.top_k}"
        )

        # Validate retrieval strategy
        if request.retrieval_strategy not in ["dense", "sparse", "ensemble"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid retrieval strategy: {request.retrieval_strategy}. "
                f"Must be 'dense', 'sparse', or 'ensemble'.",
            )

        # Perform comparison
        result = await compare_spec_to_submittal(
            spec_fact=request.spec_fact,
            submittal_document_id=request.submittal_document_id,
            db=db,
            qdrant_client=qdrant_client,
            llm_client=llm_client,
            retrieval_strategy=request.retrieval_strategy,
            top_k=request.top_k,
        )

        # Build response
        comparison_result = ComparisonResult(
            comparison_id=str(uuid.uuid4()),
            spec_fact=result["spec_fact"],
            submittal_document_id=result["submittal_document_id"],
            verdict=result["verdict"],
            confidence=result["confidence"],
            submittal_evidence=result["submittal_evidence"],
            reasoning=result["reasoning"],
            retrieved_chunks=[
                RetrievedChunk(**chunk) for chunk in result.get("retrieved_chunks", [])
            ],
            retrieval_strategy=result["retrieval_strategy"],
            compared_at=datetime.utcnow(),
        )

        logger.info(
            f"Comparison complete: verdict={comparison_result.verdict}, "
            f"confidence={comparison_result.confidence:.2f}"
        )

        return comparison_result

    except NotFoundError as e:
        logger.error(f"Document not found: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ComparisonError as e:
        logger.error(f"Comparison failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during comparison: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Comparison failed: {str(e)}"
        )


@router.post(
    "/compare-document",
    response_model=DocumentComparisonResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Compare all specification facts from a document against submittal",
    description="""
    Compare all extracted facts from a specification document against a submittal document.

    This endpoint initiates a document comparison job and returns immediately.
    Use the returned `job_id` to check the status and retrieve results.

    The comparison workflow:
    1. Retrieves all facts extracted from the specification document
    2. For each fact, performs hybrid search against the submittal
    3. Uses LLM to compare each fact against retrieved evidence
    4. Returns aggregated results with summary statistics

    **Note**: This is a long-running operation. Use GET /compare-document/{job_id}
    to check status and retrieve results.

    **Retrieval Strategies**:
    - `dense`: Vector similarity search (semantic)
    - `sparse`: BM25 keyword search (lexical)
    - `ensemble`: Weighted combination of dense + sparse (recommended)
    """,
)
async def compare_document_to_submittal_endpoint(
    request: CompareDocumentRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
    qdrant_client: QdrantClient = Depends(get_qdrant),
    llm_client: ChatOpenAI = Depends(get_llm_client),
) -> DocumentComparisonResponse:
    """
    Initiate a document comparison job.

    Args:
        request: Document comparison request with spec and submittal document IDs
        db: MongoDB database instance
        qdrant_client: Qdrant client instance
        llm_client: OpenAI LLM client

    Returns:
        Document comparison response with job_id and status

    Raises:
        HTTPException: If job initiation fails
    """
    try:
        job_id = str(uuid.uuid4())

        logger.info(
            f"Initiating document comparison job: job_id={job_id}, "
            f"spec_document_id={request.spec_document_id}, "
            f"submittal_document_id={request.submittal_document_id}"
        )

        # Validate retrieval strategy
        if request.retrieval_strategy not in ["dense", "sparse", "ensemble"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid retrieval strategy: {request.retrieval_strategy}. "
                f"Must be 'dense', 'sparse', or 'ensemble'.",
            )

        # Get total facts count from MongoDB
        from app.db.mongodb import get_facts_by_document

        facts = await get_facts_by_document(db, request.spec_document_id)
        total_facts = len(facts)

        if total_facts == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No facts found for specification document: {request.spec_document_id}",
            )

        # Create document comparison job
        document_job = DocumentComparisonStatus(
            job_id=job_id,
            spec_document_id=request.spec_document_id,
            submittal_document_id=request.submittal_document_id,
            total_facts=total_facts,
            completed_facts=0,
            status="processing",
            comparisons=[],
            created_at=datetime.utcnow(),
        )
        _document_jobs[job_id] = document_job

        # Process comparison asynchronously (in production, use task queue)
        try:
            result = await compare_document_to_submittal(
                spec_document_id=request.spec_document_id,
                submittal_document_id=request.submittal_document_id,
                db=db,
                qdrant_client=qdrant_client,
                llm_client=llm_client,
                retrieval_strategy=request.retrieval_strategy,
                top_k=request.top_k,
            )

            # Convert results to ComparisonResult objects
            from app.api.schemas.comparison import ComparisonSummary

            comparison_results = [ComparisonResult(**comp) for comp in result["comparisons"]]

            # Update job status
            document_job.status = "completed"
            document_job.completed_facts = len(comparison_results)
            document_job.summary = ComparisonSummary(**result["summary"])
            document_job.comparisons = comparison_results
            document_job.completed_at = datetime.utcnow()

            logger.info(
                f"Document comparison complete: job_id={job_id}, "
                f"total_facts={total_facts}, completed={len(comparison_results)}"
            )

        except Exception as e:
            logger.error(f"Document comparison failed: job_id={job_id}, error={e}", exc_info=True)
            document_job.status = "failed"
            document_job.error = str(e)
            document_job.completed_at = datetime.utcnow()

        return DocumentComparisonResponse(
            job_id=job_id,
            status=document_job.status,
            spec_document_id=request.spec_document_id,
            submittal_document_id=request.submittal_document_id,
            total_facts=total_facts,
            message=f"Document comparison job {document_job.status}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate document comparison: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate document comparison: {str(e)}",
        )


@router.get(
    "/compare-document/{job_id}",
    response_model=DocumentComparisonStatus,
    status_code=status.HTTP_200_OK,
    summary="Get document comparison job status and results",
    description="""
    Retrieve the status and results of a document comparison job.

    **Status values**:
    - `pending`: Job is queued but not started
    - `processing`: Job is currently running
    - `completed`: Job finished successfully
    - `failed`: Job failed with an error

    **Pagination**: Use query parameters `limit` and `offset` to paginate through results.
    **Filtering**: Use `verdict_filter` to filter by verdict type.
    """,
)
async def get_document_comparison_status(
    job_id: str,
    limit: int = 100,
    offset: int = 0,
    verdict_filter: str = None,
) -> DocumentComparisonStatus:
    """
    Get document comparison job status and results.

    Args:
        job_id: Job identifier
        limit: Maximum number of comparisons to return
        offset: Pagination offset
        verdict_filter: Optional filter by verdict

    Returns:
        Document comparison status with results if completed

    Raises:
        HTTPException: If job not found
    """
    try:
        logger.info(f"Retrieving document comparison status: job_id={job_id}")

        if job_id not in _document_jobs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}"
            )

        job = _document_jobs[job_id]

        # Apply filters and pagination if job is completed
        if job.status == "completed" and job.comparisons:
            comparisons = job.comparisons

            # Apply verdict filter
            if verdict_filter:
                if verdict_filter not in ["consistent", "inconsistent", "unclear"]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid verdict filter: {verdict_filter}. "
                        f"Must be 'consistent', 'inconsistent', or 'unclear'.",
                    )
                comparisons = [c for c in comparisons if c.verdict == verdict_filter]

            # Apply pagination
            total_comparisons = len(comparisons)
            comparisons = comparisons[offset : offset + limit]

            # Create a copy of the job with filtered/paginated results
            job_copy = job.model_copy()
            job_copy.comparisons = comparisons

            logger.info(
                f"Job status: job_id={job_id}, status={job.status}, "
                f"completed={job.completed_facts}/{job.total_facts}, "
                f"returned={len(comparisons)}/{total_comparisons}"
            )

            return job_copy

        logger.info(
            f"Job status: job_id={job_id}, status={job.status}, "
            f"completed={job.completed_facts}/{job.total_facts}"
        )

        return job

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve job status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job status: {str(e)}",
        )


@router.post(
    "/batch",
    response_model=BatchComparisonResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Batch compare multiple specification facts",
    description="""
    Compare multiple specification facts against a submittal document.
    
    This endpoint initiates a batch comparison job and returns immediately.
    Use the returned `batch_id` to check the status and retrieve results.
    
    **Note**: In production, this should use a task queue (e.g., Celery, RQ).
    Currently, it processes synchronously but returns 202 Accepted.
    """,
)
async def batch_compare_endpoint(
    request: BatchCompareRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
    qdrant_client: QdrantClient = Depends(get_qdrant),
    llm_client: ChatOpenAI = Depends(get_llm_client),
) -> BatchComparisonResponse:
    """
    Batch compare multiple specification facts against a submittal document.

    Args:
        request: Batch comparison request with spec facts and submittal document ID
        db: MongoDB database instance
        qdrant_client: Qdrant client instance
        llm_client: OpenAI LLM client

    Returns:
        Batch comparison response with batch_id and status

    Raises:
        HTTPException: If batch comparison fails
    """
    try:
        batch_id = str(uuid.uuid4())

        logger.info(
            f"Batch comparison request: batch_id={batch_id}, "
            f"total_facts={len(request.spec_facts)}, "
            f"submittal_document_id={request.submittal_document_id}"
        )

        # Validate retrieval strategy
        if request.retrieval_strategy not in ["dense", "sparse", "ensemble"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid retrieval strategy: {request.retrieval_strategy}",
            )

        # Create batch job
        batch_job = BatchComparisonStatus(
            batch_id=batch_id,
            total_facts=len(request.spec_facts),
            completed_facts=0,
            status="processing",
            results=[],
            created_at=datetime.utcnow(),
        )
        _batch_jobs[batch_id] = batch_job

        # Process batch (in production, this should be async with a task queue)
        try:
            results = await compare_batch(
                spec_facts=request.spec_facts,
                submittal_document_id=request.submittal_document_id,
                db=db,
                qdrant_client=qdrant_client,
                llm_client=llm_client,
                retrieval_strategy=request.retrieval_strategy,
                top_k=request.top_k,
            )

            # Convert results to ComparisonResult objects
            comparison_results = []
            for result in results:
                comparison_results.append(
                    ComparisonResult(
                        comparison_id=str(uuid.uuid4()),
                        spec_fact=result["spec_fact"],
                        submittal_document_id=result["submittal_document_id"],
                        verdict=result["verdict"],
                        confidence=result["confidence"],
                        submittal_evidence=result["submittal_evidence"],
                        reasoning=result["reasoning"],
                        retrieved_chunks=[
                            RetrievedChunk(**chunk) for chunk in result.get("retrieved_chunks", [])
                        ],
                        retrieval_strategy=result["retrieval_strategy"],
                        compared_at=datetime.utcnow(),
                    )
                )

            # Update batch job
            batch_job.status = "completed"
            batch_job.completed_facts = len(results)
            batch_job.results = comparison_results
            batch_job.completed_at = datetime.utcnow()

            logger.info(f"Batch comparison complete: batch_id={batch_id}, results={len(results)}")

        except Exception as e:
            logger.error(f"Batch comparison failed: {e}", exc_info=True)
            batch_job.status = "failed"
            batch_job.error = str(e)
            batch_job.completed_at = datetime.utcnow()

        return BatchComparisonResponse(
            batch_id=batch_id,
            status=batch_job.status,
            total_facts=batch_job.total_facts,
            message=f"Batch comparison {batch_job.status}",
        )

    except Exception as e:
        logger.error(f"Failed to initiate batch comparison: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate batch comparison: {str(e)}",
        )


@router.get(
    "/batch/{batch_id}",
    response_model=BatchComparisonStatus,
    status_code=status.HTTP_200_OK,
    summary="Get batch comparison results",
    description="""
    Retrieve the status and results of a batch comparison job.
    
    **Status values**:
    - `pending`: Job is queued but not started
    - `processing`: Job is currently running
    - `completed`: Job finished successfully
    - `failed`: Job failed with an error
    """,
)
async def get_batch_results(batch_id: str) -> BatchComparisonStatus:
    """
    Get batch comparison results.

    Args:
        batch_id: Batch job identifier

    Returns:
        Batch comparison status with results if completed

    Raises:
        HTTPException: If batch job not found
    """
    try:
        logger.info(f"Retrieving batch results: batch_id={batch_id}")

        if batch_id not in _batch_jobs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Batch job not found: {batch_id}"
            )

        batch_job = _batch_jobs[batch_id]

        logger.info(
            f"Batch status: batch_id={batch_id}, status={batch_job.status}, "
            f"completed={batch_job.completed_facts}/{batch_job.total_facts}"
        )

        return batch_job

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve batch results: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve batch results: {str(e)}",
        )
