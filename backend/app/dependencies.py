"""
FastAPI dependency injection for database clients and services.

This module provides dependency functions that can be injected into API endpoints.
"""

from typing import AsyncGenerator, Optional, Union
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
