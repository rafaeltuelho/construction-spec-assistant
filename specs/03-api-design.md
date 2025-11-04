# API Design Specification

## Purpose

This document specifies the FastAPI REST API endpoints, request/response schemas, error handling, and OpenAPI documentation for the Construction Spec Assistant backend.

## API Versioning

All endpoints are versioned under `/api/v1/` to allow for future API evolution without breaking existing clients.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

**Phase 1**: No authentication (development)
**Phase 2**: API key authentication via `X-API-Key` header (future)

---

## Endpoints

### 1. Health Check

#### `GET /health`

Check if the API is running and healthy.

**Response**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-10-22T18:30:00Z"
}
```

**Status Codes**:
- `200 OK`: Service is healthy

---

### 2. Document Processing

#### `POST /api/v1/documents/upload`

Upload and process a construction document (PDF).

**Request**:
- **Content-Type**: `multipart/form-data`
- **Body**:
  - `file`: PDF file (required)
  - `document_type`: `"specification" | "submittal" | "product_description" | "drawing"` (required)
  - `use_ocr`: `boolean` (optional, default: `true`)
  - `project_id`: `string` (optional)

**Response**:
```json
{
  "document_id": "doc_abc123",
  "filename": "elevator_spec.pdf",
  "document_type": "specification",
  "status": "processing",
  "created_at": "2025-10-22T18:30:00Z",
  "processing_job_id": "job_xyz789"
}
```

**Status Codes**:
- `202 Accepted`: Document uploaded and processing started
- `400 Bad Request`: Invalid file or parameters
- `413 Payload Too Large`: File size exceeds limit
- `500 Internal Server Error`: Processing failed

---

#### `GET /api/v1/documents/{document_id}`

Get document processing status and metadata.

**Path Parameters**:
- `document_id`: Document identifier

**Response**:
```json
{
  "document_id": "doc_abc123",
  "filename": "elevator_spec.pdf",
  "document_type": "specification",
  "status": "completed",
  "created_at": "2025-10-22T18:30:00Z",
  "completed_at": "2025-10-22T18:31:30Z",
  "metadata": {
    "page_count": 45,
    "section_count": 120,
    "chunk_count": 450,
    "token_count": 125000
  }
}
```

**Status Values**:
- `"processing"`: Document is being processed
- `"completed"`: Processing completed successfully
- `"failed"`: Processing failed
- `"pending"`: Queued for processing

**Status Codes**:
- `200 OK`: Document found
- `404 Not Found`: Document not found

---

#### `GET /api/v1/documents/{document_id}/sections`

Get document sections (hierarchical structure).

**Path Parameters**:
- `document_id`: Document identifier

**Query Parameters**:
- `level`: Filter by section level (optional)
- `limit`: Max sections to return (optional, default: 100)
- `offset`: Pagination offset (optional, default: 0)

**Response**:
```json
{
  "document_id": "doc_abc123",
  "sections": [
    {
      "section_id": "sec_001",
      "level": 1,
      "title": "PART 1 - GENERAL",
      "content": "...",
      "children": [
        {
          "section_id": "sec_002",
          "level": 2,
          "title": "1.1 SUMMARY",
          "content": "...",
          "children": []
        }
      ]
    }
  ],
  "total": 120,
  "limit": 100,
  "offset": 0
}
```

**Status Codes**:
- `200 OK`: Sections retrieved
- `404 Not Found`: Document not found

---

#### `GET /api/v1/documents/{document_id}/chunks`

Get document chunks for RAG retrieval.

**Path Parameters**:
- `document_id`: Document identifier

**Query Parameters**:
- `limit`: Max chunks to return (optional, default: 100)
- `offset`: Pagination offset (optional, default: 0)

**Response**:
```json
{
  "document_id": "doc_abc123",
  "chunks": [
    {
      "chunk_id": "chunk_001",
      "section_path": "PART 1 - GENERAL > 1.1 SUMMARY",
      "content": "...",
      "chunk_index": 0,
      "token_count": 450
    }
  ],
  "total": 450,
  "limit": 100,
  "offset": 0
}
```

**Status Codes**:
- `200 OK`: Chunks retrieved
- `404 Not Found`: Document not found

---

### 3. Fact Extraction

#### `POST /api/v1/facts/extract`

Extract facts from a processed document.

**Request**:
```json
{
  "document_id": "doc_abc123",
  "llm_model": "gpt-4o-mini",
  "deduplicate": true
}
```

**Response**:
```json
{
  "document_id": "doc_abc123",
  "extraction_job_id": "job_fact_123",
  "status": "processing",
  "started_at": "2025-10-22T18:35:00Z"
}
```

**Status Codes**:
- `202 Accepted`: Fact extraction started
- `400 Bad Request`: Invalid request
- `404 Not Found`: Document not found
- `500 Internal Server Error`: Extraction failed

---

#### `GET /api/v1/facts/extraction/{job_id}`

Get fact extraction job status.

**Path Parameters**:
- `job_id`: Extraction job identifier

**Response**:
```json
{
  "job_id": "job_fact_123",
  "document_id": "doc_abc123",
  "status": "completed",
  "started_at": "2025-10-22T18:35:00Z",
  "completed_at": "2025-10-22T18:36:30Z",
  "facts_extracted": 245,
  "facts_deduplicated": 198
}
```

**Status Codes**:
- `200 OK`: Job status retrieved
- `404 Not Found`: Job not found

---

#### `GET /api/v1/facts`

Query extracted facts.

**Query Parameters**:
- `document_id`: Filter by document (optional)
- `entity`: Filter by entity (optional)
- `attribute`: Filter by attribute (optional)
- `limit`: Max facts to return (optional, default: 100)
- `offset`: Pagination offset (optional, default: 0)

**Response**:
```json
{
  "facts": [
    {
      "fact_id": "fact_001",
      "entity": {
        "raw": "Elevator",
        "normalized": "elevator",
        "type": "equipment"
      },
      "attribute": {
        "raw": "capacity",
        "normalized": "capacity",
        "category": "performance"
      },
      "value": {
        "raw": "2500 lbs",
        "normalized": "1133.98 kg",
        "unit": "kg",
        "numeric": 1133.98
      },
      "context": {
        "source_document": "doc_abc123",
        "section_path": "PART 2 - PRODUCTS > 2.1 ELEVATOR SYSTEM",
        "chunk_id": "chunk_045",
        "page_number": 12
      },
      "confidence": 0.95,
      "extracted_at": "2025-10-22T18:36:00Z"
    }
  ],
  "total": 198,
  "limit": 100,
  "offset": 0
}
```

**Status Codes**:
- `200 OK`: Facts retrieved
- `400 Bad Request`: Invalid query parameters

---

### 4. Comparison Agent

#### `POST /api/v1/comparison/compare`

Compare a specification fact against a submittal document.

**Request**:
```json
{
  "spec_fact": {
    "entity": "Elevator",
    "attribute": "capacity",
    "value": "2500 lbs",
    "operator": ">="
  },
  "submittal_document_id": "doc_submittal_456",
  "retrieval_strategy": "ensemble",
  "top_k": 5
}
```

**Response**:
```json
{
  "comparison_id": "comp_789",
  "spec_fact": {
    "entity": "Elevator",
    "attribute": "capacity",
    "value": "2500 lbs",
    "operator": ">="
  },
  "verdict": "consistent",
  "confidence": 0.92,
  "submittal_evidence": "The submittal states: 'Elevator capacity: 3000 lbs'",
  "retrieved_chunks": [
    {
      "chunk_id": "chunk_submittal_023",
      "content": "...",
      "relevance_score": 0.89
    }
  ],
  "reasoning": "The submittal capacity (3000 lbs) exceeds the specification requirement (>= 2500 lbs).",
  "compared_at": "2025-10-22T18:40:00Z"
}
```

**Verdict Values**:
- `"consistent"`: Submittal meets specification
- `"inconsistent"`: Submittal does not meet specification
- `"unclear"`: Cannot determine from available information

**Status Codes**:
- `200 OK`: Comparison completed
- `400 Bad Request`: Invalid request
- `404 Not Found`: Submittal document not found
- `500 Internal Server Error`: Comparison failed

---

#### `POST /api/v1/comparison/compare-document`

Compare all extracted facts from a specification document against a submittal document.

**Note**: This is an asynchronous operation that returns immediately with a job ID. Use the GET endpoint to check status and retrieve results.

**Request**:
```json
{
  "spec_document_id": "doc_spec_123",
  "submittal_document_id": "doc_submittal_456",
  "retrieval_strategy": "ensemble",
  "top_k": 5
}
```

**Response** (202 Accepted - Immediate):
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "pending",
  "spec_document_id": "doc_spec_123",
  "submittal_document_id": "doc_submittal_456",
  "total_facts": 67,
  "message": "Document comparison job initiated with 67 facts to compare"
}
```

