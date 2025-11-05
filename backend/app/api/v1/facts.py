"""
Fact extraction API endpoints.

This module provides REST API endpoints for fact extraction from construction documents.

Reference: specs/03-api-design.md (lines 198-309)
"""

import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.schemas.fact import (
    FactExtractionRequest,
    FactExtractionResponse,
    FactExtractionJobStatus,
    FactQueryResponse,
    FactResponse,
)
from app.models.fact import Fact, FactExtractionJob
from app.models.document import DocumentChunk
from app.services.fact_extraction import harvest_facts_for_doc
from app.db.mongodb import (
    get_document_chunks,
    store_facts,
    get_facts_by_document,
    get_document,
    get_fact_by_id,
)
from app.dependencies import get_mongodb, get_openai_client, LLMClient
from app.utils.logging import get_logger
from app.utils.exceptions import NotFoundError, FactExtractionError

logger = get_logger(__name__)

router = APIRouter(prefix="/facts", tags=["facts"])


# In-memory job storage (for simplicity - in production, use MongoDB or Redis)
_extraction_jobs: dict[str, FactExtractionJob] = {}


async def run_fact_extraction(
    job_id: str,
    document_id: str,
    chunks: list[DocumentChunk],
    llm_client: LLMClient,
    db: AsyncIOMotorDatabase,
    entity_hints: Optional[dict] = None,
    normalize: bool = True,
):
    """
    Background task to run fact extraction.

    Args:
        job_id: Job identifier
        document_id: Document identifier
        chunks: Document chunks
        llm_client: OpenAI LLM client
        db: MongoDB database
        entity_hints: Optional entity type hints
        normalize: Whether to normalize units
    """
    try:
        # Update job status
        _extraction_jobs[job_id].status = "processing"

        # Define progress callback
        async def update_progress(chunks_processed: int, total_chunks: int, percentage: int):
            """Update job progress."""
            from app.models.fact import FactExtractionProgress

            progress = FactExtractionProgress(
                percentage=percentage,
                chunks_processed=chunks_processed,
                total_chunks=total_chunks,
                estimated_completion=None,  # Could calculate based on processing rate
            )
            _extraction_jobs[job_id].progress = progress

            logger.info(
                f"[PROGRESS] Job {job_id} progress updated: {chunks_processed}/{total_chunks} ({percentage}%) - Progress object: {progress}"
            )
            logger.info(
                f"[PROGRESS] Job {job_id} current state: status={_extraction_jobs[job_id].status}, progress={_extraction_jobs[job_id].progress}"
            )

        # Extract facts with progress tracking
        facts = await harvest_facts_for_doc(
            document_id=document_id,
            chunks=chunks,
            llm_client=llm_client,
            entity_hints=entity_hints,
            normalize=normalize,
            progress_callback=update_progress,
        )

        # Store facts in MongoDB
        fact_ids = await store_facts(db, facts)

        # Update job status
        _extraction_jobs[job_id].status = "completed"
        _extraction_jobs[job_id].completed_at = datetime.utcnow()
        _extraction_jobs[job_id].facts_extracted = len(facts)
        _extraction_jobs[job_id].facts_deduplicated = len(facts)  # Already deduplicated

        logger.info(f"Fact extraction job {job_id} completed: {len(facts)} facts extracted")

    except Exception as e:
        logger.error(f"Fact extraction job {job_id} failed: {e}")
        _extraction_jobs[job_id].status = "failed"
        _extraction_jobs[job_id].completed_at = datetime.utcnow()
        _extraction_jobs[job_id].error = str(e)


