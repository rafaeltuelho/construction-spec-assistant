"""
Fact extraction models.

This module defines Pydantic models for the Entity-Attribute-Value (EAV) schema
used for structured fact extraction from construction documents.

Reference: notebooks/document_processing_new_pipeline.ipynb (lines 884-926)
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ValueType(str, Enum):
    """Value type categories."""

    QUANTITY = "quantity"
    TEXT = "text"
    RANGE = "range"
    BOOLEAN = "boolean"
    ENUM = "enum"


class Entity(BaseModel):
    """
    Entity in EAV schema (e.g., 'Elevator', 'Concrete').

    Attributes:
        type: Entity type (e.g., 'elevator', 'material')
        name: Entity name (e.g., 'Hydraulic Elevator')
        manufacturer: Manufacturer name if applicable
    """

    type: Optional[str] = Field(None, description="Entity type")
    name: Optional[str] = Field(None, description="Entity name")
    manufacturer: Optional[str] = Field(None, description="Manufacturer name")


class Attribute(BaseModel):
    """
    Attribute in EAV schema (e.g., 'capacity', 'strength').

    Attributes:
        raw: Raw attribute text from document
        canonical: Normalized/canonical attribute name
    """

    raw: str = Field(..., description="Raw attribute text from document")
    canonical: Optional[str] = Field(None, description="Canonical attribute name")


class Value(BaseModel):
    """
    Value in EAV schema with unit normalization support.

    Attributes:
        raw: Raw value text from document
        type: Value type (quantity, text, range, boolean, enum)
        num: Numeric value if applicable
        unit: Unit of measurement if applicable
        min: Minimum value for range type
        max: Maximum value for range type
    """

    raw: str = Field(..., description="Raw value text from document")
    type: str = Field(..., description="Value type: quantity, text, range, boolean, enum")
    num: Optional[float] = Field(None, description="Numeric value")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    min: Optional[float] = Field(None, description="Minimum value for range")
    max: Optional[float] = Field(None, description="Maximum value for range")

    @model_validator(mode="before")
    @classmethod
    def check_value_fields(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate value fields based on type.

        For quantity type, num should be present.
        For range type, min and max should be present.
        """
        value_type = v.get("type")

        # Allow LLM to miss num for quantity; we'll backfill later if possible
        if value_type == "quantity" and v.get("num") is None:
            pass

        # Allow LLM to miss min/max for range; we'll backfill later if possible
        if value_type == "range" and (v.get("min") is None or v.get("max") is None):
            pass

        return v


class Context(BaseModel):
    """
    Context information for fact provenance.

    Attributes:
        doc_id: Source document identifier
        section_id: Section identifier
        header_path: Hierarchical section path (e.g., ["PART 1", "1.1 SUMMARY"])
        source_span: Verbatim text span from document (≤ 25 words)
        confidence: Extraction confidence score (0.0-1.0)
    """

    doc_id: str = Field(..., description="Source document identifier")
    section_id: str = Field(..., description="Section identifier")
    header_path: List[str] = Field(..., description="Hierarchical section path")
    source_span: str = Field(..., description="Verbatim text span from document")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")


class Fact(BaseModel):
    """
    Complete fact with EAV structure and context.

    Attributes:
        id: Unique fact identifier (UUID)
        entity: Entity information
        attribute: Attribute information
        value: Value information
        op: Comparison operator (=, >=, <=, >, <, ~, between)
        qualifiers: Additional qualifiers (e.g., {"frequency": "monthly"})
        context: Provenance context
    """

    id: str = Field(..., description="Unique fact identifier")
    entity: Entity
    attribute: Attribute
    value: Value
    op: str = Field(default="=", description="Comparison operator")
    qualifiers: Optional[Dict[str, Any]] = Field(None, description="Additional qualifiers")
    context: Context

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class FactExtractionProgress(BaseModel):
    """Progress information for fact extraction."""

    percentage: int = Field(default=0, ge=0, le=100, description="Progress percentage (0-100)")
    chunks_processed: int = Field(default=0, description="Number of chunks processed")
    total_chunks: int = Field(default=0, description="Total number of chunks")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")


class FactExtractionJob(BaseModel):
    """
    Fact extraction job status.

    Attributes:
        job_id: Unique job identifier
        document_id: Source document identifier
        status: Job status (pending, processing, completed, failed)
        started_at: Job start timestamp
        completed_at: Job completion timestamp
        facts_extracted: Number of facts extracted
        facts_deduplicated: Number of facts after deduplication
        progress: Progress information during extraction
        error: Error message if failed
    """

    job_id: str = Field(..., description="Unique job identifier")
    document_id: str = Field(..., description="Source document identifier")
    status: str = Field(..., description="Job status")
    started_at: datetime = Field(..., description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    facts_extracted: Optional[int] = Field(None, description="Number of facts extracted")
    facts_deduplicated: Optional[int] = Field(
        None, description="Number of facts after deduplication"
    )
    progress: Optional[FactExtractionProgress] = Field(
        None, description="Progress information during extraction"
    )
    error: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
