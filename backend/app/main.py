"""
FastAPI application entry point for Construction Spec Assistant.

This module initializes the FastAPI application with all routes, middleware,
and event handlers.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import settings
from app.dependencies import startup_dependencies, shutdown_dependencies
from app.utils.logging import setup_logging, get_logger
from app.utils.exceptions import ConstructionSpecAssistantError
from app.api.v1 import health

# Setup logging
setup_logging(level=settings.log_level, log_format=settings.log_format)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    
    try:
        await startup_dependencies()
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    try:
        await shutdown_dependencies()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered assistant for reviewing construction specifications and submittals",
    docs_url=f"{settings.api_v1_prefix}/docs",
    redoc_url=f"{settings.api_v1_prefix}/redoc",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    lifespan=lifespan
)


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers

@app.exception_handler(ConstructionSpecAssistantError)
async def construction_spec_assistant_exception_handler(
    request: Request,
    exc: ConstructionSpecAssistantError
) -> JSONResponse:
    """
    Handle custom application exceptions.
    
    Args:
        request: FastAPI request
        exc: Custom exception
    
    Returns:
        JSON error response
    """
    logger.error(
        f"Application error: {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors.
    
    Args:
        request: FastAPI request
        exc: Validation error
    
    Returns:
        JSON error response
    """
    logger.warning(
        f"Validation error: {exc}",
        extra={
            "path": request.url.path,
            "errors": exc.errors()
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": {"errors": exc.errors()}
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handle unexpected exceptions.
    
    Args:
        request: FastAPI request
        exc: Exception
    
    Returns:
        JSON error response
    """
    logger.error(
        f"Unexpected error: {exc}",
        extra={
            "path": request.url.path,
            "exception_type": type(exc).__name__
        },
        exc_info=True
    )
    
    # Don't expose internal error details in production
    if settings.is_production:
        message = "An internal error occurred"
    else:
        message = str(exc)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": message,
            "details": {}
        }
    )


# Include routers
app.include_router(
    health.router,
    prefix=settings.api_v1_prefix
)

# TODO: Add more routers as they are implemented
# app.include_router(
#     documents.router,
#     prefix=f"{settings.api_v1_prefix}/documents"
# )
# app.include_router(
#     facts.router,
#     prefix=f"{settings.api_v1_prefix}/facts"
# )
# app.include_router(
#     comparison.router,
#     prefix=f"{settings.api_v1_prefix}/comparison"
# )


@app.get("/")
async def root() -> dict:
    """
    Root endpoint.
    
    Returns:
        Welcome message with API information
    """
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": f"{settings.api_v1_prefix}/docs",
        "health": f"{settings.api_v1_prefix}/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_level=settings.log_level.lower()
    )