**Status Codes**:
- `202 Accepted`: Comparison job initiated
- `400 Bad Request`: Invalid request
- `404 Not Found`: Specification document not found or no facts extracted
- `500 Internal Server Error`: Failed to initiate comparison

---

#### `GET /api/v1/comparison/compare-document/{job_id}`

Get document comparison job status and results.

**Path Parameters**:
- `job_id`: Job identifier returned from POST endpoint

**Query Parameters** (optional):
- `limit`: Maximum number of comparisons to return (default: 100)
- `offset`: Pagination offset (default: 0)
- `verdict_filter`: Filter by verdict (`consistent`, `inconsistent`, `unclear`)

**Response** (Processing):
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "spec_document_id": "doc_spec_123",
  "submittal_document_id": "doc_submittal_456",
  "total_facts": 67,
  "completed_facts": 35,
  "status": "processing",
  "comparisons": [],
  "created_at": "2025-10-22T18:40:00Z"
}
```

**Response** (Completed):
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "spec_document_id": "doc_spec_123",
  "submittal_document_id": "doc_submittal_456",
  "total_facts": 67,
  "completed_facts": 67,
  "status": "completed",
  "summary": {
    "consistent": 45,
    "inconsistent": 12,
    "unclear": 10
  },
  "comparisons": [
    {
      "comparison_id": "comp_789",
      "spec_fact": {
        "entity": "Elevator",
        "attribute": "capacity",
        "value": "2500 lbs",
        "operator": ">="
      },
      "verdict": "consistent",
      "confidence": 0.92,
      "submittal_evidence": "The submittal states: 'Elevator capacity: 3000 lbs'",
      "retrieved_chunks": [
        {
          "chunk_id": "chunk_submittal_023",
          "content": "...",
          "relevance_score": 0.89
        }
      ],
      "reasoning": "The submittal capacity (3000 lbs) exceeds the specification requirement (>= 2500 lbs).",
      "compared_at": "2025-10-22T18:40:00Z"
    },
    {
      "comparison_id": "comp_790",
      "spec_fact": {
        "entity": "Elevator",
        "attribute": "speed",
        "value": "200 fpm",
        "operator": "="
      },
      "verdict": "inconsistent",
      "confidence": 0.88,
      "submittal_evidence": "The submittal states: 'Elevator speed: 150 fpm'",
      "retrieved_chunks": [
        {
          "chunk_id": "chunk_submittal_024",
          "content": "...",
          "relevance_score": 0.91
        }
      ],
      "reasoning": "The submittal speed (150 fpm) does not match the specification requirement (= 200 fpm).",
      "compared_at": "2025-10-22T18:40:01Z"
    }
  ],
  "created_at": "2025-10-22T18:40:00Z",
  "completed_at": "2025-10-22T18:42:30Z"
}
```

