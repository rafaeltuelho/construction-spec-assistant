"""Services for document processing and business logic."""

import logging
from typing import Any
from ..config import Settings
from .document_parser import DocumentParser
from .fact_extractor import FactExtractor
from .vectorstore import VectorStoreManager
from .metadata_tagger import MetadataTagger

logger = logging.getLogger(__name__)


class ServiceManager:
    """Manager for all backend services."""
    
    def __init__(self, settings: Settings):
        """Initialize all services."""
        self.settings = settings
        self.document_parser = DocumentParser()
        self.fact_extractor = FactExtractor(
            model=settings.default_llm_model,
            temperature=0.0
        )
        self.vectorstore_manager = VectorStoreManager(
            embedding_model=settings.embedding_model,
            embedding_dim=settings.embedding_dimensions,
            catalog_path=settings.catalog_path
        )
        self.metadata_tagger = MetadataTagger(settings.catalog_path)
    
    async def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up services...")
        # Add any cleanup logic here if needed


async def initialize_services(settings: Settings) -> ServiceManager:
    """Initialize all backend services."""
    logger.info("Initializing services...")
    
    # Set up environment variables for LangChain
    if settings.openai_api_key:
        import os
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    
    if settings.langchain_api_key:
        import os
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        os.environ["LANGCHAIN_TRACING_V2"] = str(settings.langchain_tracing_v2).lower()
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    
    # Initialize service manager
    service_manager = ServiceManager(settings)
    
    logger.info("Services initialized successfully")
    return service_manager


from .document_parser import DocumentParser
from .fact_extractor import FactExtractor
from .vectorstore import VectorStoreManager
from .metadata_tagger import MetadataTagger

__all__ = [
    "DocumentParser",
    "FactExtractor",
    "VectorStoreManager",
    "MetadataTagger",
    "ServiceManager",
    "initialize_services",
]