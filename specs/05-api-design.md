# API Design Specification

## Overview

This specification defines the FastAPI-based REST API for the Architectural Submittal Reviewer system, including endpoints, request/response models, and OpenAPI documentation.

## FastAPI Application Structure

### Installation and Dependencies

```python
# requirements.txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
pydantic==2.5.0
pydantic-settings==2.1.0
```

### Application Configuration

```python
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from typing import List, Optional, Dict, Any
import uvicorn
from contextlib import asynccontextmanager

class Settings(BaseSettings):
    """Application settings"""
    
    # API Configuration
    api_title: str = "Architectural Submittal Reviewer API"
    api_description: str = "API for reviewing construction documents and identifying discrepancies"
    api_version: str = "1.0.0"
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # CORS Configuration
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    cors_methods: List[str] = ["GET", "POST", "PUT", "DELETE"]
    cors_headers: List[str] = ["*"]
    
    # File Upload Configuration
    max_file_size_mb: int = 100
    allowed_file_types: List[str] = ["application/pdf"]
    upload_directory: str = "./uploads"
    
    # Database Configuration
    mongodb_url: str = "mongodb://localhost:27017/construction_specs"
    
    # Vector Database Configuration
    qdrant_url: str = "http://localhost:6333"
    
    # LLM Configuration
    default_llm_provider: str = "openai"
    default_llm_model: str = "gpt-4-turbo"
    
    class Config:
        env_file = ".env"

settings = Settings()

# Global application state
app_state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print("Starting Architectural Submittal Reviewer API...")
    
    # Initialize services
    from .services import initialize_services
    app_state["services"] = await initialize_services(settings)
    
    yield
    
    # Shutdown
    print("Shutting down Architectural Submittal Reviewer API...")
    if "services" in app_state:
        await app_state["services"].cleanup()

# Create FastAPI application
app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)
```

## Request/Response Models

### Base Models

```python
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
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

# Base response model
class BaseResponse(BaseModel):
    """Base response model"""
    success: bool
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ErrorResponse(BaseResponse):
    """Error response model"""
    error_code: str
    details: Optional[Dict[str, Any]] = None

class PaginatedResponse(BaseModel):
    """Paginated response model"""
    items: List[Any]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool
```

### Document Models

```python
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

class DocumentResponse(BaseModel):
    """Response model for document information"""
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
    """Response model for document list"""
    items: List[DocumentResponse]

class DocumentProcessingStatus(BaseModel):
    """Document processing status"""
    document_id: str
    status: DocumentStatus
    progress_percentage: float = Field(ge=0, le=100)
    current_step: str
    error_message: Optional[str] = None
    estimated_completion_time: Optional[datetime] = None
```

### Review Models

```python
class ReviewRequest(BaseModel):
    """Request model for initiating a review"""
    specification_document_id: str = Field(..., min_length=1)
    submittal_document_id: str = Field(..., min_length=1)
    review_scope: Optional[List[str]] = Field(default_factory=list, description="CSI division codes")
    llm_provider: Optional[str] = Field(default="openai")
    llm_model: Optional[str] = Field(default="gpt-4-turbo")
    enable_verification: bool = Field(default=True)

class Citation(BaseModel):
    """Citation model for findings"""
    source: str = Field(..., description="specification or submittal")
    page: int
    section: Optional[str] = None
    text: str

class Finding(BaseModel):
    """Finding model"""
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
    """Response model for review results"""
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
    """Request model for validating findings"""
    finding_id: str
    validation_decision: str = Field(..., regex="^(accept|reject|modify)$")
    validation_notes: Optional[str] = None
    reviewer_id: Optional[str] = None

class ReviewListResponse(PaginatedResponse):
    """Response model for review list"""
    items: List[ReviewResponse]
```

### Search Models

```python
class SearchRequest(BaseModel):
    """Request model for document search"""
    query: str = Field(..., min_length=1, max_length=1000)
    document_types: Optional[List[DocumentType]] = None
    csi_divisions: Optional[List[str]] = None
    limit: int = Field(default=10, ge=1, le=100)
    exact_terms: Optional[List[str]] = None

class PassageSearchResult(BaseModel):
    """Search result for passages"""
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
    """Response model for search results"""
    query: str
    total_results: int
    passages: List[PassageSearchResult]
    processing_time_seconds: float
```

### Health Check Models

```python
class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    version: str
    services: Dict[str, str]  # Service name -> status
    uptime_seconds: float
```

## API Endpoints

### Health and Status Endpoints

