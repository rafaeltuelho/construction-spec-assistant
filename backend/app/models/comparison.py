"""
Document comparison models for MongoDB persistence.

This module defines Pydantic models for storing document comparison results
in MongoDB, enabling persistence across server restarts and historical queries.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class AnnotationType(str, Enum):
    """User annotation types."""

    DISREGARD = "disregard"
    CONFIRMED = "confirmed"
    NOTE = "note"


class UserAnnotation(BaseModel):
    """
    User annotation for a comparison result.

    Attributes:
        comparison_id: Comparison identifier
        annotation_type: Type of annotation (disregard, confirmed, note)
        note_text: Custom note text (required when annotation_type='note')
        annotated_by: User identifier (for future authentication)
        annotated_at: Annotation timestamp
    """

    comparison_id: str = Field(..., description="Comparison identifier")
    annotation_type: AnnotationType = Field(
        ..., description="Annotation type: 'disregard', 'confirmed', 'note'"
    )
    note_text: Optional[str] = Field(
        None, description="Custom note text (required when annotation_type='note')"
    )
    annotated_by: Optional[str] = Field(
        None, description="User identifier (for future authentication)"
    )
    annotated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Annotation timestamp"
    )


class ComparisonSummary(BaseModel):
    """
    Summary statistics for document comparison.

    Attributes:
        consistent: Number of consistent facts
        inconsistent: Number of inconsistent facts
        unclear: Number of unclear facts
    """

    consistent: int = Field(..., description="Number of consistent facts")
    inconsistent: int = Field(..., description="Number of inconsistent facts")
    unclear: int = Field(..., description="Number of unclear facts")


class RetrievedChunk(BaseModel):
    """
    Retrieved chunk information for comparison.

    Attributes:
        chunk_id: Unique chunk identifier
        content: Chunk content (truncated)
        relevance_score: Relevance score from retrieval
        page_start: Starting page number (0-indexed, from Docling provenance)
        page_end: Ending page number (0-indexed, from Docling provenance)
    """

    chunk_id: str = Field(..., description="Unique chunk identifier")
    content: str = Field(..., description="Chunk content (truncated)")
    relevance_score: float = Field(..., description="Relevance score from retrieval")
    page_start: Optional[int] = Field(
        None, description="Starting page number (0-indexed, from Docling provenance)"
    )
    page_end: Optional[int] = Field(
        None, description="Ending page number (0-indexed, from Docling provenance)"
    )


class ComparisonResult(BaseModel):
    """
    Individual fact comparison result with optional web search enhancement.

    Attributes:
        comparison_id: Unique comparison identifier
        spec_fact: Original specification fact
        submittal_document_id: Submittal document ID
        verdict: Comparison verdict (consistent, inconsistent, unclear)
        confidence: Confidence score (0.0 to 1.0)
        submittal_evidence: Direct quote from submittal
        reasoning: Explanation of the verdict
        retrieved_chunks: Chunks retrieved for comparison
        retrieval_strategy: Retrieval strategy used
        compared_at: Timestamp of comparison
        user_annotation: User annotation for this comparison (if any)
        web_search_used: Whether web search was used for this comparison (optional)
        web_evidence: Relevant information from web sources (optional)
        primary_source: Primary evidence source: 'submittal', 'web', 'both', or 'neither' (optional)
        web_sources: List of web sources used with title and URL (optional)
    """

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
    user_annotation: Optional[UserAnnotation] = Field(
        None, description="User annotation for this comparison (if any)"
    )

    # Web search enhancement fields (optional, only present when web search was used)
    web_search_used: Optional[bool] = Field(
        None, description="Whether web search was used for this comparison"
    )
    web_evidence: Optional[str] = Field(None, description="Relevant information from web sources")
    primary_source: Optional[str] = Field(
        None,
        description="Primary evidence source: 'submittal', 'web', 'both', or 'neither'",
    )
    web_sources: Optional[List[Dict[str, str]]] = Field(
        None, description="List of web sources used (title and URL)"
    )


class DocumentComparisonResult(BaseModel):
    """
    Complete document comparison result for MongoDB persistence.

    This model stores the full comparison result including all individual
    fact comparisons, summary statistics, and metadata.

    Attributes:
        job_id: Unique job identifier (used as MongoDB _id)
        spec_document_id: Specification document ID
        submittal_document_id: Submittal document ID
        total_facts: Total number of facts compared
        completed_facts: Number of facts completed
        status: Job status (pending, processing, completed, failed)
        summary: Summary statistics (available when completed)
        comparisons: Individual comparison results
        error: Error message if job failed
        created_at: Timestamp when job was created
        completed_at: Timestamp when job was completed
        retrieval_strategy: Retrieval strategy used
        top_k: Number of chunks retrieved per fact
    """

    job_id: str = Field(..., description="Unique job identifier")
    spec_document_id: str = Field(..., description="Specification document ID")
    submittal_document_id: str = Field(..., description="Submittal document ID")
    total_facts: int = Field(..., description="Total number of facts compared")
    completed_facts: int = Field(..., description="Number of facts completed")
    status: str = Field(
        ..., description="Job status: 'pending', 'processing', 'completed', 'failed'"
    )
    summary: Optional[ComparisonSummary] = Field(
        default=None, description="Summary statistics (available when completed)"
    )
    comparisons: List[ComparisonResult] = Field(
        default_factory=list, description="Individual comparison results"
    )
    error: Optional[str] = Field(default=None, description="Error message if job failed")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp when job was created"
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="Timestamp when job was completed"
    )
    retrieval_strategy: str = Field(default="ensemble", description="Retrieval strategy used")
    top_k: int = Field(default=5, description="Number of chunks retrieved per fact")
    annotations: Dict[str, List[UserAnnotation]] = Field(
        default_factory=dict, description="User annotations keyed by comparison_id"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ConclusionType(str, Enum):
    """Report conclusion types."""

    REVIEWED = "reviewed"
    REVIEWED_AS_NOTED = "reviewed_as_noted"
    REVISE_AND_RESUBMIT = "revise_and_resubmit"
    REJECTED = "rejected"
    FOR_RECORD_ONLY = "for_record_only"


class ReportAnnotation(BaseModel):
    """
    Annotation data for report generation.

    Attributes:
        comparison_id: Comparison identifier
        note_text: The note text content
        annotated_at: When the annotation was created
        spec_fact: The specification fact that was annotated
    """

    comparison_id: str = Field(..., description="Comparison identifier")
    note_text: str = Field(..., description="The note text content")
    annotated_at: datetime = Field(..., description="When the annotation was created")
    spec_fact: Dict[str, Any] = Field(..., description="The specification fact that was annotated")


class ReportResponse(BaseModel):
    """
    Response model for report generation.

    Attributes:
        job_id: Job identifier
        spec_document_id: Specification document ID
        submittal_document_id: Submittal document ID
        annotations: List of note annotations
        report_generated_at: When the report was generated
        conclusion: Saved report conclusion (if any)
    """

    job_id: str = Field(..., description="Job identifier")
    spec_document_id: str = Field(..., description="Specification document ID")
    submittal_document_id: str = Field(..., description="Submittal document ID")
    annotations: List[ReportAnnotation] = Field(
        default_factory=list, description="List of note annotations"
    )
    report_generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="When the report was generated"
    )
    conclusion: Optional["ReportConclusion"] = Field(
        None, description="Saved report conclusion (if any)"
    )


class SaveReportRequest(BaseModel):
    """
    Request model for saving report conclusion.

    Attributes:
        conclusion_type: Type of conclusion (reviewed, reviewed_as_noted, etc.)
        conclusion_comment: Optional additional comments
    """

    conclusion_type: ConclusionType = Field(..., description="Type of conclusion")
    conclusion_comment: Optional[str] = Field(None, description="Optional additional comments")


class ReportConclusion(BaseModel):
    """
    Report conclusion data.

    Attributes:
        conclusion_type: Type of conclusion
        conclusion_comment: Optional additional comments
        concluded_at: When the conclusion was saved
        concluded_by: User who saved the conclusion (for future authentication)
    """

    conclusion_type: ConclusionType = Field(..., description="Type of conclusion")
    conclusion_comment: Optional[str] = Field(None, description="Optional additional comments")
    concluded_at: datetime = Field(
        default_factory=datetime.utcnow, description="When the conclusion was saved"
    )
    concluded_by: Optional[str] = Field(
        None, description="User who saved the conclusion (for future authentication)"
    )


class SaveReportResponse(BaseModel):
    """
    Response model for saving report conclusion.

    Attributes:
        success: Whether the save was successful
        message: Success or error message
        conclusion: The saved conclusion data
    """

    success: bool = Field(..., description="Whether the save was successful")
    message: str = Field(..., description="Success or error message")
    conclusion: Optional[ReportConclusion] = Field(None, description="The saved conclusion data")