@router.post("/extract", response_model=FactExtractionResponse, status_code=202)
async def extract_facts(
    request: FactExtractionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
    llm_client: LLMClient = Depends(get_openai_client),
):
    """
    Extract facts from a processed document.

    This endpoint initiates a background job to extract structured facts from
    a document's chunks using LLM-based extraction.

    Args:
        request: Fact extraction request
        background_tasks: FastAPI background tasks
        db: MongoDB database
        llm_client: OpenAI LLM client

    Returns:
        Fact extraction response with job ID

    Raises:
        HTTPException: If document not found or extraction fails
    """
    try:
        # Verify document exists
        document = await get_document(db, request.document_id)
        if not document:
            raise NotFoundError(f"Document not found: {request.document_id}")

        # Get document chunks
        chunks = await get_document_chunks(db, request.document_id)
        if not chunks:
            raise FactExtractionError(f"No chunks found for document: {request.document_id}")

        # Create extraction job
        job_id = f"job_fact_{uuid.uuid4().hex[:12]}"
        job = FactExtractionJob(
            job_id=job_id,
            document_id=request.document_id,
            status="pending",
            started_at=datetime.utcnow(),
        )
        _extraction_jobs[job_id] = job

        # Start background task
        background_tasks.add_task(
            run_fact_extraction,
            job_id=job_id,
            document_id=request.document_id,
            chunks=chunks,
            llm_client=llm_client,
            db=db,
            entity_hints=request.entity_hints,
            normalize=request.normalize,
        )

        logger.info(f"Started fact extraction job {job_id} for document {request.document_id}")

        return FactExtractionResponse(
            document_id=request.document_id,
            extraction_job_id=job_id,
            status="processing",
            started_at=job.started_at,
        )

    except NotFoundError as e:
        logger.error(f"Document not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FactExtractionError as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Fact extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Fact extraction failed: {str(e)}")


@router.get("/extraction/{job_id}", response_model=FactExtractionJobStatus)
async def get_extraction_job_status(job_id: str):
    """
    Get fact extraction job status.

    Args:
        job_id: Extraction job identifier

    Returns:
        Job status information

    Raises:
        HTTPException: If job not found
    """
    try:
        job = _extraction_jobs.get(job_id)
        if not job:
            raise NotFoundError(f"Job not found: {job_id}")

        return FactExtractionJobStatus(
            job_id=job.job_id,
            document_id=job.document_id,
            status=job.status,
            progress=job.progress,  # Include progress field
            started_at=job.started_at,
            completed_at=job.completed_at,
            facts_extracted=job.facts_extracted,
            facts_deduplicated=job.facts_deduplicated,
            error=job.error,
        )

    except NotFoundError as e:
        logger.error(f"Job not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")


@router.get("/{fact_id}", response_model=FactResponse)
async def get_fact(
    fact_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Get a single fact by ID.

    Args:
        fact_id: Fact identifier
        db: MongoDB database

    Returns:
        Fact details including context information

    Raises:
        HTTPException: If fact not found or retrieval fails
    """
    try:
        fact = await get_fact_by_id(db, fact_id)

        return FactResponse(
            fact_id=fact.id,
            entity=fact.entity,
            attribute=fact.attribute,
            value=fact.value,
            op=fact.op,
            qualifiers=fact.qualifiers,
            context=fact.context,
        )

    except NotFoundError as e:
        logger.error(f"Fact not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to retrieve fact: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve fact: {str(e)}")


@router.get("", response_model=FactQueryResponse)
async def query_facts(
    document_id: Optional[str] = Query(None, description="Filter by document"),
    entity: Optional[str] = Query(None, description="Filter by entity"),
    attribute: Optional[str] = Query(None, description="Filter by attribute"),
    limit: int = Query(100, ge=1, le=1000, description="Max facts to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Query extracted facts.

    Args:
        document_id: Filter by document (optional)
        entity: Filter by entity (optional)
        attribute: Filter by attribute (optional)
        limit: Max facts to return
        offset: Pagination offset
        db: MongoDB database

    Returns:
        List of facts matching query

    Raises:
        HTTPException: If query fails
    """
    try:
        # For now, only support document_id filter
        # TODO: Add entity and attribute filters
        if document_id:
            facts = await get_facts_by_document(db, document_id, limit=limit, offset=offset)
        else:
            # Get all facts (with pagination)
            collection = db["facts"]
            cursor = collection.find().skip(offset).limit(limit)
            documents = await cursor.to_list(length=limit)
            facts = [Fact(**doc) for doc in documents]

        # Convert to response format
        fact_responses = [
            FactResponse(
                fact_id=fact.id,
                entity=fact.entity,
                attribute=fact.attribute,
                value=fact.value,
                op=fact.op,
                qualifiers=fact.qualifiers,
                context=fact.context,
            )
            for fact in facts
        ]

        # Get total count
        collection = db["facts"]
        if document_id:
            total = await collection.count_documents({"context.doc_id": document_id})
        else:
            total = await collection.count_documents({})

        return FactQueryResponse(facts=fact_responses, total=total, limit=limit, offset=offset)

    except Exception as e:
        logger.error(f"Failed to query facts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to query facts: {str(e)}")