```python
@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint"""
    import time
    
    services_status = {}
    if "services" in app_state:
        services = app_state["services"]
        
        # Check MongoDB
        try:
            await services.database.ping()
            services_status["mongodb"] = "healthy"
        except Exception:
            services_status["mongodb"] = "unhealthy"
        
        # Check Qdrant
        try:
            await services.vector_db.health_check()
            services_status["qdrant"] = "healthy"
        except Exception:
            services_status["qdrant"] = "unhealthy"
        
        # Check LLM providers
        try:
            await services.llm_manager.check_providers()
            services_status["llm_providers"] = "healthy"
        except Exception:
            services_status["llm_providers"] = "unhealthy"
    
    return HealthCheckResponse(
        status="healthy" if all(status == "healthy" for status in services_status.values()) else "unhealthy",
        timestamp=datetime.utcnow(),
        version=settings.api_version,
        services=services_status,
        uptime_seconds=time.time() - app_state.get("start_time", time.time())
    )

@app.get("/status")
async def get_status():
    """Get application status"""
    return {
        "status": "running",
        "version": settings.api_version,
        "environment": "development" if settings.debug else "production"
    }
```

### Document Management Endpoints

```python
@app.post("/documents/upload", response_model=BaseResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(...),
    metadata: Optional[str] = Form(None)
):
    """Upload and process a document"""
    try:
        # Validate file
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        if file.size > settings.max_file_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=400, 
                detail=f"File size exceeds maximum allowed size of {settings.max_file_size_mb}MB"
            )
        
        # Parse metadata
        parsed_metadata = {}
        if metadata:
            import json
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid metadata JSON")
        
        # Upload and process document
        services = app_state["services"]
        document_id = await services.document_manager.upload_document(
            file=file,
            document_type=document_type,
            metadata=parsed_metadata
        )
        
        # Start background processing
        background_tasks.add_task(
            services.document_manager.process_document,
            document_id
        )
        
        return BaseResponse(
            success=True,
            message=f"Document uploaded successfully. Document ID: {document_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    document_type: Optional[DocumentType] = Query(None),
    status: Optional[DocumentStatus] = Query(None)
):
    """List documents with pagination and filtering"""
    try:
        services = app_state["services"]
        
        # Build filters
        filters = {}
        if document_type:
            filters["document_type"] = document_type
        if status:
            filters["status"] = status
        
        # Get documents
        documents, total = await services.document_manager.list_documents(
            page=page,
            page_size=page_size,
            filters=filters
        )
        
        return DocumentListResponse(
            items=documents,
            total=total,
            page=page,
            page_size=page_size,
            has_next=(page * page_size) < total,
            has_previous=page > 1
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")

@app.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """Get document details"""
    try:
        services = app_state["services"]
        document = await services.document_manager.get_document(document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return document
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")

@app.get("/documents/{document_id}/status", response_model=DocumentProcessingStatus)
async def get_document_status(document_id: str):
    """Get document processing status"""
    try:
        services = app_state["services"]
        status = await services.document_manager.get_processing_status(document_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get document status: {str(e)}")

@app.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and all associated data"""
    try:
        services = app_state["services"]
        success = await services.document_manager.delete_document(document_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return BaseResponse(
            success=True,
            message=f"Document {document_id} deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")
```

### Review Endpoints

```python
@app.post("/reviews", response_model=BaseResponse)
async def create_review(
    background_tasks: BackgroundTasks,
    review_request: ReviewRequest
):
    """Create a new document review"""
    try:
        services = app_state["services"]
        
        # Validate documents exist
        spec_doc = await services.document_manager.get_document(review_request.specification_document_id)
        submittal_doc = await services.document_manager.get_document(review_request.submittal_document_id)
        
        if not spec_doc:
            raise HTTPException(status_code=404, detail="Specification document not found")
        
        if not submittal_doc:
            raise HTTPException(status_code=404, detail="Submittal document not found")
        
        # Check document status
        if spec_doc.status != DocumentStatus.INDEXED:
            raise HTTPException(
                status_code=400, 
                detail="Specification document not fully processed"
            )
        
        if submittal_doc.status != DocumentStatus.INDEXED:
            raise HTTPException(
                status_code=400, 
                detail="Submittal document not fully processed"
            )
        
        # Create review
        review_id = await services.review_manager.create_review(review_request)
        
        # Start background review process
        background_tasks.add_task(
            services.review_manager.process_review,
            review_id
        )
        
        return BaseResponse(
            success=True,
            message=f"Review created successfully. Review ID: {review_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create review: {str(e)}")

@app.get("/reviews", response_model=ReviewListResponse)
async def list_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[ReviewStatus] = Query(None),
    specification_document_id: Optional[str] = Query(None),
    submittal_document_id: Optional[str] = Query(None)
):
    """List reviews with pagination and filtering"""
    try:
        services = app_state["services"]
        
        # Build filters
        filters = {}
        if status:
            filters["status"] = status
        if specification_document_id:
            filters["specification_document_id"] = specification_document_id
        if submittal_document_id:
            filters["submittal_document_id"] = submittal_document_id
        
        # Get reviews
        reviews, total = await services.review_manager.list_reviews(
            page=page,
            page_size=page_size,
            filters=filters
        )
        
        return ReviewListResponse(
            items=reviews,
            total=total,
            page=page,
            page_size=page_size,
            has_next=(page * page_size) < total,
            has_previous=page > 1
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list reviews: {str(e)}")

@app.get("/reviews/{review_id}", response_model=ReviewResponse)
async def get_review(review_id: str):
    """Get review details"""
    try:
        services = app_state["services"]
        review = await services.review_manager.get_review(review_id)
        
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        
        return review
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get review: {str(e)}")

@app.put("/reviews/{review_id}/findings/{finding_id}/validate")
async def validate_finding(
    review_id: str,
    finding_id: str,
    validation_request: FindingValidationRequest
):
    """Validate a finding from a review"""
    try:
        services = app_state["services"]
        success = await services.review_manager.validate_finding(
            review_id=review_id,
            finding_id=finding_id,
            validation_request=validation_request
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Review or finding not found")
        
        return BaseResponse(
            success=True,
            message=f"Finding {finding_id} validated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate finding: {str(e)}")

@app.delete("/reviews/{review_id}")
async def delete_review(review_id: str):
    """Delete a review"""
    try:
        services = app_state["services"]
        success = await services.review_manager.delete_review(review_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Review not found")
        
        return BaseResponse(
            success=True,
            message=f"Review {review_id} deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete review: {str(e)}")
```

