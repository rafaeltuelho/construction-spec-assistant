"""
API schemas for fact extraction endpoints.

This module defines request and response schemas for the fact extraction API.

Reference: specs/03-api-design.md (lines 198-309)
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.models.fact import Entity, Attribute, Value, Context


class FactExtractionProgress(BaseModel):
    """Progress information for fact extraction."""

    percentage: int = Field(default=0, ge=0, le=100, description="Progress percentage (0-100)")
    chunks_processed: int = Field(default=0, description="Number of chunks processed")
    total_chunks: int = Field(default=0, description="Total number of chunks")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")


class FactExtractionRequest(BaseModel):
    """
    Request schema for fact extraction.

    Attributes:
        document_id: Document identifier
        llm_model: LLM model to use (default: gpt-4o-mini)
        deduplicate: Whether to deduplicate facts (default: True)
        normalize: Whether to normalize units (default: True)
        entity_hints: Optional hints for entity types by section_id
    """

    document_id: str = Field(..., description="Document identifier")
    llm_model: str = Field(default="gpt-4o-mini", description="LLM model to use")
    deduplicate: bool = Field(default=True, description="Whether to deduplicate facts")
    normalize: bool = Field(default=True, description="Whether to normalize units")
    entity_hints: Optional[dict] = Field(None, description="Entity type hints by section_id")


class FactExtractionResponse(BaseModel):
    """
    Response schema for fact extraction initiation.

    Attributes:
        document_id: Document identifier
        extraction_job_id: Job identifier
        status: Job status
        started_at: Job start timestamp
    """

    document_id: str = Field(..., description="Document identifier")
    extraction_job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status")
    started_at: datetime = Field(..., description="Job start timestamp")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class FactExtractionJobStatus(BaseModel):
    """
    Response schema for fact extraction job status.

    Attributes:
        job_id: Job identifier
        document_id: Document identifier
        status: Job status (pending, processing, completed, failed)
        progress: Progress information (when processing)
        started_at: Job start timestamp
        completed_at: Job completion timestamp
        facts_extracted: Number of facts extracted
        facts_deduplicated: Number of facts after deduplication
        error: Error message if failed
    """

    job_id: str = Field(..., description="Job identifier")
    document_id: str = Field(..., description="Document identifier")
    status: str = Field(..., description="Job status")
    progress: Optional[FactExtractionProgress] = Field(
        None, description="Progress information (when processing)"
    )
    started_at: datetime = Field(..., description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    facts_extracted: Optional[int] = Field(None, description="Number of facts extracted")
    facts_deduplicated: Optional[int] = Field(
        None, description="Number of facts after deduplication"
    )
    error: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class FactResponse(BaseModel):
    """
    Response schema for a single fact.

    Attributes:
        fact_id: Unique fact identifier
        entity: Entity information
        attribute: Attribute information
        value: Value information
        op: Comparison operator
        qualifiers: Additional qualifiers
        context: Provenance context
    """

    fact_id: str = Field(..., description="Unique fact identifier")
    entity: Entity
    attribute: Attribute
    value: Value
    op: str = Field(..., description="Comparison operator")
    qualifiers: Optional[dict] = Field(None, description="Additional qualifiers")
    context: Context


class FactQueryRequest(BaseModel):
    """
    Request schema for querying facts.

    Attributes:
        document_id: Filter by document (optional)
        entity: Filter by entity (optional)
        attribute: Filter by attribute (optional)
        limit: Max facts to return (default: 100)
        offset: Pagination offset (default: 0)
    """

    document_id: Optional[str] = Field(None, description="Filter by document")
    entity: Optional[str] = Field(None, description="Filter by entity")
    attribute: Optional[str] = Field(None, description="Filter by attribute")
    limit: int = Field(default=100, ge=1, le=1000, description="Max facts to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


class FactQueryResponse(BaseModel):
    """
    Response schema for fact query.

    Attributes:
        facts: List of facts
        total: Total number of facts matching query
        limit: Limit used
        offset: Offset used
    """

    facts: List[FactResponse] = Field(..., description="List of facts")
    total: int = Field(..., description="Total number of facts")
    limit: int = Field(..., description="Limit used")
    offset: int = Field(..., description="Offset used")