**Status Values**:
- `pending`: Job is queued but not started
- `processing`: Job is currently running
- `completed`: Job finished successfully
- `failed`: Job failed with an error

**Persistence**:
- Results are stored in MongoDB (`document_comparison_results` collection)
- Results persist across server restarts
- Can be retrieved by job_id even after server restart

**Status Codes**:
- `200 OK`: Job status retrieved
- `404 Not Found`: Job not found
- `500 Internal Server Error`: Failed to retrieve status

---

#### `POST /api/v1/comparison/batch`

Compare multiple specification facts against a submittal document.

**Request**:
```json
{
  "spec_facts": [
    {
      "entity": "Elevator",
      "attribute": "capacity",
      "value": "2500 lbs",
      "operator": ">="
    },
    {
      "entity": "Elevator",
      "attribute": "speed",
      "value": "200 fpm",
      "operator": "="
    }
  ],
  "submittal_document_id": "doc_submittal_456",
  "retrieval_strategy": "ensemble",
  "top_k": 5
}
```

**Response**:
```json
{
  "batch_id": "batch_999",
  "status": "processing",
  "total_comparisons": 2,
  "started_at": "2025-10-22T18:45:00Z"
}
```

**Status Codes**:
- `202 Accepted`: Batch comparison started
- `400 Bad Request`: Invalid request
- `404 Not Found`: Submittal document not found

