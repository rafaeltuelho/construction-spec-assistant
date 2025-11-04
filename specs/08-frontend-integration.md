# Frontend Integration Specification

## Purpose

This document specifies the backend changes required to support the Construction Specification Assistant frontend application. It covers new API endpoints, modifications to existing endpoints, data structures for user annotations, and configuration requirements.

## Overview

The frontend is a React-based web application that enables architects to:
1. Upload construction documents (specifications, submittals, product descriptions)
2. Trigger document processing and fact extraction
3. Initiate document comparison workflows
4. Review comparison results with interactive analysis tools
5. Generate reports with user annotations

## Required Backend Changes

### 1. CORS Configuration

**File**: `backend/app/main.py`

**Changes Required**:
- Update CORS middleware to allow frontend origin
- Support credentials for future authentication

**Configuration**:
```python
from fastapi.middleware.cors import CORSMiddleware

origins = [
    "http://localhost:5173",  # Vite dev server (default)
    "http://localhost:3000",  # Alternative React dev server
    "http://localhost:4173",  # Vite preview server
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Environment Variable** (for production):
- `FRONTEND_URL`: Frontend application URL for CORS

---

### 2. File Upload Enhancements

**Endpoint**: `POST /api/v1/documents/upload`

**Current Status**: ✅ Already implemented

**Required Enhancements**:

#### 2.1 File Size Validation
- Add explicit file size limit (e.g., 50MB)
- Return clear error message when limit exceeded

#### 2.2 File Type Validation
- Validate file extension (.pdf only)
- Validate MIME type (application/pdf)
- Return 400 Bad Request with clear error message for invalid files

#### 2.3 Response Enhancement
- Ensure response includes `processing_job_id` for status polling
- Add estimated processing time (optional)

**Example Enhanced Response**:
```json
{
  "document_id": "doc_abc123",
  "filename": "elevator_spec.pdf",
  "document_type": "specification",
  "status": "processing",
  "created_at": "2025-10-22T18:30:00Z",
  "processing_job_id": "job_xyz789",
  "estimated_duration_seconds": 120
}
```

---

### 3. Document Processing Status Polling

**Endpoint**: `GET /api/v1/documents/{document_id}`

**Current Status**: ✅ Already implemented

**Required Enhancements**:

#### 3.1 Add Progress Information
- Include progress percentage for long-running operations
- Add current processing stage (parsing, sectionizing, chunking, indexing)

**Example Enhanced Response**:
```json
{
  "document_id": "doc_abc123",
  "filename": "elevator_spec.pdf",
  "document_type": "specification",
  "status": "processing",
  "progress": {
    "percentage": 65,
    "current_stage": "chunking",
    "stages": ["parsing", "sectionizing", "chunking", "indexing"]
  },
  "created_at": "2025-10-22T18:30:00Z",
  "metadata": null
}
```

---

### 4. Fact Extraction Status Polling

**Endpoint**: `GET /api/v1/facts/extraction/{job_id}`

**Current Status**: ✅ Already implemented

**Required Enhancements**:

#### 4.1 Add Progress Information
- Include progress percentage
- Add current chunk being processed

**Example Enhanced Response**:
```json
{
  "job_id": "job_fact_123",
  "document_id": "doc_abc123",
  "status": "processing",
  "progress": {
    "percentage": 45,
    "chunks_processed": 203,
    "total_chunks": 450
  },
  "started_at": "2025-10-22T18:35:00Z",
  "facts_extracted": 98
}
```

---

### 5. Comparison Status Polling

**Endpoint**: `GET /api/v1/comparison/compare-document/{job_id}`

**Current Status**: ✅ Already implemented

**Required Enhancements**:

#### 5.1 Pagination Support
- Already specified in API design (limit, offset, verdict_filter)
- Ensure implementation supports these query parameters

#### 5.2 Response Optimization
- For large result sets, consider returning summary first
- Allow fetching full comparison details separately if needed

---

### 6. User Annotations API (NEW)

**Purpose**: Store user feedback on comparison results for report generation

#### 6.1 Data Model

**File**: `backend/app/models/comparison.py`

**New Model**:
```python
class UserAnnotation(BaseModel):
    """User annotation for a comparison result."""
    
    comparison_id: str = Field(..., description="Comparison identifier")
    annotation_type: str = Field(
        ..., 
        description="Annotation type: 'disregard', 'confirmed', 'note'"
    )
    note_text: Optional[str] = Field(
        None, 
        description="Custom note text (required when annotation_type='note')"
    )
    annotated_by: Optional[str] = Field(
        None, 
        description="User identifier (for future authentication)"
    )
    annotated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Annotation timestamp"
    )

