"""
FastAPI dependency injection for database clients and services.

This module provides dependency functions that can be injected into API endpoints.
"""

import os
from typing import AsyncGenerator, Optional, Union, Any
from fastapi import Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI
from langchain_together import ChatTogether

from app.config import settings
from app.utils.logging import get_logger
from app.utils.exceptions import DatabaseConnectionError, ConfigurationError

logger = get_logger(__name__)

# Type alias for LLM clients
LLMClient = Union[ChatOpenAI, ChatTogether]

# Global client instances (initialized on startup)
_mongodb_client: Optional[AsyncIOMotorClient] = None
_qdrant_client: Optional[QdrantClient] = None
_llm_client: Optional[LLMClient] = None
_tavily_search_tool: Optional[Any] = None  # Tavily search tool for web search


# Getter functions for health checks


def get_mongodb_client_instance() -> Optional[AsyncIOMotorClient]:
    """Get the MongoDB client instance (for health checks)."""
    return _mongodb_client


def get_qdrant_client_instance() -> Optional[QdrantClient]:
    """Get the Qdrant client instance (for health checks)."""
    return _qdrant_client


def get_llm_client_instance() -> Optional[LLMClient]:
    """Get the LLM client instance (for health checks)."""
    return _llm_client


def get_openai_client_instance() -> Optional[LLMClient]:
    """Get the LLM client instance (for health checks). Alias for backward compatibility."""
    return _llm_client


def get_tavily_search_tool_instance() -> Optional[Any]:
    """Get the Tavily search tool instance (for health checks)."""
    return _tavily_search_tool


# MongoDB Dependencies


async def get_mongodb_client() -> AsyncIOMotorClient:
    """
    Get MongoDB client instance.

    Returns:
        MongoDB client

    Raises:
        DatabaseConnectionError: If MongoDB client is not initialized
    """
    global _mongodb_client

    if _mongodb_client is None:
        raise DatabaseConnectionError(
            database="MongoDB",
            message="MongoDB client not initialized. Call init_mongodb() on startup.",
        )

    return _mongodb_client


async def get_mongodb_database(
    client: AsyncIOMotorClient = Depends(get_mongodb_client),
) -> AsyncIOMotorDatabase:
    """
    Get MongoDB database instance.

    Args:
        client: MongoDB client (injected)

    Returns:
        MongoDB database
    """
    return client[settings.mongodb_database]


# Convenience alias for API endpoints
async def get_mongodb() -> AsyncIOMotorDatabase:
    """
    Convenience function to get MongoDB database directly.

    Returns:
        MongoDB database
    """
    client = await get_mongodb_client()
    return client[settings.mongodb_database]


async def init_mongodb() -> None:
    """
    Initialize MongoDB client.

    Should be called during application startup.
    Note: This is optional - the application will start even if MongoDB is not available.
    """
    global _mongodb_client

    try:
        logger.info(f"Connecting to MongoDB at {settings.mongodb_url}")

        _mongodb_client = AsyncIOMotorClient(
            settings.mongodb_url,
            maxPoolSize=settings.mongodb_max_pool_size,
            serverSelectionTimeoutMS=5000,  # 5 second timeout for faster failure
        )

        # Test connection
        await _mongodb_client.admin.command("ping")

        logger.info("MongoDB connection established")

    except Exception as e:
        logger.warning(f"Failed to connect to MongoDB: {e}")
        logger.warning(
            "Application will continue without MongoDB. Document storage will not be available."
        )
        _mongodb_client = None


async def close_mongodb() -> None:
    """
    Close MongoDB client.

    Should be called during application shutdown.
    """
    global _mongodb_client

    if _mongodb_client is not None:
        logger.info("Closing MongoDB connection")
        _mongodb_client.close()
        _mongodb_client = None


# Qdrant Dependencies


async def get_qdrant_client() -> QdrantClient:
    """
    Get Qdrant client instance.

    Returns:
        Qdrant client

    Raises:
        DatabaseConnectionError: If Qdrant client is not initialized
    """
    global _qdrant_client

    if _qdrant_client is None:
        raise DatabaseConnectionError(
            database="Qdrant",
            message="Qdrant client not initialized. Call init_qdrant() on startup.",
        )

    return _qdrant_client


# Convenience alias for API endpoints
def get_qdrant() -> QdrantClient:
    """
    Convenience function to get Qdrant client directly (synchronous).

    Returns:
        Qdrant client
    """
    global _qdrant_client

    if _qdrant_client is None:
        raise DatabaseConnectionError(
            database="Qdrant",
            message="Qdrant client not initialized. Call init_qdrant() on startup.",
        )

    return _qdrant_client


