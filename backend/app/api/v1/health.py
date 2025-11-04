"""
Health check endpoints.

Provides endpoints to check the health status of the application and its dependencies.
"""

from fastapi import APIRouter

from app.api.schemas.common import HealthCheckResponse
from app.config import settings
from app.dependencies import (
    get_mongodb_client_instance,
    get_qdrant_client_instance,
    get_openai_client_instance,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """
    Check the health status of the application and its dependencies.

    Returns:
        Health check response with status of all services

    Note: The application can run with degraded functionality if some services are unavailable.
    Only critical failures will mark the overall status as unhealthy.
    """
    services = {}
    overall_status = "healthy"

    # Get client instances
    mongodb_client = get_mongodb_client_instance()
    qdrant_client = get_qdrant_client_instance()
    openai_client = get_openai_client_instance()

    # Check MongoDB (optional service)
    if mongodb_client is not None:
        try:
            await mongodb_client.admin.command("ping")
            services["mongodb"] = "connected"
            logger.debug("MongoDB health check: connected")
        except Exception as e:
            logger.warning(f"MongoDB health check failed: {e}")
            services["mongodb"] = "disconnected"
            # Don't mark as unhealthy - MongoDB is optional for basic operations
    else:
        services["mongodb"] = "not_available"
        logger.debug("MongoDB not initialized")

    # Check Qdrant (required for vector search)
    if qdrant_client is not None:
        try:
            # For in-memory Qdrant, just check if client exists
            services["qdrant"] = "connected"
            logger.debug("Qdrant health check: connected")
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            services["qdrant"] = "disconnected"
            overall_status = "unhealthy"
    else:
        services["qdrant"] = "not_available"
        overall_status = "unhealthy"
        logger.error("Qdrant not initialized")

    # Check OpenAI (optional service)
    if openai_client is not None:
        services["openai"] = "configured"
        logger.debug("OpenAI client: configured")
    elif settings.openai_api_key:
        services["openai"] = "configured_but_not_initialized"
        logger.debug("OpenAI API key set but client not initialized")
    else:
        services["openai"] = "not_configured"
        logger.debug("OpenAI not configured")
        # Don't mark as unhealthy - OpenAI might not be required for all operations

    return HealthCheckResponse(
        status=overall_status, version=settings.app_version, services=services
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