class AnnotatedComparisonResult(ComparisonResult):
    """Comparison result with user annotations."""
    
    annotations: List[UserAnnotation] = Field(
        default_factory=list,
        description="User annotations for this comparison"
    )
```

#### 6.2 New Endpoint: Save Annotations

**Endpoint**: `POST /api/v1/comparison/{job_id}/annotations`

**Purpose**: Save user annotations for comparison results

**Request Schema**:
```json
{
  "annotations": [
    {
      "comparison_id": "comp_789",
      "annotation_type": "confirmed",
      "note_text": null
    },
    {
      "comparison_id": "comp_790",
      "annotation_type": "note",
      "note_text": "Need to verify with manufacturer"
    },
    {
      "comparison_id": "comp_791",
      "annotation_type": "disregard",
      "note_text": "Not applicable to this project"
    }
  ]
}
```

**Response**:
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "annotations_saved": 3,
  "message": "Annotations saved successfully"
}
```

**Status Codes**:
- `200 OK`: Annotations saved successfully
- `400 Bad Request`: Invalid annotation data
- `404 Not Found`: Job not found
- `500 Internal Server Error`: Failed to save annotations

**Implementation Notes**:
- Store annotations in MongoDB alongside comparison results
- Update `DocumentComparisonResult` model to include annotations
- Support partial updates (can save annotations multiple times)
- Validate annotation_type enum values

#### 6.3 New Endpoint: Get Annotations

**Endpoint**: `GET /api/v1/comparison/{job_id}/annotations`

**Purpose**: Retrieve all annotations for a comparison job

**Response**:
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "annotations": [
    {
      "comparison_id": "comp_789",
      "annotation_type": "confirmed",
      "note_text": null,
      "annotated_at": "2025-10-22T19:00:00Z"
    }
  ],
  "total_annotations": 1
}
```

---

### 7. Report Generation API (NEW - Placeholder)

**Purpose**: Generate PDF/Word report with comparison results and user annotations

#### 7.1 New Endpoint: Generate Report

**Endpoint**: `POST /api/v1/comparison/{job_id}/report`

**Purpose**: Trigger report generation (async operation)

**Request Schema**:
```json
{
  "format": "pdf",
  "include_sections": {
    "summary": true,
    "consistent_items": false,
    "inconsistent_items": true,
    "unclear_items": true,
    "annotations": true
  },
  "report_title": "Elevator Specification Compliance Report",
  "project_name": "Downtown Office Building"
}
```

**Response** (202 Accepted):
```json
{
  "report_job_id": "report_xyz123",
  "status": "pending",
  "message": "Report generation initiated"
}
```

**Status Codes**:
- `202 Accepted`: Report generation initiated
- `400 Bad Request`: Invalid request
- `404 Not Found`: Comparison job not found
- `500 Internal Server Error`: Failed to initiate report generation

#### 7.2 New Endpoint: Get Report Status

**Endpoint**: `GET /api/v1/comparison/{job_id}/report/{report_job_id}`

**Purpose**: Check report generation status and download link

**Response** (Processing):
```json
{
  "report_job_id": "report_xyz123",
  "status": "processing",
  "progress": 45,
  "started_at": "2025-10-22T19:05:00Z"
}
```

**Response** (Completed):
```json
{
  "report_job_id": "report_xyz123",
  "status": "completed",
  "download_url": "/api/v1/comparison/reports/report_xyz123/download",
  "filename": "elevator_compliance_report.pdf",
  "file_size_bytes": 2458624,
  "started_at": "2025-10-22T19:05:00Z",
  "completed_at": "2025-10-22T19:06:30Z"
}
```

#### 7.3 New Endpoint: Download Report

**Endpoint**: `GET /api/v1/comparison/reports/{report_job_id}/download`

**Purpose**: Download generated report file

**Response**: Binary file stream (PDF or DOCX)

**Headers**:
- `Content-Type`: `application/pdf` or `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- `Content-Disposition`: `attachment; filename="report.pdf"`

