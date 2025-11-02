# Backend Architecture Overview

## Purpose

This document outlines the overall architecture and design principles for migrating the experimental code from `notebooks/document_processing_new_pipeline.ipynb` into a production-ready FastAPI backend.

## Design Principles

### 1. Separation of Concerns
- **API Layer**: FastAPI endpoints for HTTP communication
- **Service Layer**: Business logic and orchestration
- **Data Layer**: Database interactions (MongoDB, Qdrant)
- **Domain Layer**: Core models and entities (Pydantic models)
- **Infrastructure Layer**: External integrations (Docling, LangChain, OpenAI)

### 2. Modularity
- Each component should be independently testable
- Clear interfaces between modules
- Minimal coupling between layers

### 3. Async-First
- Use async/await throughout for better performance
- Non-blocking I/O operations
- Efficient handling of concurrent requests

### 4. Configuration Management
- Environment-based configuration
- Secrets management (API keys, database credentials)
- Feature flags for experimental features

### 5. Error Handling
- Meaningful error messages for clients
- Proper HTTP status codes
- Structured logging for debugging

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Document   │  │     Fact     │  │  Comparison  │       │
│  │  Processing  │  │  Extraction  │  │    Agent     │       │
│  │   Endpoints  │  │   Endpoints  │  │   Endpoints  │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                  │                  │             │
├─────────┼──────────────────┼──────────────────┼─────────────┤
│         │                  │                  │             │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐       │
│  │   Document   │  │     Fact     │  │  Comparison  │       │
│  │  Processing  │  │  Extraction  │  │    Agent     │       │
│  │   Service    │  │   Service    │  │   Service    │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                  │                  │             │
├─────────┼──────────────────┼──────────────────┼─────────────┤
│         │                  │                  │             │
│  ┌──────▼───────────────────▼──────────────────▼───────┐    │
│  │              Core Domain Models                     │    │
│  │  (Section, Chunk, Fact, Entity, Attribute, Value)   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Docling    │  │   LangChain  │  │    Qdrant    │       │
│  │ Integration  │  │  /LangGraph  │  │  VectorStore │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   MongoDB    │  │    OpenAI    │  │    Pint      │       │
│  │   Client     │  │     LLM      │  │ Unit Normaliz│       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Folder Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI application entry point
│   ├── config.py                    # Configuration management
│   ├── dependencies.py              # FastAPI dependencies
│   │
│   ├── api/                         # API layer
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── documents.py         # Document processing endpoints
│   │   │   ├── facts.py             # Fact extraction endpoints
│   │   │   ├── comparison.py        # Comparison agent endpoints
│   │   │   └── health.py            # Health check endpoints
│   │   └── schemas/                 # Request/Response schemas
│   │       ├── __init__.py
│   │       ├── document.py
│   │       ├── fact.py
│   │       └── comparison.py
│   │
│   ├── services/                    # Business logic layer
│   │   ├── __init__.py
│   │   ├── document_processing.py   # Document parsing & chunking
│   │   ├── fact_extraction.py       # Fact extraction orchestration
│   │   ├── comparison_agent.py      # LangGraph comparison workflow
│   │   └── retrieval.py             # RAG retrieval logic
│   │
│   ├── models/                      # Domain models (Pydantic)
│   │   ├── __init__.py
│   │   ├── document.py              # Section, SectionChunk
│   │   ├── fact.py                  # Fact, Entity, Attribute, Value
│   │   └── comparison.py            # ComparisonResult, Verdict
│   │
│   ├── core/                        # Core utilities
│   │   ├── __init__.py
│   │   ├── docling_parser.py        # Docling integration
│   │   ├── sectionizer.py           # CSI-aware document sectionizer
│   │   ├── chunker.py               # Document chunking logic
│   │   ├── unit_normalizer.py       # Pint-based unit normalization
│   │   └── token_counter.py         # Token counting utilities
│   │
│   ├── agents/                      # LangGraph agents
│   │   ├── __init__.py
│   │   ├── comparison_graph.py      # LangGraph state machine
│   │   ├── nodes.py                 # Agent nodes (retrieve, compare, etc.)
│   │   └── prompts.py               # LLM prompts
│   │
│   ├── retrievers/                  # RAG retrievers
│   │   ├── __init__.py
│   │   ├── base.py                  # Base retriever interface
│   │   ├── dense.py                 # Dense vector retriever
│   │   ├── sparse.py                # BM25 sparse retriever
│   │   ├── ensemble.py              # Ensemble retriever
│   │   └── query_builder.py         # Query construction logic
│   │
│   ├── db/                          # Database layer
│   │   ├── __init__.py
│   │   ├── mongodb.py               # MongoDB client & operations
│   │   └── qdrant.py                # Qdrant vector store client
│   │
│   └── utils/                       # Shared utilities
│       ├── __init__.py
│       ├── logging.py               # Logging configuration
│       └── exceptions.py            # Custom exceptions
│
├── tests/                           # Unit and integration tests
│   ├── __init__.py
│   ├── test_api/
│   ├── test_services/
│   ├── test_models/
│   └── test_core/
│
├── alembic/                         # Database migrations (if needed)
│
├── pyproject.toml                   # Project dependencies (uv)
├── .env.example                     # Example environment variables
└── README.md                        # Backend documentation
```

## Technology Stack

### Core Framework
- **FastAPI**: Modern, fast web framework with automatic OpenAPI docs
- **Pydantic**: Data validation and settings management
- **Python 3.13**: Latest Python version with performance improvements

### Document Processing
- **Docling**: PDF parsing with OCR support (EasyOCR)
- **tiktoken**: Token counting for LLM context management

### AI/ML Stack
- **LangChain**: LLM orchestration and chaining
- **LangGraph**: State machine for agentic workflows
- **OpenAI**: GPT-4 family models for fact extraction and comparison
- **Qdrant**: In-memory vector database for hybrid search
- **FastEmbed**: Fast embedding generation

### Data Storage
- **MongoDB**: Document storage for facts and metadata
- **Qdrant**: Vector storage for semantic search
- **Local Filesystem**: Document storage

### Utilities
- **pint**: Unit normalization and conversion
- **pandas**: Data manipulation (minimal use)
- **uvicorn**: ASGI server

## Key Design Decisions

### 1. Async Architecture
All I/O operations (database, LLM calls, file operations) will use async/await to maximize throughput and handle concurrent requests efficiently.

### 2. Dependency Injection
FastAPI's dependency injection system will be used for:
- Database connections
- LLM clients
- Configuration
- Authentication/authorization (future)

### 3. Pydantic Models Everywhere
- Request/response validation
- Configuration management
- Domain models
- Database schemas

### 4. Structured Logging
- Use Python's logging module with structured output
- Log levels: DEBUG for tracing, INFO for operations, ERROR for failures
- Include request IDs for tracing

### 5. Error Handling Strategy
- Custom exception classes for different error types
- FastAPI exception handlers for consistent error responses
- Meaningful error messages for clients
- Detailed logging for debugging

### 6. Configuration Management
- Environment variables for secrets (API keys, DB credentials)
- Config file for application settings
- Separate configs for dev/staging/prod

### 7. Testing Strategy
- Unit tests for core logic (sectionizer, chunker, unit normalizer)
- Integration tests for services
- API tests for endpoints
- Mock external dependencies (LLM, databases)

## Migration Strategy

### Phase 1: Core Infrastructure
1. Set up FastAPI application structure
2. Implement configuration management
3. Set up logging and error handling
4. Create base Pydantic models

### Phase 2: Document Processing
1. Migrate Docling integration
2. Implement sectionizer and chunker
3. Create document processing service
4. Build document processing API endpoints

### Phase 3: Fact Extraction
1. Migrate fact extraction Pydantic models
2. Implement fact extraction service
3. Integrate unit normalization
4. Create fact extraction API endpoints

### Phase 4: RAG & Agents
1. Set up Qdrant vector store
2. Implement retrievers (dense, sparse, ensemble)
3. Build LangGraph comparison agent
4. Create comparison API endpoints

### Phase 5: Testing & Documentation
1. Write unit and integration tests
2. Generate OpenAPI documentation
3. Create deployment documentation
4. Performance testing and optimization

## Non-Functional Requirements

### Performance
- API response time < 2s for document upload
- Fact extraction: ~30s for typical construction spec document
- Comparison query: < 5s for single fact comparison

### Scalability
- Support concurrent document processing
- Horizontal scaling via multiple workers
- Async operations for I/O-bound tasks

### Reliability
- Graceful error handling
- Retry logic for external API calls
- Health check endpoints

### Security
- API key authentication (future)
- Input validation and sanitization
- Secure storage of credentials
- CORS configuration

### Observability
- Structured logging
- Request tracing
- Performance metrics
- Error tracking

## Next Steps

Refer to the following specification documents for detailed implementation guidance:

1. **02-module-organization.md**: Detailed module responsibilities and notebook-to-backend mapping
2. **03-api-design.md**: API endpoint specifications and schemas
3. **04-document-processing-pipeline.md**: Document processing implementation details
4. **05-fact-extraction.md**: Fact extraction system design
5. **06-rag-and-agents.md**: RAG and agent architecture
6. **07-evaluation-exclusion.md**: What to exclude from production backend

