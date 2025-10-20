"""Enums for the Construction Spec Assistant backend."""

from enum import Enum


class DocumentType(str, Enum):
    """Document type enumeration."""
    SPECIFICATION = "specification"
    SUBMITTAL = "submittal"
    DRAWING = "drawing"


class DocumentStatus(str, Enum):
    """Document processing status enumeration."""
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    INDEXED = "indexed"
    FAILED = "failed"


class ReviewStatus(str, Enum):
    """Review status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class FindingType(str, Enum):
    """Finding type enumeration."""
    DISCREPANCY = "discrepancy"
    CONSISTENT = "consistent"
    MISSING = "missing"
    ADDITIONAL = "additional"
    UNCLEAR = "unclear"


class RetrievalStrategy(str, Enum):
    """Retrieval strategy enumeration."""
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"


class ComparisonVerdict(str, Enum):
    """Comparison verdict enumeration."""
    CONSISTENT = "consistent"
    INCONSISTENT = "inconsistent"
    UNCLEAR = "unclear"
    GAP = "gap"
