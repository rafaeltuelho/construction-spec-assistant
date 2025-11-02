"""
Custom exception classes for the Construction Spec Assistant backend.

These exceptions provide meaningful error messages and proper HTTP status codes.
"""

from typing import Any, Dict, Optional


class ConstructionSpecAssistantError(Exception):
    """Base exception for all application errors."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize exception.
        
        Args:
            message: Human-readable error message
            status_code: HTTP status code
            error_code: Machine-readable error code
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}


# Document Processing Exceptions

class DocumentProcessingError(ConstructionSpecAssistantError):
    """Base exception for document processing errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="DOCUMENT_PROCESSING_ERROR",
            details=details
        )


class DocumentNotFoundError(ConstructionSpecAssistantError):
    """Exception raised when a document is not found."""
    
    def __init__(self, document_id: str):
        super().__init__(
            message=f"Document not found: {document_id}",
            status_code=404,
            error_code="DOCUMENT_NOT_FOUND",
            details={"document_id": document_id}
        )


class DocumentParsingError(DocumentProcessingError):
    """Exception raised when document parsing fails."""
    
    def __init__(self, message: str, document_id: Optional[str] = None):
        super().__init__(
            message=f"Failed to parse document: {message}",
            details={"document_id": document_id} if document_id else {}
        )


class InvalidDocumentTypeError(ConstructionSpecAssistantError):
    """Exception raised when document type is invalid."""
    
    def __init__(self, document_type: str):
        super().__init__(
            message=f"Invalid document type: {document_type}",
            status_code=400,
            error_code="INVALID_DOCUMENT_TYPE",
            details={"document_type": document_type}
        )


# Fact Extraction Exceptions

class FactExtractionError(ConstructionSpecAssistantError):
    """Base exception for fact extraction errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="FACT_EXTRACTION_ERROR",
            details=details
        )


class FactNotFoundError(ConstructionSpecAssistantError):
    """Exception raised when a fact is not found."""
    
    def __init__(self, fact_id: str):
        super().__init__(
            message=f"Fact not found: {fact_id}",
            status_code=404,
            error_code="FACT_NOT_FOUND",
            details={"fact_id": fact_id}
        )


class UnitNormalizationError(FactExtractionError):
    """Exception raised when unit normalization fails."""
    
    def __init__(self, value: str, unit: str):
        super().__init__(
            message=f"Failed to normalize unit: {value} {unit}",
            details={"value": value, "unit": unit}
        )


# Retrieval and Comparison Exceptions

class RetrievalError(ConstructionSpecAssistantError):
    """Base exception for retrieval errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="RETRIEVAL_ERROR",
            details=details
        )


class ComparisonError(ConstructionSpecAssistantError):
    """Base exception for comparison errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="COMPARISON_ERROR",
            details=details
        )


# Database Exceptions

class DatabaseError(ConstructionSpecAssistantError):
    """Base exception for database errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="DATABASE_ERROR",
            details=details
        )


class NotFoundError(ConstructionSpecAssistantError):
    """Generic exception for resource not found errors."""

    def __init__(self, message: str, resource_type: Optional[str] = None, resource_id: Optional[str] = None):
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id

        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND",
            details=details
        )


class DatabaseConnectionError(DatabaseError):
    """Exception raised when database connection fails."""
    
    def __init__(self, database: str, message: str):
        super().__init__(
            message=f"Failed to connect to {database}: {message}",
            details={"database": database}
        )


# LLM Exceptions

class LLMError(ConstructionSpecAssistantError):
    """Base exception for LLM errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="LLM_ERROR",
            details=details
        )


class LLMRateLimitError(LLMError):
    """Exception raised when LLM rate limit is exceeded."""
    
    def __init__(self, provider: str):
        super().__init__(
            message=f"Rate limit exceeded for {provider}",
            details={"provider": provider}
        )


class LLMResponseParsingError(LLMError):
    """Exception raised when LLM response cannot be parsed."""
    
    def __init__(self, message: str):
        super().__init__(
            message=f"Failed to parse LLM response: {message}"
        )


# Validation Exceptions

class ValidationError(ConstructionSpecAssistantError):
    """Exception raised for validation errors."""
    
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(
            message=message,
            status_code=422,
            error_code="VALIDATION_ERROR",
            details={"field": field} if field else {}
        )


# Configuration Exceptions

class ConfigurationError(ConstructionSpecAssistantError):
    """Exception raised for configuration errors."""
    
    def __init__(self, message: str):
        super().__init__(
            message=f"Configuration error: {message}",
            status_code=500,
            error_code="CONFIGURATION_ERROR"
        )