async def init_qdrant() -> None:
    """
    Initialize Qdrant client.

    Should be called during application startup.
    """
    global _qdrant_client

    try:
        logger.info("Initializing Qdrant client")

        if settings.qdrant_use_memory:
            # Use in-memory Qdrant for development
            logger.info("Using in-memory Qdrant")
            _qdrant_client = QdrantClient(":memory:")
        else:
            # Connect to Qdrant server
            logger.info(f"Connecting to Qdrant at {settings.qdrant_host}:{settings.qdrant_port}")
            _qdrant_client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

        # Ensure collection exists
        from app.db.qdrant import ensure_collection_exists

        await ensure_collection_exists(_qdrant_client, settings.qdrant_collection_name)

        logger.info("Qdrant client initialized")

    except Exception as e:
        logger.error(f"Failed to initialize Qdrant: {e}")
        raise DatabaseConnectionError(database="Qdrant", message=str(e))


async def close_qdrant() -> None:
    """
    Close Qdrant client.

    Should be called during application shutdown.
    """
    global _qdrant_client

    if _qdrant_client is not None:
        logger.info("Closing Qdrant connection")
        _qdrant_client.close()
        _qdrant_client = None


# LLM Dependencies


async def get_llm_client() -> LLMClient:
    """
    Get LLM client instance (OpenAI, Together.ai, etc.).

    Returns:
        LLM client (ChatOpenAI or ChatTogether)

    Raises:
        ConfigurationError: If LLM client is not initialized
    """
    global _llm_client

    if _llm_client is None:
        raise ConfigurationError(
            f"LLM client not initialized. Call init_llm() on startup. "
            f"Current provider: {settings.llm_provider}"
        )

    return _llm_client


async def get_openai_client() -> LLMClient:
    """
    Get LLM client instance. Alias for backward compatibility.

    Returns:
        LLM client

    Raises:
        ConfigurationError: If LLM client is not initialized
    """
    return await get_llm_client()


async def get_tavily_search_tool() -> Optional[Any]:
    """
    Get Tavily search tool instance.

    Returns:
        Tavily search tool or None if not initialized/enabled

    Note:
        This function returns None if Tavily is not configured or disabled.
        Callers should handle None gracefully.
    """
    global _tavily_search_tool
    return _tavily_search_tool


async def init_llm() -> None:
    """
    Initialize LLM client based on configured provider.

    Should be called during application startup.
    Note: This is optional - the application will start even if LLM is not configured.
    """
    global _llm_client

    provider = settings.llm_provider.lower()
    logger.info(f"Initializing LLM client with provider: {provider}")

    try:
        if provider == "openai":
            if not settings.openai_api_key:
                logger.warning("OPENAI_API_KEY not set in environment")
                logger.warning(
                    "Application will continue without OpenAI. LLM features will not be available."
                )
                _llm_client = None
                return

            logger.info(f"Initializing OpenAI client with model {settings.openai_model}")

            _llm_client = ChatOpenAI(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                temperature=settings.openai_temperature,
                max_tokens=settings.openai_max_tokens,
            )

            logger.info("OpenAI client initialized successfully")

        elif provider == "together":
            if not settings.together_api_key:
                logger.warning("TOGETHER_API_KEY not set in environment")
                logger.warning(
                    "Application will continue without Together.ai. LLM features will not be available."
                )
                _llm_client = None
                return

            logger.info(f"Initializing Together.ai client with model {settings.together_model}")

            # NOTE: JSON mode is NOT enabled here because it conflicts with tool calling
            # JSON mode requires "strict" function tools, which TavilySearch doesn't support
            # Instead, we rely on:
            # 1. Strong prompt instructions for JSON output
            # 2. JSON format reminders after tool execution (in comparison_graph.py)
            # 3. json-repair fallback for malformed responses
            # This approach works with both tool calling and non-tool scenarios

            _llm_client = ChatTogether(
                api_key=settings.together_api_key,
                model=settings.together_model,
                temperature=settings.together_temperature,
                max_tokens=settings.together_max_tokens,
            )

            logger.info("Together.ai client initialized successfully")

        else:
            logger.warning(
                f"Unsupported LLM provider: {provider}. Supported providers: openai, together"
            )
            logger.warning(
                "Application will continue without LLM. LLM features will not be available."
            )
            _llm_client = None

    except Exception as e:
        logger.warning(f"Failed to initialize {provider} LLM client: {e}")
        logger.warning("Application will continue without LLM. LLM features will not be available.")
        _llm_client = None


