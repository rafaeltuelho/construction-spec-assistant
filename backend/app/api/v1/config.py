"""
Configuration API endpoints.

This module provides REST API endpoints for retrieving application configuration information.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["config"])


class LLMInfoResponse(BaseModel):
    """Response schema for LLM configuration information."""

    provider: str = Field(..., description="LLM provider name (e.g., 'openai', 'together', 'anthropic', 'ollama')")
    model: str = Field(..., description="Model name for the configured LLM provider")


@router.get("/config/llm", response_model=LLMInfoResponse)
async def get_llm_info() -> LLMInfoResponse:
    """
    Get the currently configured LLM provider and model name.

    This endpoint returns information about which LLM provider is being used
    and which specific model is configured for that provider.

    Returns:
        LLMInfoResponse: Contains provider name and model name

    Example:
        ```json
        {
            "provider": "openai",
            "model": "gpt-4o-mini"
        }
        ```
    """
    # Determine the model based on the configured provider
    provider = settings.llm_provider.lower()
    
    if provider == "openai":
        model = settings.openai_model
    elif provider == "together":
        model = settings.together_model
    elif provider == "anthropic":
        model = settings.anthropic_model
    elif provider == "ollama":
        model = settings.ollama_model or "unknown"
    else:
        model = "unknown"
    
    logger.debug(f"LLM info requested: provider={provider}, model={model}")
    
    return LLMInfoResponse(provider=provider, model=model)

