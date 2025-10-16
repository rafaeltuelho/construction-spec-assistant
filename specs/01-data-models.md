# Data Models Specification

## Overview

This specification defines the data models, database schemas, and data structures used throughout the Architectural Submittal Reviewer system.

## Database Design

### MongoDB Collections

#### 1. Documents Collection
Stores metadata about uploaded PDF documents.

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

class DocumentType(str, Enum):
    SPECIFICATION = "specification"
    SUBMITTAL = "submittal"
    DRAWING = "drawing"

class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    INDEXED = "indexed"
    FAILED = "failed"

class Document(BaseModel):
    """Document metadata and processing status"""
    id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    file_path: str = Field(..., description="Local file system path")
    document_type: DocumentType = Field(..., description="Type of document")
    file_size_bytes: int = Field(..., description="File size in bytes")
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: DocumentStatus = Field(default=DocumentStatus.UPLOADED)
    
    # Processing metadata
    page_count: Optional[int] = Field(None, description="Number of pages in PDF")
    processing_started: Optional[datetime] = None
    processing_completed: Optional[datetime] = None
    processing_error: Optional[str] = None
    
    # Document structure
    sections: List[str] = Field(default_factory=list, description="Document section identifiers")
    csi_divisions: List[str] = Field(default_factory=list, description="CSI division codes")
    
    # PDF-specific metadata (from real data analysis)
    pdf_version: Optional[str] = Field(None, description="PDF version (e.g., 1.7, 1.4)")
    creator: Optional[str] = Field(None, description="PDF creator (e.g., Bluebeam Revu x64)")
    producer: Optional[str] = Field(None, description="PDF producer (e.g., Bluebeam PDF Library 21)")
    creation_date: Optional[datetime] = Field(None, description="PDF creation date")
    modification_date: Optional[datetime] = Field(None, description="PDF modification date")
    
    # Drawing-specific metadata
    page_rotation: Optional[int] = Field(None, description="Page rotation in degrees (0, 90, 180, 270)")
    media_box: Optional[Dict[str, float]] = Field(None, description="MediaBox dimensions [x1, y1, x2, y2]")
    annotation_count: Optional[int] = Field(None, description="Total number of annotations")
    xobject_count: Optional[int] = Field(None, description="Number of embedded XObjects")
    
    # Indexing status
    vector_indexed: bool = Field(default=False)
    facts_extracted: bool = Field(default=False)
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional document metadata")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

#### 2. Passages Collection
Stores text chunks extracted from documents for retrieval.

```python
class Passage(BaseModel):
    """Text passage for retrieval and indexing"""
    id: str = Field(..., description="Unique passage identifier")
    document_id: str = Field(..., description="Reference to source document")
    passage_type: str = Field(..., description="Type: text, table, figure, etc.")
    
    # Content
    text: str = Field(..., description="Extracted text content")
    title: Optional[str] = Field(None, description="Section or table title")
    
    # Location information
    page_number: int = Field(..., description="Page number in document")
    section_id: Optional[str] = Field(None, description="Document section identifier")
    span_start: Optional[int] = Field(None, description="Character start position")
    span_end: Optional[int] = Field(None, description="Character end position")
    
    # Structural metadata
    heading_level: Optional[int] = Field(None, description="Heading hierarchy level")
    csi_division: Optional[str] = Field(None, description="CSI division code")
    subsection: Optional[str] = Field(None, description="Subsection identifier")
    
    # Indexing metadata
    token_count: int = Field(..., description="Approximate token count")
    embedding_model: Optional[str] = Field(None, description="Model used for embeddings")
    vector_id: Optional[str] = Field(None, description="ID in vector database")
    
    # Table-specific fields
    table_headers: Optional[List[str]] = Field(None, description="Table column headers")
    table_rows: Optional[List[Dict[str, Any]]] = Field(None, description="Table data")
    
    # Figure-specific fields
    figure_caption: Optional[str] = Field(None, description="Figure caption text")
    figure_coordinates: Optional[Dict[str, float]] = Field(None, description="Bounding box coordinates")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

#### 3. Facts Collection
Stores normalized construction specifications as atomic facts.

```python
class FactType(str, Enum):
    NUMERIC = "numeric"
    BOOLEAN = "boolean"
    TEXT = "text"
    ENUM = "enum"

class ComparisonOperator(str, Enum):
    EQUALS = "="
    GREATER_THAN = ">"
    GREATER_EQUAL = ">="
    LESS_THAN = "<"
    LESS_EQUAL = "<="
    NOT_EQUALS = "!="
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"