**Implementation Notes**:
- This is a **placeholder** for future implementation
- Frontend should show "Coming Soon" or disabled state
- Backend should return 501 Not Implemented initially
- Store generated reports temporarily (e.g., 24 hours)
- Consider using background task queue (Celery, RQ) for generation

---

### 8. Database Schema Changes

**Collection**: `document_comparison_results`

**Changes Required**:

#### 8.1 Add Annotations Field
```python
class DocumentComparisonResult(BaseModel):
    # ... existing fields ...
    annotations: Dict[str, List[UserAnnotation]] = Field(
        default_factory=dict,
        description="User annotations keyed by comparison_id"
    )
```

#### 8.2 Add Report Metadata Field (Optional)
```python
class DocumentComparisonResult(BaseModel):
    # ... existing fields ...
    reports: List[ReportMetadata] = Field(
        default_factory=list,
        description="Generated reports for this comparison"
    )

class ReportMetadata(BaseModel):
    report_job_id: str
    format: str
    filename: str
    file_path: str
    generated_at: datetime
    expires_at: Optional[datetime]
```

---

### 9. Error Handling Enhancements

**File**: `backend/app/utils/exceptions.py`

**New Exception Classes**:
```python
class FileValidationError(Exception):
    """Raised when uploaded file fails validation."""
    pass

class AnnotationError(Exception):
    """Raised when annotation operation fails."""
    pass

class ReportGenerationError(Exception):
    """Raised when report generation fails."""
    pass
```

**File**: `backend/app/main.py`

**New Exception Handlers**:
- Add handlers for new exception types
- Return consistent error response format
- Include helpful error messages for frontend display

---

### 10. Configuration Changes

**File**: `backend/app/config.py`

**New Configuration Variables**:
```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # File upload settings
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_FILE_TYPES: List[str] = [".pdf"]
    
    # Frontend settings
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    # Report generation settings (future)
    REPORT_STORAGE_PATH: str = "./reports"
    REPORT_EXPIRY_HOURS: int = 24
```

---

## Implementation Priority

### Phase 1: Essential (Required for MVP)
1. ✅ CORS configuration
2. ✅ File upload enhancements (validation, error messages)
3. ✅ Status polling enhancements (progress information)
4. ✅ User annotations API (save and retrieve)

### Phase 2: Enhanced Features
5. ⏳ Report generation API (placeholder implementation)
6. ⏳ Advanced filtering and pagination
7. ⏳ Batch annotation operations

### Phase 3: Future Enhancements
8. ⏳ Real-time updates via WebSockets
9. ⏳ Report generation implementation
10. ⏳ User authentication and authorization

---

## Testing Requirements

### API Testing
- Test file upload with various file sizes and types
- Test status polling for all async operations
- Test annotation CRUD operations
- Test error handling for all new endpoints

### Integration Testing
- Test complete workflow from upload to comparison
- Test annotation persistence across server restarts
- Test concurrent operations

### Performance Testing
- Test file upload with maximum allowed size
- Test comparison with large fact sets
- Test annotation operations with many annotations

---

## Security Considerations

### Input Validation
- Validate all file uploads (size, type, content)
- Sanitize user-provided text (annotation notes)
- Validate comparison_id references

### Rate Limiting (Future)
- Limit file uploads per IP/user
- Limit API requests per IP/user
- Prevent abuse of report generation

### Data Privacy
- Ensure uploaded documents are stored securely
- Implement proper access controls (future)
- Consider data retention policies

---

## Monitoring and Logging

### Logging Requirements
- Log all file uploads (filename, size, user)
- Log all comparison job initiations
- Log annotation operations
- Log report generation requests
- Log all errors with context

### Metrics to Track
- File upload success/failure rate
- Average processing time per document
- Comparison job completion rate
- Annotation usage statistics
- API response times

---

## Next Steps

1. Review this specification with the team
2. Prioritize implementation based on frontend needs
3. Implement Phase 1 changes first
4. Test thoroughly with frontend integration
5. Iterate based on feedback

---

**Last Updated**: 2025-11-04  
**Status**: Ready for review  
**Next Step**: Implement Phase 1 backend changes