### Search Endpoints

```python
@app.post("/search", response_model=SearchResponse)
async def search_documents(search_request: SearchRequest):
    """Search documents using hybrid retrieval"""
    try:
        import time
        start_time = time.time()
        
        services = app_state["services"]
        
        # Perform search
        results = await services.search_engine.search(
            query=search_request.query,
            document_types=search_request.document_types,
            csi_divisions=search_request.csi_divisions,
            limit=search_request.limit,
            exact_terms=search_request.exact_terms
        )
        
        processing_time = time.time() - start_time
        
        return SearchResponse(
            query=search_request.query,
            total_results=len(results),
            passages=results,
            processing_time_seconds=processing_time
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/search/suggestions")
async def get_search_suggestions(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50)
):
    """Get search suggestions based on query"""
    try:
        services = app_state["services"]
        suggestions = await services.search_engine.get_suggestions(
            query=query,
            limit=limit
        )
        
        return {
            "query": query,
            "suggestions": suggestions
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get suggestions: {str(e)}")
```

### Analytics Endpoints

```python
@app.get("/analytics/overview")
async def get_analytics_overview():
    """Get system analytics overview"""
    try:
        services = app_state["services"]
        analytics = await services.analytics_manager.get_overview()
        
        return analytics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")

@app.get("/analytics/reviews")
async def get_review_analytics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None)
):
    """Get review analytics for date range"""
    try:
        services = app_state["services"]
        analytics = await services.analytics_manager.get_review_analytics(
            start_date=start_date,
            end_date=end_date
        )
        
        return analytics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get review analytics: {str(e)}")

@app.get("/analytics/findings")
async def get_finding_analytics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    finding_type: Optional[FindingType] = Query(None)
):
    """Get finding analytics for date range"""
    try:
        services = app_state["services"]
        analytics = await services.analytics_manager.get_finding_analytics(
            start_date=start_date,
            end_date=end_date,
            finding_type=finding_type
        )
        
        return analytics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get finding analytics: {str(e)}")
```

## Error Handling and Middleware

### Global Exception Handler

```python
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            success=False,
            message=exc.detail,
            error_code=f"HTTP_{exc.status_code}",
            details={"path": str(request.url)}
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            success=False,
            message="Internal server error",
            error_code="INTERNAL_ERROR",
            details={"path": str(request.url)} if settings.debug else None
        ).dict()
    )
```

### Request Logging Middleware

```python
import time
from fastapi import Request

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests"""
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url}")
    
    # Process request
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.info(f"Response: {response.status_code} - {process_time:.3f}s")
    
    return response
```

## API Documentation

### OpenAPI Configuration

```python
# The FastAPI app automatically generates OpenAPI documentation
# Access it at: http://localhost:8000/docs

# Custom OpenAPI schema modifications
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=settings.api_title,
        version=settings.api_version,
        description=settings.api_description,
        routes=app.routes,
    )
    
    # Add custom tags
    openapi_schema["tags"] = [
        {
            "name": "health",
            "description": "Health check and status endpoints"
        },
        {
            "name": "documents",
            "description": "Document management endpoints"
        },
        {
            "name": "reviews",
            "description": "Document review endpoints"
        },
        {
            "name": "search",
            "description": "Document search endpoints"
        },
        {
            "name": "analytics",
            "description": "Analytics and reporting endpoints"
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

## Development Server

### Uvicorn Configuration

```python
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug"
    )
```

This API design specification provides a comprehensive REST API for the Architectural Submittal Reviewer system with proper error handling, validation, and documentation.
