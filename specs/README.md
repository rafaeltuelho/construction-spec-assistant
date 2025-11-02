# Backend Architecture Specifications

This folder contains comprehensive specification documents for migrating the experimental code from `notebooks/document_processing_new_pipeline.ipynb` into a production-ready FastAPI backend.

## 📋 Document Overview

### [01-architecture-overview.md](./01-architecture-overview.md)
**Purpose**: High-level architecture and design principles

**Contents**:
- Overall system architecture
- Backend folder structure
- Technology stack
- Design principles (separation of concerns, async-first, etc.)
- Migration strategy and phases
- Non-functional requirements

**Read this first** to understand the big picture.

---

### [02-module-organization.md](./02-module-organization.md)
**Purpose**: Detailed module responsibilities and notebook-to-backend mapping

**Contents**:
- Complete mapping of notebook cells to backend modules
- Module responsibilities and interfaces
- Dependency guidelines (what can import what)
- Testing strategy
- Import rules and best practices

**Use this** to understand where each piece of notebook code should go.

---

### [03-api-design.md](./03-api-design.md)
**Purpose**: REST API endpoint specifications

**Contents**:
- All API endpoints with request/response schemas
- Error handling and error codes
- Authentication strategy (future)
- OpenAPI documentation
- CORS configuration

**Use this** to implement FastAPI endpoints and understand the API contract.

---

### [04-document-processing-pipeline.md](./04-document-processing-pipeline.md)
**Purpose**: Document processing implementation details

**Contents**:
- Docling integration (PDF parsing with OCR)
- CSI-aware sectionization (hierarchical document structure)
- Intelligent chunking (token-limited with overlap)
- Storage in MongoDB and Qdrant

**Use this** to implement document processing services.

---

### [05-fact-extraction.md](./05-fact-extraction.md)
**Purpose**: Fact extraction system design

**Contents**:
- Pydantic models (Entity-Attribute-Value schema)
- LLM-based extraction with structured output
- Unit normalization using pint
- Fact deduplication
- MongoDB storage

**Use this** to implement fact extraction services.

---

### [06-rag-and-agents.md](./06-rag-and-agents.md)
**Purpose**: RAG retrieval and LangGraph agent architecture

**Contents**:
- Query builder (dense + sparse queries)
- Retriever implementations (dense, sparse, ensemble)
- LangGraph comparison agent (state machine)
- Comparison service orchestration

**Use this** to implement RAG retrievers and comparison agents.

---

### [07-evaluation-exclusion.md](./07-evaluation-exclusion.md)
**Purpose**: What to exclude from production backend

**Contents**:
- RAGAS evaluation code (DO NOT include in backend)
- Test dataset generation (offline activity)
- Retriever comparison logic (experimental)
- Where evaluation code should live (`evaluation/` folder)
- Backend testing vs. evaluation

**Read this** to understand what NOT to implement in the backend.

---

## 🚀 Implementation Order

Follow this order when implementing the backend:

### Phase 1: Core Infrastructure
1. Set up FastAPI application structure (`backend/app/main.py`)
2. Implement configuration management (`backend/app/config.py`)
3. Set up logging and error handling
4. Create base Pydantic models

**Reference**: `01-architecture-overview.md`, `02-module-organization.md`

---

### Phase 2: Document Processing
1. Implement Docling integration (`backend/app/core/docling_parser.py`)
2. Implement sectionizer (`backend/app/core/sectionizer.py`)
3. Implement chunker (`backend/app/core/chunker.py`)
4. Create document processing service (`backend/app/services/document_processing.py`)
5. Build document processing API endpoints (`backend/app/api/v1/documents.py`)

**Reference**: `04-document-processing-pipeline.md`, `03-api-design.md`

---

### Phase 3: Fact Extraction
1. Define fact Pydantic models (`backend/app/models/fact.py`)
2. Implement unit normalizer (`backend/app/core/unit_normalizer.py`)
3. Create fact extraction service (`backend/app/services/fact_extraction.py`)
4. Build fact extraction API endpoints (`backend/app/api/v1/facts.py`)

**Reference**: `05-fact-extraction.md`, `03-api-design.md`

---

### Phase 4: RAG & Agents
1. Set up Qdrant vector store (`backend/app/db/qdrant.py`)
2. Implement retrievers (`backend/app/retrievers/`)
3. Build LangGraph comparison agent (`backend/app/agents/comparison_graph.py`)
4. Create comparison service (`backend/app/services/comparison_agent.py`)
5. Build comparison API endpoints (`backend/app/api/v1/comparison.py`)

**Reference**: `06-rag-and-agents.md`, `03-api-design.md`

---

### Phase 5: Testing & Documentation
1. Write unit tests (`backend/tests/`)
2. Write integration tests
3. Generate OpenAPI documentation
4. Create deployment documentation
5. Performance testing and optimization

**Reference**: `02-module-organization.md`, `03-api-design.md`

---

## ⚠️ Important Notes

### What to Include in Backend
✅ Document processing (Docling, sectionizer, chunker)  
✅ Fact extraction (LLM, Pydantic models, unit normalization)  
✅ RAG retrievers (dense, sparse, ensemble)  
✅ LangGraph comparison agent  
✅ API endpoints and services  
✅ Database clients (MongoDB, Qdrant)  

### What to Exclude from Backend
❌ RAGAS framework integration  
❌ Test dataset generation  
❌ Retriever evaluation pipeline  
❌ Metric visualization  
❌ Golden dataset creation  

**See**: `07-evaluation-exclusion.md` for details

---

## 📁 Backend Folder Structure

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
├── pyproject.toml                   # Project dependencies (uv)
├── .env.example                     # Example environment variables
└── README.md                        # Backend documentation
```

---

## 🛠️ Technology Stack

- **FastAPI**: Modern, fast web framework with automatic OpenAPI docs
- **Pydantic**: Data validation and settings management
- **Python 3.13**: Latest Python version with performance improvements
- **Docling**: PDF parsing with OCR support (EasyOCR)
- **LangChain**: LLM orchestration and chaining
- **LangGraph**: State machine for agentic workflows
- **OpenAI**: GPT-4 family models for fact extraction and comparison
- **Qdrant**: In-memory vector database for hybrid search
- **MongoDB**: Document storage for facts and metadata
- **pint**: Unit normalization and conversion
- **uvicorn**: ASGI server

---

## 📚 Additional Resources

- **Notebook**: `notebooks/document_processing_new_pipeline.ipynb` (original experimentation)
- **Project Overview**: `docs/project-overview.md` (high-level project description)
- **Backend Rules**: `.augment/rules/imported/backend-rule.md` (development guidelines)

---

## 🤝 Contributing

When implementing the backend:

1. Follow the specifications in this folder
2. Respect the module organization and dependencies
3. Write tests for all new code
4. Use async/await for I/O operations
5. Log meaningful messages (DEBUG for tracing, INFO for operations, ERROR for failures)
6. Return meaningful error messages to clients
7. Document all public APIs with docstrings

---

## ❓ Questions?

If you have questions about the specifications:

1. Check the relevant specification document
2. Review the original notebook for context
3. Consult the project overview document
4. Ask the team for clarification

---

**Last Updated**: 2025-11-01  
**Status**: Ready for implementation  
**Next Step**: Begin Phase 1 (Core Infrastructure)

