"""
Document domain models.

This module defines Pydantic models for documents, sections, and chunks
used throughout the document processing pipeline.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Document type classification."""

    SPECIFICATION = "specification"
    SUBMITTAL = "submittal"
    PRODUCT_DESCRIPTION = "product_description"
    DRAWING = "drawing"


class DocumentStatus(str, Enum):
    """Document processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingError(BaseModel):
    """Error information from processing."""

    stage: str = Field(..., description="Processing stage where error occurred")
    error_type: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DocumentMetadata(BaseModel):
    """Document metadata."""

    document_type: DocumentType = Field(..., description="Type of document")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(default="application/pdf")
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_timestamp: Optional[datetime] = None
    used_ocr: bool = Field(default=False, description="Whether OCR was used")
    ocr_engine: Optional[str] = None
    parse_time: float = Field(default=0.0, description="Parse time in seconds")


class ProcessingStats(BaseModel):
    """Statistics from document processing."""

    total_sections: int = Field(default=0)
    sections_by_level: Dict[str, int] = Field(
        default_factory=dict,
        description="Section counts by level (keys are strings for MongoDB compatibility)",
    )
    total_chunks: int = Field(default=0)
    total_tokens: int = Field(default=0)
    avg_chunk_tokens: float = Field(default=0.0)


class ProcessingProgress(BaseModel):
    """Progress information for document processing."""

    percentage: int = Field(default=0, ge=0, le=100, description="Progress percentage (0-100)")
    current_stage: str = Field(default="pending", description="Current processing stage")
    stages: List[str] = Field(
        default_factory=lambda: ["parsing", "sectionizing", "chunking", "indexing"],
        description="List of processing stages",
    )
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")


class Document(BaseModel):
    """Main document entity."""

    document_id: str = Field(..., description="Unique document identifier")
    title: str = Field(..., description="Document title")
    status: DocumentStatus = Field(default=DocumentStatus.PENDING)
    metadata: DocumentMetadata
    markdown_content: Optional[str] = None
    processing_stats: Optional[ProcessingStats] = None
    progress: Optional[ProcessingProgress] = Field(
        None, description="Processing progress information"
    )
    errors: List[ProcessingError] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentSection(BaseModel):
    """Flattened document section for storage."""

    section_id: str = Field(..., description="Unique section identifier")
    document_id: str = Field(..., description="Parent document ID")
    title: str = Field(..., description="Section title")
    level: int = Field(..., ge=1, le=5)
    section_number: Optional[str] = None
    content: str = Field(default="")
    parent_section_id: Optional[str] = None
    order_index: int = Field(..., description="Order in document")
    # New fields for enhanced section tracking
    header_path: List[str] = Field(
        default_factory=list, description="Full hierarchical path from root to this section"
    )
    page_start: Optional[int] = Field(
        None, description="Starting page number (0-indexed, from Docling provenance)"
    )
    page_end: Optional[int] = Field(
        None, description="Ending page number (0-indexed, from Docling provenance)"
    )


class DocumentChunk(BaseModel):
    """Document chunk for vector storage."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    document_id: str = Field(..., description="Parent document ID")
    section_id: str = Field(..., description="Parent section ID")
    section_title: str
    section_number: Optional[str] = None
    section_level: int
    content: str
    token_count: int
    chunk_index: int
    total_chunks: int
    embedding: Optional[List[float]] = None
    # Page number tracking (from Docling provenance)
    page_start: Optional[int] = Field(
        None, description="Starting page number (0-indexed, from Docling provenance)"
    )
    page_end: Optional[int] = Field(
        None, description="Ending page number (0-indexed, from Docling provenance)"
    )


# Request/Response Models


class DocumentUploadRequest(BaseModel):
    """Request model for document upload."""

    title: Optional[str] = Field(None, description="Document title (optional)")
    use_ocr: bool = Field(default=True, description="Enable OCR for scanned PDFs")
    max_chunk_tokens: int = Field(default=500, ge=100, le=2000)
    chunk_overlap_tokens: int = Field(default=50, ge=0, le=500)


class DocumentResponse(BaseModel):
    """Response model for document."""

    document_id: str
    title: str
    status: DocumentStatus
    metadata: DocumentMetadata
    processing_stats: Optional[ProcessingStats] = None
    progress: Optional[ProcessingProgress] = Field(
        None, description="Processing progress information"
    )
    errors: List[ProcessingError] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    processing_job_id: Optional[str] = Field(
        None, description="Processing job ID for status polling"
    )
    estimated_duration_seconds: Optional[int] = Field(
        None, description="Estimated processing duration in seconds"
    )


class DocumentListResponse(BaseModel):
    """Response model for document list."""

    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int


class DocumentProcessingResponse(BaseModel):
    """Response model for document processing status."""

    document_id: str
    status: DocumentStatus
    progress: Optional[str] = None
    errors: List[ProcessingError] = Field(default_factory=list)


class ChunkSearchRequest(BaseModel):
    """Request model for chunk search."""

    query: str = Field(..., min_length=1)
    document_id: Optional[str] = None
    top_k: int = Field(default=10, ge=1, le=100)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ChunkSearchResult(BaseModel):
    """Search result for a chunk."""

    chunk_id: str
    document_id: str
    section_title: str
    content: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChunkSearchResponse(BaseModel):
    """Response model for chunk search."""

    query: str
    results: List[ChunkSearchResult]
    total_results: int
