"""Fact models for the Construction Spec Assistant backend."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ValidationError, model_validator


class Entity(BaseModel):
    """Entity model for facts."""
    type: Optional[str] = None
    name: Optional[str] = None
    manufacturer: Optional[str] = None


class Attribute(BaseModel):
    """Attribute model for facts."""
    raw: str
    canonical: Optional[str] = None


class Value(BaseModel):
    """Value model for facts."""
    raw: str
    type: str                       # quantity | text | enum | boolean | range
    num: Optional[float] = None
    unit: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None

    @model_validator(mode="before")
    def check_value_fields(cls, v):
        """Validate value fields based on type."""
        t = v.get("type")
        if t == "quantity" and v.get("num") is None:
            # allow LLM to miss num; we'll backfill later if possible
            pass
        if t == "range" and (v.get("min") is None or v.get("max") is None):
            pass
        return v


class Context(BaseModel):
    """Context model for facts."""
    doc_id: str
    section_id: str
    header_path: List[str]
    source_span: str
    confidence: float = Field(ge=0.0, le=1.0)


class Fact(BaseModel):
    """Fact model for extracted information."""
    id: str
    entity: Entity
    attribute: Attribute
    value: Value
    op: str = "="
    qualifiers: Optional[Dict[str, Any]] = None
    context: Context