class Fact(BaseModel):
    """Normalized construction specification fact"""
    id: str = Field(..., description="Stable fact identifier")
    document_id: str = Field(..., description="Source document reference")
    passage_id: Optional[str] = Field(None, description="Source passage reference")
    
    # Fact content
    topic: str = Field(..., description="Subject area (e.g., hydraulic_elevator, insulation, concrete)")
    attribute: str = Field(..., description="Property name (e.g., capacity_lbs, min_thickness_in)")
    operator: ComparisonOperator = Field(..., description="Comparison operator")
    value: Any = Field(..., description="Fact value")
    value_type: FactType = Field(..., description="Data type of value")
    
    # Units and normalization
    original_value: str = Field(..., description="Original text from document")
    normalized_value: Any = Field(..., description="Normalized/parsed value")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    unit_converted: Optional[str] = Field(None, description="Converted to standard unit")
    
    # Source location
    source: Dict[str, Any] = Field(..., description="Source location details")
    page_number: int = Field(..., description="Source page number")
    span_text: str = Field(..., description="Exact text span from document")
    
    # Classification
    csi_division: Optional[str] = Field(None, description="CSI division code (e.g., 14 24 00)")
    section_id: Optional[str] = Field(None, description="Document section (e.g., Part 2)")
    subsection_id: Optional[str] = Field(None, description="Subsection identifier (e.g., 2.1.A)")
    
    # Manufacturer and product information
    manufacturer: Optional[str] = Field(None, description="Product manufacturer")
    product_code: Optional[str] = Field(None, description="Manufacturer product code")
    model_number: Optional[str] = Field(None, description="Model or part number")
    
    # Standards and certifications
    standards: List[str] = Field(default_factory=list, description="Applicable standards (e.g., ASTM, ANSI)")
    certifications: List[str] = Field(default_factory=list, description="Certifications or approvals")
    
    # Confidence and validation
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")
    validated: bool = Field(default=False, description="Human validation status")
    validation_notes: Optional[str] = Field(None, description="Validation comments")
    
    # Relationships
    related_facts: List[str] = Field(default_factory=list, description="Related fact IDs")
    conflicting_facts: List[str] = Field(default_factory=list, description="Conflicting fact IDs")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

#### 4. Reviews Collection
Stores document comparison reviews and findings.

```python
class ReviewStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class FindingType(str, Enum):
    DISCREPANCY = "discrepancy"
    CONSISTENT = "consistent"
    MISSING = "missing"
    ADDITIONAL = "additional"
    UNCLEAR = "unclear"

class Finding(BaseModel):
    """Individual finding from document comparison"""
    id: str = Field(..., description="Unique finding identifier")
    finding_type: FindingType = Field(..., description="Type of finding")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    
    # Content
    title: str = Field(..., description="Finding title")
    description: str = Field(..., description="Detailed description")
    recommendation: Optional[str] = Field(None, description="Recommended action")
    
    # Source references
    specification_facts: List[str] = Field(default_factory=list, description="Related spec fact IDs")
    submittal_facts: List[str] = Field(default_factory=list, description="Related submittal fact IDs")
    supporting_passages: List[str] = Field(default_factory=list, description="Supporting passage IDs")
    
    # Citations
    citations: List[Dict[str, Any]] = Field(default_factory=list, description="Source citations")
    
    # Validation
    human_validated: bool = Field(default=False)
    validation_decision: Optional[str] = Field(None, description="Accept/Reject/Modify")
    validation_notes: Optional[str] = Field(None, description="Human reviewer notes")
    validated_by: Optional[str] = Field(None, description="Reviewer identifier")
    validated_at: Optional[datetime] = None

class Review(BaseModel):
    """Complete document comparison review"""
    id: str = Field(..., description="Unique review identifier")
    specification_document_id: str = Field(..., description="Spec document reference")
    submittal_document_id: str = Field(..., description="Submittal document reference")
    
    # Status and metadata
    status: ReviewStatus = Field(default=ReviewStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Review configuration
    review_scope: List[str] = Field(default_factory=list, description="CSI divisions to review")
    llm_provider: str = Field(..., description="LLM provider used")
    llm_model: str = Field(..., description="LLM model used")
    
    # Results
    findings: List[Finding] = Field(default_factory=list, description="Review findings")
    summary: Optional[str] = Field(None, description="Review summary")
    
    # Processing metadata
    context_pack_size: Optional[int] = Field(None, description="Total tokens in context pack")
    processing_time_seconds: Optional[float] = Field(None, description="Total processing time")
    error_message: Optional[str] = Field(None, description="Error details if failed")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

#### 5. Context Packs Collection
Stores assembled context packs for LLM processing.

```python
class ContextPack(BaseModel):
    """Assembled context pack for LLM comparison"""
    id: str = Field(..., description="Unique context pack identifier")
    review_id: str = Field(..., description="Associated review")
    
    # Content
    specification_passages: List[str] = Field(..., description="Spec passage IDs")
    submittal_passages: List[str] = Field(..., description="Submittal passage IDs")
    facts: List[str] = Field(..., description="Relevant fact IDs")
    
    # Metadata
    total_tokens: int = Field(..., description="Total token count")
    passage_count: int = Field(..., description="Number of passages")
    fact_count: int = Field(..., description="Number of facts")
    
    # Prompt engineering
    system_prompt: str = Field(..., description="System prompt used")
    user_prompt: str = Field(..., description="User prompt template")
    output_schema: Dict[str, Any] = Field(..., description="Expected output schema")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    used_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