async def init_openai() -> None:
    """
    Initialize OpenAI LLM client. Alias for backward compatibility.

    This function is deprecated. Use init_llm() instead.
    """
    await init_llm()


# Tavily Search Tool Initialization


async def init_tavily() -> None:
    """
    Initialize Tavily search tool for web search enhancement.

    Should be called during application startup.
    Note: This is optional - the application will start even if Tavily is not configured.
    """
    global _tavily_search_tool

    if not settings.tavily_search_enabled:
        logger.info("Tavily web search is disabled")
        _tavily_search_tool = None
        return

    if not settings.tavily_api_key:
        logger.warning("TAVILY_API_KEY not set in environment")
        logger.warning(
            "Application will continue without Tavily. Web search enhancement will not be available."
        )
        _tavily_search_tool = None
        return

    try:
        logger.info("Initializing Tavily search tool")

        # Import Tavily search tool from langchain-tavily package
        from langchain_tavily import TavilySearch

        # Initialize Tavily search tool
        _tavily_search_tool = TavilySearch(
            tavily_api_key=settings.tavily_api_key,
            max_results=settings.tavily_max_results,
            search_depth=settings.tavily_search_depth,
        )

        logger.info(
            f"Tavily search tool initialized successfully "
            f"(max_results={settings.tavily_max_results}, depth={settings.tavily_search_depth})"
        )

    except ImportError:
        logger.warning(
            "langchain-tavily package not installed. Install with: pip install langchain-tavily"
        )
        logger.warning(
            "Application will continue without Tavily. Web search enhancement will not be available."
        )
        _tavily_search_tool = None
    except Exception as e:
        logger.warning(f"Failed to initialize Tavily search tool: {e}")
        logger.warning(
            "Application will continue without Tavily. Web search enhancement will not be available."
        )
        _tavily_search_tool = None


# LangSmith Initialization


async def init_langsmith() -> None:
    """
    Initialize LangSmith tracing.

    Sets environment variables required by LangChain for automatic tracing.
    LangChain will automatically trace all LLM calls and agent workflows when
    these environment variables are set.

    Environment variables set:
    - LANGCHAIN_TRACING_V2: Enable tracing v2
    - LANGCHAIN_API_KEY: LangSmith API key
    - LANGCHAIN_PROJECT: Project name for organizing traces
    - LANGCHAIN_ENDPOINT: LangSmith API endpoint

    Raises:
        No exceptions raised - failures are logged as warnings
    """
    if not settings.langsmith_enabled:
        logger.info("LangSmith tracing is disabled")
        return

    if not settings.langsmith_api_key:
        logger.warning("LangSmith API key not set. Tracing will be disabled.")
        logger.warning(
            "Set LANGSMITH_ENABLED=true and LANGSMITH_API_KEY in environment to enable tracing."
        )
        return

    try:
        # Set environment variables for LangChain tracing
        os.environ["LANGCHAIN_TRACING_V2"] = str(settings.langsmith_tracing_v2).lower()
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint

        logger.info("=" * 60)
        logger.info("LangSmith Tracing Enabled")
        logger.info(f"  Project: {settings.langsmith_project}")
        logger.info(f"  Endpoint: {settings.langsmith_endpoint}")
        logger.info(f"  Tracing V2: {settings.langsmith_tracing_v2}")
        logger.info("=" * 60)

    except Exception as e:
        logger.warning(f"Failed to initialize LangSmith: {e}")
        logger.warning("Application will continue without LangSmith tracing.")


# Startup and Shutdown


async def startup_dependencies() -> None:
    """
    Initialize all dependencies on application startup.

    This function should be called in the FastAPI startup event.
    """
    logger.info("Initializing application dependencies")

    # Initialize database clients
    await init_mongodb()
    await init_qdrant()

    # Initialize LLM client (based on configured provider)
    await init_llm()

    # Initialize Tavily search tool (if enabled)
    await init_tavily()

    # Initialize LangSmith tracing (if enabled)
    await init_langsmith()

    logger.info("All dependencies initialized successfully")


async def shutdown_dependencies() -> None:
    """
    Close all dependencies on application shutdown.

    This function should be called in the FastAPI shutdown event.
    """
    logger.info("Shutting down application dependencies")

    # Close database clients
    await close_mongodb()
    await close_qdrant()

    logger.info("All dependencies shut down successfully")
