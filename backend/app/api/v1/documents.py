"""
Document API endpoints.

This module provides REST API endpoints for document operations:
- Upload and process documents
- Retrieve document information
- List documents
- Delete documents
- Search chunks
"""

import tempfile
from pathlib import Path
from typing import Optional
from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException,
    Depends,
    Query,
    BackgroundTasks,
)
from fastapi.responses import JSONResponse

from app.dependencies import get_mongodb, get_qdrant
from app.services.document_processing import process_document
from app.db.mongodb import (
    get_document,
    list_documents,
    delete_document,
    store_document,
    update_document_status,
)
from app.db.qdrant import search_similar_chunks
from app.models.document import (
    DocumentUploadRequest,
    DocumentResponse,
    DocumentListResponse,
    DocumentStatus,
    DocumentType,
    ChunkSearchRequest,
    ChunkSearchResponse,
    Document,
    DocumentMetadata,
    ProcessingProgress,
)
from app.utils.logging import get_logger
from app.utils.exceptions import NotFoundError, DocumentProcessingError
import uuid
from datetime import datetime, timedelta

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


async def process_document_background(
    pdf_path: Path,
    document_id: str,
    mongodb,
    qdrant,
    document_type: DocumentType,
    title: str,
    use_ocr: bool,
    max_chunk_tokens: int,
    chunk_overlap_tokens: int,
):
    """Background task to process document asynchronously."""
    try:
        logger.info(f"[{document_id}] Starting background document processing")

        # Process document
        await process_document(
            pdf_path=pdf_path,
            mongodb=mongodb,
            qdrant=qdrant,
            document_type=document_type,
            title=title,
            use_ocr=use_ocr,
            max_chunk_tokens=max_chunk_tokens,
            chunk_overlap_tokens=chunk_overlap_tokens,
            document_id=document_id,  # Pass existing document_id
        )

        logger.info(f"[{document_id}] Background document processing completed")

    except Exception as e:
        logger.error(f"[{document_id}] Background processing failed: {str(e)}")
        await update_document_status(mongodb, document_id, DocumentStatus.FAILED, error=str(e))
    finally:
        # Clean up temp file
        if pdf_path.exists():
            pdf_path.unlink()


