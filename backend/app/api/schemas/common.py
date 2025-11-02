"""
Common schemas used across the API.

These schemas define request/response structures shared by multiple endpoints.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class HealthCheckResponse(BaseModel):
    """Health check response schema."""
    
    status: str = Field(..., description="Service status (healthy, unhealthy)")
    version: str = Field(..., description="Application version")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Current timestamp")
    services: Dict[str, str] = Field(default_factory=dict, description="Status of dependent services")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "0.1.0",
                "timestamp": "2024-01-01T12:00:00Z",
                "services": {
                    "mongodb": "connected",
                    "qdrant": "connected",
                    "openai": "available"
                }
            }
        }


class ErrorResponse(BaseModel):
    """Error response schema."""
    
    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "DOCUMENT_NOT_FOUND",
                "message": "Document not found: doc_123",
                "details": {"document_id": "doc_123"},
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }


class SuccessResponse(BaseModel):
    """Generic success response schema."""
    
    success: bool = Field(True, description="Operation success status")
    message: str = Field(..., description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {"id": "123", "status": "completed"}
            }
        }


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""
    
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")
    
    @property
    def skip(self) -> int:
        """Calculate number of items to skip."""
        return (self.page - 1) * self.page_size
    
    @property
    def limit(self) -> int:
        """Get limit value."""
        return self.page_size


class PaginatedResponse(BaseModel):
    """Paginated response schema."""
    
    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    
    class Config:
        json_schema_extra = {
            "example": {
                "items": [{"id": "1"}, {"id": "2"}],
                "total": 100,
                "page": 1,
                "page_size": 20,
                "total_pages": 5
            }
        }


class JobStatus(BaseModel):
    """Job status schema for async operations."""
    
    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status (pending, processing, completed, failed)")
    progress: Optional[float] = Field(None, ge=0.0, le=1.0, description="Progress (0.0-1.0)")
    message: Optional[str] = Field(None, description="Status message")
    result: Optional[Dict[str, Any]] = Field(None, description="Job result (if completed)")
    error: Optional[str] = Field(None, description="Error message (if failed)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Job creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "job_123",
                "status": "processing",
                "progress": 0.5,
                "message": "Processing document chunks",
                "result": None,
                "error": None,
                "created_at": "2024-01-01T12:00:00Z",
                "updated_at": "2024-01-01T12:05:00Z"
            }
        }

