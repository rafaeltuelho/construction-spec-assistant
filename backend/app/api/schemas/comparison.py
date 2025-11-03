"""
Pydantic schemas for comparison API endpoints.

These schemas define request and response models for spec-to-submittal comparison.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class CompareRequest(BaseModel):
    """Request schema for single comparison."""

    spec_fact: Dict[str, Any] = Field(
        ..., description="Specification fact to compare (entity, attribute, value, operator)"
    )
    submittal_document_id: str = Field(
        ..., description="ID of the submittal document to compare against"
    )
    retrieval_strategy: str = Field(
        default="ensemble", description="Retrieval strategy: 'dense', 'sparse', or 'ensemble'"
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve")


class RetrievedChunk(BaseModel):
    """Schema for retrieved chunk information."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    content: str = Field(..., description="Chunk content (truncated)")
    relevance_score: float = Field(..., description="Relevance score from retrieval")


class ComparisonResult(BaseModel):
    """Response schema for comparison result."""

    comparison_id: str = Field(..., description="Unique comparison identifier")
    spec_fact: Dict[str, Any] = Field(..., description="Original specification fact")
    submittal_document_id: str = Field(..., description="Submittal document ID")
    verdict: str = Field(
        ..., description="Comparison verdict: 'consistent', 'inconsistent', or 'unclear'"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)")
    submittal_evidence: str = Field(
        ..., description="Direct quote from submittal supporting the verdict"
    )
    reasoning: str = Field(..., description="Explanation of the verdict")
    retrieved_chunks: List[RetrievedChunk] = Field(
        default_factory=list, description="Chunks retrieved for comparison"
    )
    retrieval_strategy: str = Field(..., description="Retrieval strategy used")
    compared_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of comparison"
    )


class BatchCompareRequest(BaseModel):
    """Request schema for batch comparison."""

    spec_facts: List[Dict[str, Any]] = Field(
        ..., min_length=1, description="List of specification facts to compare"
    )
    submittal_document_id: str = Field(
        ..., description="ID of the submittal document to compare against"
    )
    retrieval_strategy: str = Field(
        default="ensemble", description="Retrieval strategy: 'dense', 'sparse', or 'ensemble'"
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve per fact")


class BatchComparisonStatus(BaseModel):
    """Response schema for batch comparison status."""

    batch_id: str = Field(..., description="Unique batch identifier")
    total_facts: int = Field(..., description="Total number of facts to compare")
    completed_facts: int = Field(..., description="Number of facts completed")
    status: str = Field(
        ..., description="Batch status: 'pending', 'processing', 'completed', 'failed'"
    )
    results: List[ComparisonResult] = Field(
        default_factory=list, description="Comparison results (available when completed)"
    )
    error: Optional[str] = Field(default=None, description="Error message if batch failed")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp when batch was created"
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="Timestamp when batch was completed"
    )


class BatchComparisonResponse(BaseModel):
    """Response schema for batch comparison initiation."""

    batch_id: str = Field(..., description="Unique batch identifier")
    status: str = Field(..., description="Initial status: 'pending' or 'processing'")
    total_facts: int = Field(..., description="Total number of facts to compare")
    message: str = Field(..., description="Status message")


class CompareDocumentRequest(BaseModel):
    """Request schema for document-level comparison."""

    spec_document_id: str = Field(
        ..., description="ID of the specification document containing facts to compare"
    )
    submittal_document_id: str = Field(
        ..., description="ID of the submittal document to compare against"
    )
    retrieval_strategy: str = Field(
        default="ensemble", description="Retrieval strategy: 'dense', 'sparse', or 'ensemble'"
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve per fact")


class ComparisonSummary(BaseModel):
    """Summary statistics for document comparison."""

    consistent: int = Field(..., description="Number of consistent facts")
    inconsistent: int = Field(..., description="Number of inconsistent facts")
    unclear: int = Field(..., description="Number of unclear facts")


class DocumentComparisonResponse(BaseModel):
    """Response schema for document comparison job initiation."""

    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Initial status: 'pending' or 'processing'")
    spec_document_id: str = Field(..., description="Specification document ID")
    submittal_document_id: str = Field(..., description="Submittal document ID")
    total_facts: int = Field(..., description="Total number of facts to compare")
    message: str = Field(..., description="Status message")


class DocumentComparisonStatus(BaseModel):
    """Response schema for document comparison job status."""

    job_id: str = Field(..., description="Unique job identifier")
    spec_document_id: str = Field(..., description="Specification document ID")
    submittal_document_id: str = Field(..., description="Submittal document ID")
    total_facts: int = Field(..., description="Total number of facts to compare")
    completed_facts: int = Field(..., description="Number of facts completed")
    status: str = Field(
        ..., description="Job status: 'pending', 'processing', 'completed', 'failed'"
    )
    summary: Optional[ComparisonSummary] = Field(
        default=None, description="Summary statistics (available when completed)"
    )
    comparisons: List[ComparisonResult] = Field(
        default_factory=list, description="Individual comparison results (available when completed)"
    )
    error: Optional[str] = Field(default=None, description="Error message if job failed")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp when job was created"
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="Timestamp when job was completed"
    )


class DocumentComparisonResult(BaseModel):
    """Response schema for document-level comparison (deprecated - use DocumentComparisonStatus)."""

    comparison_id: str = Field(..., description="Unique document comparison identifier")
    spec_document_id: str = Field(..., description="Specification document ID")
    submittal_document_id: str = Field(..., description="Submittal document ID")
    total_facts: int = Field(..., description="Total number of facts compared")
    status: str = Field(..., description="Comparison status: 'completed', 'partial', 'failed'")
    summary: ComparisonSummary = Field(..., description="Summary statistics")
    comparisons: List[ComparisonResult] = Field(
        default_factory=list, description="Individual comparison results"
    )
    compared_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of comparison"
    )