@router.post("/upload", response_model=DocumentResponse, status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF file to upload"),
    document_type: str = Form(
        ...,
        description="Type of document: specification, submittal, product_description, or drawing",
    ),
    title: Optional[str] = Form(None, description="Document title (optional)"),
    use_ocr: bool = Form(True, description="Enable OCR for scanned PDFs"),
    project_id: Optional[str] = Form(None, description="Project ID (optional)"),
    max_chunk_tokens: int = Form(500, description="Maximum tokens per chunk"),
    chunk_overlap_tokens: int = Form(50, description="Overlap tokens between chunks"),
    mongodb=Depends(get_mongodb),
    qdrant=Depends(get_qdrant),
):
    """
    Upload and process a PDF document.

    Processing differs based on document type:

    **CSI Specification** (`document_type="specification"`):
    - CSI-aware hierarchical sectionization (PART 1/2/3 structure)
    - Section-aware chunking with token limits
    - Stored in MongoDB (sections + chunks)
    - **NOT indexed in Qdrant** (used for fact extraction only)

    **Submittal/Product Description/Drawing** (`document_type="submittal"`, `"product_description"`, `"drawing"`):
    - Simple paragraph-based chunking without CSI hierarchy
    - Stored in MongoDB (chunks only, no sections)
    - **Indexed in Qdrant** for vector similarity search

    **Processing Pipeline:**
    1. Parse PDF with Docling (with optional OCR)
    2. Sectionize (specifications only) or chunk (other types)
    3. Store in MongoDB
    4. Index in Qdrant (submittals/product descriptions/drawings only)

    Returns immediately with document ID. Processing happens asynchronously.

    **Note:** Per the notebook logic, CSI specifications are used for fact extraction
    and comparison, while submittals/product descriptions are indexed for retrieval.
    """
    # Validate file type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported. Please upload a file with .pdf extension.",
        )

    # Validate MIME type if available
    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Only application/pdf is supported.",
        )

    # Validate document_type
    try:
        doc_type = DocumentType(document_type)
    except ValueError:
        raise HTTPException(  # noqa: B904
            status_code=400,
            detail=f"Invalid document_type. Must be one of: {', '.join([t.value for t in DocumentType])}",
        )

    try:
        # Read file content and validate size
        content = await file.read()
        file_size_mb = len(content) / (1024 * 1024)

        # Import settings for max file size
        from app.config import settings

        if file_size_mb > settings.max_file_size_mb:
            raise HTTPException(
                status_code=400,
                detail=f"File size ({file_size_mb:.2f} MB) exceeds maximum allowed size ({settings.max_file_size_mb} MB)",
            )

        logger.info(f"File validation passed: {file.filename} ({file_size_mb:.2f} MB)")

        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(content)
            tmp_path = Path(tmp_file.name)

        # Generate document ID
        document_id = str(uuid.uuid4())
        doc_title = title or file.filename

        # Create initial document record with pending status
        metadata = DocumentMetadata(
            document_type=doc_type,
            filename=file.filename,
            file_size=len(content),
            mime_type="application/pdf",
        )

        # Initialize progress tracking
        progress = ProcessingProgress(
            percentage=0,
            current_stage="pending",
            stages=["parsing", "sectionizing", "chunking", "indexing"],
            estimated_completion=datetime.utcnow() + timedelta(seconds=int(file_size_mb * 2) + 10),
        )

        document = Document(
            document_id=document_id,
            title=doc_title,
            status=DocumentStatus.PENDING,
            metadata=metadata,
            progress=progress,
        )

        # Store initial document in MongoDB
        await store_document(mongodb, document)

        logger.info(f"Created document record: {document_id} [type={doc_type.value}]")

        # Estimate processing duration based on file size
        estimated_duration = int(file_size_mb * 2) + 10  # 2 seconds per MB + 10s buffer

        # Schedule background processing
        background_tasks.add_task(
            process_document_background,
            tmp_path,
            document_id,
            mongodb,
            qdrant,
            doc_type,
            doc_title,
            use_ocr,
            max_chunk_tokens,
            chunk_overlap_tokens,
        )

        logger.info(f"Scheduled background processing for document: {document_id}")

        # Return 202 response immediately
        response = DocumentResponse(**document.model_dump())
        response.processing_job_id = document_id  # Use document_id as job_id
        response.estimated_duration_seconds = estimated_duration

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during upload: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document_by_id(document_id: str, mongodb=Depends(get_mongodb)):
    """Get document by ID."""
    try:
        document = await get_document(mongodb, document_id)
        return DocumentResponse(**document.model_dump())
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except Exception as e:
        logger.error(f"Failed to retrieve document: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=DocumentListResponse)
async def list_all_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[DocumentStatus] = None,
    mongodb=Depends(get_mongodb),
):
    """List documents with pagination."""
    try:
        skip = (page - 1) * page_size
        documents, total = await list_documents(mongodb, skip=skip, limit=page_size, status=status)

        return DocumentListResponse(
            documents=[DocumentResponse(**doc.model_dump()) for doc in documents],
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        logger.error(f"Failed to list documents: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{document_id}", status_code=204)
async def delete_document_by_id(
    document_id: str, mongodb=Depends(get_mongodb), qdrant=Depends(get_qdrant)
):
    """Delete document and all related data."""
    try:
        # Delete from MongoDB
        await delete_document(mongodb, document_id)

        # Delete from Qdrant
        from app.db.qdrant import delete_document_chunks

        await delete_document_chunks(qdrant, document_id)

        return JSONResponse(status_code=204, content=None)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except Exception as e:
        logger.error(f"Failed to delete document: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/search", response_model=ChunkSearchResponse)
async def search_chunks(request: ChunkSearchRequest, qdrant=Depends(get_qdrant)):
    """
    Search for similar chunks using vector similarity.

    Optionally filter by document_id.
    """
    try:
        results = await search_similar_chunks(
            client=qdrant,
            query=request.query,
            top_k=request.top_k,
            document_id=request.document_id,
            min_score=request.min_score,
        )

        return ChunkSearchResponse(query=request.query, results=results, total_results=len(results))
    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{document_id}/status")
async def get_document_status(document_id: str, mongodb=Depends(get_mongodb)):
    """Get document processing status."""
    try:
        document = await get_document(mongodb, document_id)
        return {
            "document_id": document.document_id,
            "status": document.status,
            "errors": document.errors,
        }
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except Exception as e:
        logger.error(f"Failed to get status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
