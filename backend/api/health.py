"""Health check endpoints for the Construction Spec Assistant API."""

import time
from datetime import datetime
from fastapi import APIRouter, Depends
from typing import Dict, Any

from ..models.api_models import HealthCheckResponse, BaseResponse
from ..config import settings

router = APIRouter()


def get_app_state() -> Dict[str, Any]:
    """Get application state from main module."""
    from ..main import app_state
    return app_state


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(app_state: Dict[str, Any] = Depends(get_app_state)):
    """Health check endpoint."""
    services_status = {}
    
    try:
        # Check services
        if "services" in app_state:
            services_status["services"] = "healthy"
        else:
            services_status["services"] = "unhealthy"
        
        # Check vector store
        try:
            if "services" in app_state:
                services = app_state["services"]
                collections = services.vectorstore_manager.list_collections()
                services_status["vectorstore"] = "healthy"
            else:
                services_status["vectorstore"] = "unhealthy"
        except Exception:
            services_status["vectorstore"] = "unhealthy"
        
        # Check LLM providers (basic check)
        try:
            import openai
            services_status["llm_providers"] = "healthy"
        except Exception:
            services_status["llm_providers"] = "unhealthy"
        
    except Exception as e:
        services_status["error"] = str(e)
    
    overall_status = "healthy" if all(
        status == "healthy" for status in services_status.values() 
        if status != "error"
    ) else "unhealthy"
    
    uptime = time.time() - app_state.get("start_time", time.time())
    
    return HealthCheckResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version=settings.api_version,
        services=services_status,
        uptime_seconds=uptime
    )


@router.get("/status", response_model=BaseResponse)
async def get_status():
    """Get application status."""
    return BaseResponse(
        success=True,
        message="Application is running",
        timestamp=datetime.utcnow()
    )