## Database Indexes

### MongoDB Indexes

```python
# Documents collection indexes
documents_indexes = [
    {"document_type": 1, "status": 1},
    {"upload_timestamp": -1},
    {"csi_divisions": 1},
    {"filename": 1}
]

# Passages collection indexes
passages_indexes = [
    {"document_id": 1},
    {"document_id": 1, "page_number": 1},
    {"csi_division": 1},
    {"section_id": 1},
    {"passage_type": 1}
]

# Facts collection indexes
facts_indexes = [
    {"document_id": 1},
    {"topic": 1, "attribute": 1},
    {"csi_division": 1},
    {"confidence_score": -1},
    {"validated": 1},
    {"created_at": -1}
]

# Reviews collection indexes
reviews_indexes = [
    {"specification_document_id": 1, "submittal_document_id": 1},
    {"status": 1},
    {"created_at": -1},
    {"llm_provider": 1, "llm_model": 1}
]

# Context Packs collection indexes
context_packs_indexes = [
    {"review_id": 1},
    {"created_at": -1}
]
```

## Real-World Data Examples

### Sample Document Records

#### Hydraulic Elevator Specification Document
```json
{
  "id": "doc_spec_14_24_00_001",
  "filename": "Spec 14 24 00 - Hydraulic Elevators.pdf",
  "document_type": "specification",
  "pdf_version": "1.7",
  "creator": "Bluebeam Revu x64",
  "producer": "Bluebeam PDF Library 21",
  "page_count": 6,
  "csi_divisions": ["14 24 00"],
  "sections": ["Part 1 - General", "Part 2 - Products", "Part 3 - Execution"],
  "metadata": {
    "creation_date": "2025-01-08T12:55:59-05:00",
    "modification_date": "2025-01-09T12:18:15-05:00"
  }
}
```

#### Architectural Drawing Document
```json
{
  "id": "doc_drawings_001",
  "filename": "Architectural Drawings.pdf",
  "document_type": "drawing",
  "pdf_version": "1.4",
  "page_count": 8,
  "page_rotation": 90,
  "media_box": {"width": 2160, "height": 3024},
  "annotation_count": 97,
  "xobject_count": 5,
  "csi_divisions": ["14 24 00"],
  "metadata": {
    "drawing_type": "floor_plan",
    "contains_elevator": true
  }
}
```

### Sample Fact Records

#### Hydraulic Elevator Capacity Fact
```json
{
  "id": "fact:14-24-00:2.1.A:capacity",
  "topic": "hydraulic_elevator",
  "attribute": "capacity_lbs",
  "operator": "=",
  "value": 2500,
  "value_type": "numeric",
  "unit": "lbs",
  "original_value": "2,500 pounds",
  "csi_division": "14 24 00",
  "section_id": "Part 2",
  "subsection_id": "2.1.A",
  "manufacturer": "Otis Elevator Company",
  "standards": ["ASME A17.1", "ANSI A17.2"],
  "source": {
    "pdf": "Spec_14_24_00_Hydraulic_Elevators.pdf",
    "page": 2,
    "span": "Part 2, Section 2.1.A"
  },
  "confidence_score": 0.95
}
```

