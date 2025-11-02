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
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from fastapi.responses import JSONResponse

from app.dependencies import get_mongodb, get_qdrant
from app.services.document_processing import process_document
from app.db.mongodb import get_document, list_documents, delete_document
from app.db.qdrant import search_similar_chunks
from app.models.document import (
    DocumentUploadRequest,
    DocumentResponse,
    DocumentListResponse,
    DocumentStatus,
    DocumentType,
    ChunkSearchRequest,
    ChunkSearchResponse
)
from app.utils.logging import get_logger
from app.utils.exceptions import NotFoundError, DocumentProcessingError

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentResponse, status_code=202)
async def upload_document(
    file: UploadFile = File(..., description="PDF file to upload"),
    document_type: str = Form(..., description="Type of document: specification, submittal, product_description, or drawing"),
    title: Optional[str] = Form(None, description="Document title (optional)"),
    use_ocr: bool = Form(True, description="Enable OCR for scanned PDFs"),
    project_id: Optional[str] = Form(None, description="Project ID (optional)"),
    max_chunk_tokens: int = Form(500, description="Maximum tokens per chunk"),
    chunk_overlap_tokens: int = Form(50, description="Overlap tokens between chunks"),
    mongodb=Depends(get_mongodb),
    qdrant=Depends(get_qdrant)
):
    """
    Upload and process a PDF document.

    Processing differs based on document type:
    - **specification**: CSI-aware sectionization with hierarchical structure (PART 1/2/3)
    - **submittal**: Simple paragraph-based chunking without CSI hierarchy
    - **product_description**: Simple paragraph-based chunking
    - **drawing**: Simple paragraph-based chunking

    The document will be:
    1. Parsed with Docling (with optional OCR)
    2. Sectionized (only for specifications) or chunked (for other types)
    3. Stored in MongoDB
    4. Indexed in Qdrant

    Returns immediately with document ID. Processing happens asynchronously.
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Validate document_type
    try:
        doc_type = DocumentType(document_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document_type. Must be one of: {', '.join([t.value for t in DocumentType])}"
        )

    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = Path(tmp_file.name)

        logger.info(f"Processing uploaded file: {file.filename} [type={doc_type.value}]")

        # Process document
        document = await process_document(
            pdf_path=tmp_path,
            mongodb=mongodb,
            qdrant=qdrant,
            document_type=doc_type,
            title=title or file.filename,
            use_ocr=use_ocr,
            max_chunk_tokens=max_chunk_tokens,
            chunk_overlap_tokens=chunk_overlap_tokens
        )
        
        # Clean up temp file
        tmp_path.unlink()
        
        return DocumentResponse(**document.model_dump())
        
    except DocumentProcessingError as e:
        logger.error(f"Document processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document_by_id(
    document_id: str,
    mongodb=Depends(get_mongodb)
):
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
    mongodb=Depends(get_mongodb)
):
    """List documents with pagination."""
    try:
        skip = (page - 1) * page_size
        documents, total = await list_documents(
            mongodb,
            skip=skip,
            limit=page_size,
            status=status
        )
        
        return DocumentListResponse(
            documents=[DocumentResponse(**doc.model_dump()) for doc in documents],
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"Failed to list documents: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{document_id}", status_code=204)
async def delete_document_by_id(
    document_id: str,
    mongodb=Depends(get_mongodb),
    qdrant=Depends(get_qdrant)
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
async def search_chunks(
    request: ChunkSearchRequest,
    qdrant=Depends(get_qdrant)
):
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
            min_score=request.min_score
        )
        
        return ChunkSearchResponse(
            query=request.query,
            results=results,
            total_results=len(results)
        )
    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{document_id}/status")
async def get_document_status(
    document_id: str,
    mongodb=Depends(get_mongodb)
):
    """Get document processing status."""
    try:
        document = await get_document(mongodb, document_id)
        return {
            "document_id": document.document_id,
            "status": document.status,
            "errors": document.errors
        }
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except Exception as e:
        logger.error(f"Failed to get status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

