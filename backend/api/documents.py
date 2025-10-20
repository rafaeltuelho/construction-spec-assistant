"""Document management endpoints for the Construction Spec Assistant API."""

import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Query
from fastapi.responses import JSONResponse

from ..models.api_models import (
    BaseResponse, DocumentResponse, DocumentListResponse, 
    DocumentProcessingStatus, DocumentType, DocumentStatus
)
from ..config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory storage for demo (replace with proper database in production)
documents_db: Dict[str, Dict[str, Any]] = {}


def get_services():
    """Get services from app state."""
    from ..main import app_state
    return app_state.get("services")


@router.post("/documents/upload", response_model=BaseResponse)
async def upload_document(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(...),
    metadata: Optional[str] = Form(None),
    services = Depends(get_services)
):
    """Upload and process a document."""
    try:
        # Validate file
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        if file.size > settings.max_file_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=400, 
                detail=f"File size exceeds maximum allowed size of {settings.max_file_size_mb}MB"
            )
        
        # Parse metadata
        parsed_metadata = {}
        if metadata:
            import json
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid metadata JSON")
        
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Create upload directory
        upload_dir = Path(settings.upload_directory)
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Save uploaded file
        file_path = upload_dir / f"{document_id}_{file.filename}"
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Create document record
        document_record = {
            "id": document_id,
            "filename": file.filename,
            "document_type": document_type,
            "status": DocumentStatus.UPLOADED,
            "file_size_bytes": file.size,
            "upload_timestamp": datetime.utcnow(),
            "file_path": str(file_path),
            "metadata": parsed_metadata,
            "sections": [],
            "csi_divisions": [],
            "vector_indexed": False,
            "facts_extracted": False,
        }
        
        documents_db[document_id] = document_record
        
        # Start processing in background (simplified for demo)
        try:
            await process_document_background(document_id, services)
        except Exception as e:
            logger.error(f"Background processing failed: {e}")
            document_record["status"] = DocumentStatus.FAILED
            document_record["processing_error"] = str(e)
        
        return BaseResponse(
            success=True,
            message=f"Document uploaded successfully. Document ID: {document_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


async def process_document_background(document_id: str, services):
    """Process document in background."""
    try:
        document_record = documents_db[document_id]
        document_record["status"] = DocumentStatus.PARSING
        document_record["processing_started"] = datetime.utcnow()
        
        # Parse document
        file_path = Path(document_record["file_path"])
        is_csi_spec = document_record["document_type"] == DocumentType.SPECIFICATION
        
        doc_info = services.document_parser.parse_document_with_docling(
            pdf_path=file_path,
            is_csi_spec=is_csi_spec,
            save_pictures=False,
            save_tables=False,
            write_artifacts=True
        )
        
        if doc_info["success"]:
            # Extract facts if it's a specification
            if is_csi_spec:
                facts = services.fact_extractor.harvest_facts_for_doc(
                    doc_info=doc_info,
                    entity_hints={"default": "elevator"},
                    normalize=True
                )
                document_record["extracted_facts"] = facts
                document_record["facts_extracted"] = True
            
            # Index in vector store if it's a submittal
            if document_record["document_type"] == DocumentType.SUBMITTAL:
                collection_name = f"submittal_{document_id}"
                services.vectorstore_manager.create_collection(
                    collection_name=collection_name,
                    hybrid=True
                )
                
                # Add documents to vector store
                chunk_texts = [chunk["text"] for chunk in doc_info["section_chunks"]]
                services.vectorstore_manager.add_documents(
                    collection_name=collection_name,
                    documents=chunk_texts
                )
                document_record["vector_indexed"] = True
                document_record["collection_name"] = collection_name
            
            document_record["status"] = DocumentStatus.INDEXED
            document_record["processing_completed"] = datetime.utcnow()
            document_record["sections"] = [s["header"] for s in doc_info["sections"]]
            
        else:
            document_record["status"] = DocumentStatus.FAILED
            document_record["processing_error"] = doc_info["error"]
            
    except Exception as e:
        logger.error(f"Document processing failed: {e}")
        document_record["status"] = DocumentStatus.FAILED
        document_record["processing_error"] = str(e)


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    document_type: Optional[DocumentType] = Query(None),
    status: Optional[DocumentStatus] = Query(None)
):
    """List documents with pagination and filtering."""
    try:
        # Filter documents
        filtered_docs = list(documents_db.values())
        
        if document_type:
            filtered_docs = [d for d in filtered_docs if d["document_type"] == document_type]
        
        if status:
            filtered_docs = [d for d in filtered_docs if d["status"] == status]
        
        # Paginate
        total = len(filtered_docs)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_docs = filtered_docs[start_idx:end_idx]
        
        # Convert to response format
        document_responses = []
        for doc in paginated_docs:
            doc_response = DocumentResponse(
                id=doc["id"],
                filename=doc["filename"],
                document_type=doc["document_type"],
                status=doc["status"],
                file_size_bytes=doc["file_size_bytes"],
                upload_timestamp=doc["upload_timestamp"],
                processing_started=doc.get("processing_started"),
                processing_completed=doc.get("processing_completed"),
                processing_error=doc.get("processing_error"),
                sections=doc["sections"],
                csi_divisions=doc["csi_divisions"],
                vector_indexed=doc["vector_indexed"],
                facts_extracted=doc["facts_extracted"],
                metadata=doc["metadata"]
            )
            document_responses.append(doc_response)
        
        return DocumentListResponse(
            items=document_responses,
            total=total,
            page=page,
            page_size=page_size,
            has_next=(page * page_size) < total,
            has_previous=page > 1
        )
        
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """Get document details."""
    try:
        if document_id not in documents_db:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc = documents_db[document_id]
        
        return DocumentResponse(
            id=doc["id"],
            filename=doc["filename"],
            document_type=doc["document_type"],
            status=doc["status"],
            file_size_bytes=doc["file_size_bytes"],
            upload_timestamp=doc["upload_timestamp"],
            processing_started=doc.get("processing_started"),
            processing_completed=doc.get("processing_completed"),
            processing_error=doc.get("processing_error"),
            sections=doc["sections"],
            csi_divisions=doc["csi_divisions"],
            vector_indexed=doc["vector_indexed"],
            facts_extracted=doc["facts_extracted"],
            metadata=doc["metadata"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")


@router.get("/documents/{document_id}/status", response_model=DocumentProcessingStatus)
async def get_document_status(document_id: str):
    """Get document processing status."""
    try:
        if document_id not in documents_db:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc = documents_db[document_id]
        
        # Calculate progress percentage
        progress = 0
        current_step = "uploaded"
        
        if doc["status"] == DocumentStatus.PARSING:
            progress = 50
            current_step = "parsing"
        elif doc["status"] == DocumentStatus.INDEXED:
            progress = 100
            current_step = "completed"
        elif doc["status"] == DocumentStatus.FAILED:
            progress = 0
            current_step = "failed"
        
        return DocumentProcessingStatus(
            document_id=document_id,
            status=doc["status"],
            progress_percentage=progress,
            current_step=current_step,
            error_message=doc.get("processing_error")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document status: {str(e)}")


@router.get("/documents/{document_id}/facts")
async def get_document_facts(document_id: str):
    """Get extracted facts from a document."""
    try:
        if document_id not in documents_db:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc = documents_db[document_id]
        
        if not doc.get("facts_extracted", False):
            raise HTTPException(status_code=400, detail="Facts not extracted for this document")
        
        facts = doc.get("extracted_facts", [])
        
        return {
            "document_id": document_id,
            "facts_count": len(facts),
            "facts": facts
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document facts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document facts: {str(e)}")


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and all associated data."""
    try:
        if document_id not in documents_db:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc = documents_db[document_id]
        
        # Delete file
        file_path = Path(doc["file_path"])
        if file_path.exists():
            file_path.unlink()
        
        # Delete from vector store if indexed
        if doc.get("vector_indexed") and "collection_name" in doc:
            try:
                services = get_services()
                if services:
                    # Note: Qdrant client doesn't have delete_collection method in this version
                    # In production, you'd want to implement proper cleanup
                    pass
            except Exception as e:
                logger.warning(f"Failed to clean up vector store: {e}")
        
        # Remove from database
        del documents_db[document_id]
        
        return BaseResponse(
            success=True,
            message=f"Document {document_id} deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")