#### Elevator Speed Specification
```json
{
  "id": "fact:14-24-00:2.1.B:speed",
  "topic": "hydraulic_elevator",
  "attribute": "travel_speed_fpm",
  "operator": ">=",
  "value": 150,
  "value_type": "numeric",
  "unit": "fpm",
  "original_value": "150 feet per minute minimum",
  "csi_division": "14 24 00",
  "section_id": "Part 2",
  "subsection_id": "2.1.B",
  "standards": ["ASME A17.1"],
  "source": {
    "pdf": "Spec_14_24_00_Hydraulic_Elevators.pdf",
    "page": 2,
    "span": "Part 2, Section 2.1.B"
  },
  "confidence_score": 0.92
}
```

### CSI Division Classification Patterns

#### Standard CSI Format Recognition
```python
# CSI Division Pattern (from real data analysis)
CSI_PATTERN = r'^\d{2}\s\d{2}\s\d{2}$'

# Examples from real documents:
CSI_EXAMPLES = [
    "14 24 00",  # Hydraulic Elevators
    "07 21 00",  # Thermal Insulation
    "03 30 00",  # Cast-in-Place Concrete
    "08 11 00",  # Metal Doors and Frames
    "09 68 00",  # Carpeting
    "11 53 00",  # Residential Appliances
    "16 22 00",  # Plumbing Fixtures
    "17 23 00",  # HVAC Piping and Pumps
    "18 51 00",  # Interior Lighting
    "23 05 00"   # Common Work Results for HVAC
]

# Specification Section Patterns
SPEC_SECTION_PATTERNS = {
    "Part 1": "General",
    "Part 2": "Products", 
    "Part 3": "Execution"
}
```

#### Drawing Annotation Patterns
```python
# Drawing annotation types (from real data analysis)
ANNOTATION_TYPES = [
    "text_callout",      # Text annotations with leaders
    "dimension",         # Dimension lines and text
    "symbol",           # Standard symbols
    "detail_reference",  # Detail callouts
    "elevation_marker",  # Elevation markers
    "grid_line",        # Grid line references
    "section_marker"    # Section cut markers
]

# XObject types found in architectural drawings
XOBJECT_TYPES = [
    "BBA",   # Main drawing content
    "BBA1",  # Detail drawings
    "BBA2",  # Additional details
    "BBA3",  # Section views
    "BBA4",  # Elevation views
    "BBA5"   # Plan views
]
```

## Data Validation

### Pydantic Models for API

```python
from pydantic import BaseModel, validator, Field
from typing import Optional, List, Union

class DocumentUploadRequest(BaseModel):
    """Request model for document upload"""
    filename: str = Field(..., min_length=1, max_length=255)
    document_type: DocumentType
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('filename')
    def validate_filename(cls, v):
        if not v.lower().endswith('.pdf'):
            raise ValueError('Only PDF files are supported')
        return v

class ReviewRequest(BaseModel):
    """Request model for initiating a review"""
    specification_document_id: str = Field(..., min_length=1)
    submittal_document_id: str = Field(..., min_length=1)
    review_scope: Optional[List[str]] = Field(default_factory=list)
    llm_provider: Optional[str] = Field(default="openai")
    llm_model: Optional[str] = Field(default="gpt-4-turbo")

class ReviewResponse(BaseModel):
    """Response model for review results"""
    review_id: str
    status: ReviewStatus
    findings: List[Finding]
    summary: Optional[str] = None
    processing_time_seconds: Optional[float] = None

class FindingValidationRequest(BaseModel):
    """Request model for validating findings"""
    finding_id: str
    validation_decision: str = Field(..., regex="^(accept|reject|modify)$")
    validation_notes: Optional[str] = None
```

## Data Migration and Versioning

### Schema Versioning Strategy

```python
class SchemaVersion(BaseModel):
    """Schema version tracking"""
    collection_name: str
    version: str
    migration_date: datetime
    changes: List[str]
    rollback_script: Optional[str] = None

# Example migration for adding new fields
migration_001 = SchemaVersion(
    collection_name="facts",
    version="1.1",
    migration_date=datetime.utcnow(),
    changes=[
        "Added validation_notes field",
        "Added related_facts field",
        "Added confidence_score field"
    ]
)
```

## Data Backup and Recovery

### Backup Strategy
- Daily automated backups of MongoDB collections
- Incremental backups for large collections
- Document file system backups
- Vector database snapshot backups

### Recovery Procedures
- Point-in-time recovery for MongoDB
- Document re-indexing from backup files
- Vector database reconstruction from embeddings

## Performance Considerations

### Query Optimization
- Compound indexes for common query patterns
- Aggregation pipelines for complex queries
- Connection pooling configuration
- Read preference settings for scaling

### Data Archival
- Archive old reviews after retention period
- Compress historical context packs
- Cleanup orphaned passages and facts
- Regular maintenance of vector database
