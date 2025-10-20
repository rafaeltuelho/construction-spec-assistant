"""API request/response models for the Construction Spec Assistant backend."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator

from .enums import DocumentType, DocumentStatus, ReviewStatus, FindingType


# Base Models
class BaseResponse(BaseModel):
    """Base response model."""
    success: bool
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseResponse):
    """Error response model."""
    error_code: str
    details: Optional[Dict[str, Any]] = None


class PaginatedResponse(BaseModel):
    """Paginated response model."""
    items: List[Any]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


# Document Models
class DocumentUploadRequest(BaseModel):
    """Request model for document upload."""
    filename: str = Field(..., min_length=1, max_length=255)
    document_type: DocumentType
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('filename')
    def validate_filename(cls, v):
        """Validate filename extension."""
        if not v.lower().endswith('.pdf'):
            raise ValueError('Only PDF files are supported')
        return v


class DocumentResponse(BaseModel):
    """Response model for document information."""
    id: str
    filename: str
    document_type: DocumentType
    status: DocumentStatus
    file_size_bytes: int
    upload_timestamp: datetime
    page_count: Optional[int] = None
    processing_started: Optional[datetime] = None
    processing_completed: Optional[datetime] = None
    processing_error: Optional[str] = None
    sections: List[str] = Field(default_factory=list)
    csi_divisions: List[str] = Field(default_factory=list)
    vector_indexed: bool = False
    facts_extracted: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentListResponse(PaginatedResponse):
    """Response model for document list."""
    items: List[DocumentResponse]


class DocumentProcessingStatus(BaseModel):
    """Document processing status."""
    document_id: str
    status: DocumentStatus
    progress_percentage: float = Field(ge=0, le=100)
    current_step: str
    error_message: Optional[str] = None
    estimated_completion_time: Optional[datetime] = None


# Review Models
class ReviewRequest(BaseModel):
    """Request model for initiating a review."""
    specification_document_id: str = Field(..., min_length=1)
    submittal_document_id: str = Field(..., min_length=1)
    review_scope: Optional[List[str]] = Field(default_factory=list, description="CSI division codes")
    llm_provider: Optional[str] = Field(default="openai")
    llm_model: Optional[str] = Field(default="gpt-4-turbo")
    enable_verification: bool = Field(default=True)


class Citation(BaseModel):
    """Citation model for findings."""
    source: str = Field(..., description="specification or submittal")
    page: int
    section: Optional[str] = None
    text: str


class Finding(BaseModel):
    """Finding model."""
    id: str
    finding_type: FindingType
    confidence: float = Field(ge=0.0, le=1.0)
    title: str
    description: str
    recommendation: Optional[str] = None
    specification_facts: List[str] = Field(default_factory=list)
    submittal_facts: List[str] = Field(default_factory=list)
    supporting_passages: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)


class ReviewResponse(BaseModel):
    """Response model for review results."""
    review_id: str
    specification_document_id: str
    submittal_document_id: str
    status: ReviewStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    findings: List[Finding] = Field(default_factory=list)
    summary: Optional[str] = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    processing_time_seconds: Optional[float] = None
    review_scope: List[str] = Field(default_factory=list)
    llm_provider: str
    llm_model: str
    error_message: Optional[str] = None


class FindingValidationRequest(BaseModel):
    """Request model for validating findings."""
    finding_id: str
    validation_decision: str = Field(..., regex="^(accept|reject|modify)$")
    validation_notes: Optional[str] = None
    reviewer_id: Optional[str] = None


class ReviewListResponse(PaginatedResponse):
    """Response model for review list."""
    items: List[ReviewResponse]


# Search Models
class SearchRequest(BaseModel):
    """Request model for document search."""
    query: str = Field(..., min_length=1, max_length=1000)
    document_types: Optional[List[DocumentType]] = None
    csi_divisions: Optional[List[str]] = None
    limit: int = Field(default=10, ge=1, le=100)
    exact_terms: Optional[List[str]] = None


class PassageSearchResult(BaseModel):
    """Search result for passages."""
    id: str
    text: str
    document_id: str
    passage_type: str
    page_number: int
    section_id: Optional[str] = None
    csi_division: Optional[str] = None
    title: Optional[str] = None
    vector_score: float
    bm25_score: float
    combined_score: float


class SearchResponse(BaseModel):
    """Response model for search results."""
    query: str
    total_results: int
    passages: List[PassageSearchResult]
    processing_time_seconds: float


# Health Check Models
class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    version: str
    services: Dict[str, str]  # Service name -> status
    uptime_seconds: float