---

#### `GET /api/v1/comparison/batch/{batch_id}`

Get batch comparison results.

**Path Parameters**:
- `batch_id`: Batch identifier

**Response**:
```json
{
  "batch_id": "batch_999",
  "status": "completed",
  "total_comparisons": 2,
  "completed_comparisons": 2,
  "started_at": "2025-10-22T18:45:00Z",
  "completed_at": "2025-10-22T18:46:30Z",
  "results": [
    {
      "comparison_id": "comp_789",
      "verdict": "consistent",
      "confidence": 0.92
    },
    {
      "comparison_id": "comp_790",
      "verdict": "inconsistent",
      "confidence": 0.88
    }
  ]
}
```

**Status Codes**:
- `200 OK`: Batch results retrieved
- `404 Not Found`: Batch not found

---

## Error Handling

### Error Response Format

All errors follow a consistent format:

```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "Document with ID 'doc_abc123' not found",
    "details": {
      "document_id": "doc_abc123"
    },
    "timestamp": "2025-10-22T18:50:00Z",
    "request_id": "req_xyz123"
  }
}
```

### Error Codes

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | `INVALID_REQUEST` | Invalid request parameters |
| 400 | `INVALID_FILE_TYPE` | Unsupported file type |
| 404 | `DOCUMENT_NOT_FOUND` | Document not found |
| 404 | `JOB_NOT_FOUND` | Job not found |
| 413 | `FILE_TOO_LARGE` | File size exceeds limit |
| 422 | `VALIDATION_ERROR` | Request validation failed |
| 500 | `PROCESSING_ERROR` | Document processing failed |
| 500 | `EXTRACTION_ERROR` | Fact extraction failed |
| 500 | `COMPARISON_ERROR` | Comparison failed |
| 500 | `INTERNAL_ERROR` | Unexpected server error |

---

## Request/Response Schemas

All schemas are defined using Pydantic models in `backend/app/api/schemas/`.

### Key Schema Files

- `document.py`: Document upload, processing, sections, chunks
- `fact.py`: Fact extraction, fact queries
- `comparison.py`: Comparison requests and results

---

## OpenAPI Documentation

FastAPI automatically generates OpenAPI documentation at:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

---

## Rate Limiting (Future)

**Phase 2**: Implement rate limiting per API key:
- 100 requests per minute for document upload
- 1000 requests per minute for queries

---

## CORS Configuration

Allow cross-origin requests from frontend:

```python
origins = [
    "http://localhost:3000",  # React dev server
    "http://localhost:5173",  # Vite dev server
]
```

---

## Next Steps

Refer to the following specification documents for implementation details:

1. **04-document-processing-pipeline.md**: Document processing implementation
2. **05-fact-extraction.md**: Fact extraction implementation
3. **06-rag-and-agents.md**: Comparison agent implementation

