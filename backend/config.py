"""Configuration settings for the Construction Spec Assistant backend."""

import logging
from typing import List, Optional
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings."""
    
    # API Configuration
    api_title: str = "Construction Spec Assistant API"
    api_description: str = "API for processing construction documents and identifying discrepancies"
    api_version: str = "1.0.0"
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # CORS Configuration
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    cors_methods: List[str] = ["GET", "POST", "PUT", "DELETE"]
    cors_headers: List[str] = ["*"]
    
    # File Upload Configuration
    max_file_size_mb: int = 100
    allowed_file_types: List[str] = ["application/pdf"]
    upload_directory: str = "./uploads"
    
    # LLM Configuration
    openai_api_key: Optional[str] = None
    langchain_api_key: Optional[str] = None
    langchain_tracing_v2: bool = True
    langchain_project: str = "construction-spec-assistant"
    default_llm_provider: str = "openai"
    default_llm_model: str = "gpt-4o-mini"
    
    # Document Processing Configuration
    max_tokens_per_chunk: int = 700
    overlap_tokens: int = 80
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1024
    
    # Vector Store Configuration
    qdrant_url: str = "http://localhost:6333"
    use_in_memory_qdrant: bool = True
    
    # Catalog Configuration
    catalog_path: str = "backend/data/spec_attributes_catalog.yaml"
    
    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


def setup_logging(settings: Settings) -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format=settings.log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("backend.log") if not settings.debug else logging.NullHandler()
        ]
    )
    
    # Set specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    
    if settings.debug:
        logging.getLogger("backend").setLevel(logging.DEBUG)


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()


# Global settings instance
settings = get_settings()
