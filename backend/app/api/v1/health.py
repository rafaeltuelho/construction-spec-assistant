"""
Health check endpoints.

Provides endpoints to check the health status of the application and its dependencies.
"""

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from qdrant_client import QdrantClient

from app.api.schemas.common import HealthCheckResponse
from app.config import settings
from app.dependencies import get_mongodb_database, get_qdrant_client
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    mongodb: AsyncIOMotorDatabase = Depends(get_mongodb_database),
    qdrant: QdrantClient = Depends(get_qdrant_client)
) -> HealthCheckResponse:
    """
    Check the health status of the application and its dependencies.
    
    Returns:
        Health check response with status of all services
    """
    services = {}
    overall_status = "healthy"
    
    # Check MongoDB
    try:
        await mongodb.command('ping')
        services["mongodb"] = "connected"
    except Exception as e:
        logger.error(f"MongoDB health check failed: {e}")
        services["mongodb"] = "disconnected"
        overall_status = "unhealthy"
    
    # Check Qdrant
    try:
        # For in-memory Qdrant, just check if client exists
        if qdrant:
            services["qdrant"] = "connected"
        else:
            services["qdrant"] = "disconnected"
            overall_status = "unhealthy"
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
        services["qdrant"] = "disconnected"
        overall_status = "unhealthy"
    
    # Check OpenAI (just check if API key is configured)
    if settings.openai_api_key:
        services["openai"] = "configured"
    else:
        services["openai"] = "not_configured"
        # Don't mark as unhealthy since OpenAI might not be required for all operations
    
    return HealthCheckResponse(
        status=overall_status,
        version=settings.app_version,
        services=services
    )


@router.get("/health/ready")
async def readiness_check() -> dict:
    """
    Kubernetes readiness probe endpoint.
    
    Returns:
        Simple ready status
    """
    return {"status": "ready"}


@router.get("/health/live")
async def liveness_check() -> dict:
    """
    Kubernetes liveness probe endpoint.
    
    Returns:
        Simple alive status
    """
    return {"status": "alive"}

