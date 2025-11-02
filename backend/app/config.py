"""
Configuration management for the Construction Spec Assistant backend.

Uses Pydantic Settings for environment-based configuration with validation.
"""

from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Environment variables can be set in .env file or system environment.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application Settings
    app_name: str = Field(
        default="Construction Spec Assistant",
        description="Application name"
    )
    app_version: str = Field(
        default="0.1.0",
        description="Application version"
    )
    environment: str = Field(
        default="development",
        description="Environment (development, staging, production)"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    
    # API Settings
    api_v1_prefix: str = Field(
        default="/api/v1",
        description="API v1 prefix"
    )
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="CORS allowed origins"
    )
    
    # Logging Settings
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    log_format: str = Field(
        default="json",
        description="Log format (json or text)"
    )
    
    # MongoDB Settings
    mongodb_url: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection URL"
    )
    mongodb_database: str = Field(
        default="construction_spec_assistant",
        description="MongoDB database name"
    )
    mongodb_max_pool_size: int = Field(
        default=10,
        description="MongoDB connection pool size"
    )
    
    # Qdrant Settings
    qdrant_host: str = Field(
        default="localhost",
        description="Qdrant host"
    )
    qdrant_port: int = Field(
        default=6333,
        description="Qdrant port"
    )
    qdrant_collection_name: str = Field(
        default="construction_docs",
        description="Qdrant collection name"
    )
    qdrant_use_memory: bool = Field(
        default=True,
        description="Use in-memory Qdrant (for development)"
    )
    
    # OpenAI Settings
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key"
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model for fact extraction"
    )
    openai_temperature: float = Field(
        default=0.0,
        description="OpenAI temperature (0.0 = deterministic)"
    )
    openai_max_tokens: int = Field(
        default=4096,
        description="OpenAI max tokens per request"
    )
    
    # Anthropic Settings (optional)
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key"
    )
    anthropic_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Anthropic model"
    )
    
    # Ollama Settings (optional)
    ollama_base_url: Optional[str] = Field(
        default=None,
        description="Ollama base URL"
    )
    ollama_model: Optional[str] = Field(
        default=None,
        description="Ollama model name"
    )
    
    # LangSmith Settings (optional)
    langsmith_api_key: Optional[str] = Field(
        default=None,
        description="LangSmith API key for tracing"
    )
    langsmith_project: Optional[str] = Field(
        default="construction-spec-assistant",
        description="LangSmith project name"
    )
    
    # Document Processing Settings
    max_file_size_mb: int = Field(
        default=50,
        description="Maximum file size in MB"
    )
    supported_file_types: List[str] = Field(
        default=[".pdf", ".docx", ".doc"],
        description="Supported file types"
    )
    upload_dir: str = Field(
        default="./data/uploads",
        description="Directory for uploaded files"
    )
    
    # Docling Settings
    docling_use_ocr: bool = Field(
        default=True,
        description="Enable OCR for document parsing"
    )
    docling_ocr_engine: str = Field(
        default="easyocr",
        description="OCR engine (easyocr or tesseract)"
    )
    
    # Chunking Settings
    chunk_size: int = Field(
        default=1000,
        description="Target chunk size in tokens"
    )
    chunk_overlap: int = Field(
        default=200,
        description="Overlap between chunks in tokens"
    )
    
    # Fact Extraction Settings
    fact_extraction_batch_size: int = Field(
        default=10,
        description="Number of chunks to process concurrently"
    )
    fact_confidence_threshold: float = Field(
        default=0.5,
        description="Minimum confidence for extracted facts"
    )
    
    # Retrieval Settings
    retrieval_top_k: int = Field(
        default=5,
        description="Number of documents to retrieve"
    )
    dense_weight: float = Field(
        default=0.5,
        description="Weight for dense retrieval (0-1)"
    )
    sparse_weight: float = Field(
        default=0.5,
        description="Weight for sparse retrieval (0-1)"
    )
    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        description="Embedding model for dense retrieval"
    )
    
    # Comparison Agent Settings
    comparison_max_retries: int = Field(
        default=3,
        description="Maximum retries for comparison agent"
    )
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment."""
        valid_envs = ["development", "staging", "production"]
        v_lower = v.lower()
        if v_lower not in valid_envs:
            raise ValueError(f"Invalid environment: {v}. Must be one of {valid_envs}")
        return v_lower
    
    @field_validator("dense_weight", "sparse_weight")
    @classmethod
    def validate_weight(cls, v: float) -> float:
        """Validate retrieval weights."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Weight must be between 0.0 and 1.0, got {v}")
        return v
    
    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == "development"


# Global settings instance
settings = Settings()

