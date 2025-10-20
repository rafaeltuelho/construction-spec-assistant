# Construction Spec Assistant Backend

A FastAPI-based backend service for processing construction documents, extracting facts, and performing automated comparisons between specifications and submittals.

## Features

- **Document Processing**: PDF parsing using Docling with OCR support
- **Fact Extraction**: LLM-based extraction of structured facts from specifications
- **Vector Storage**: In-memory Qdrant for document indexing and retrieval
- **Hybrid Search**: Combined dense and sparse vector search (BM25)
- **LangGraph Agents**: Multi-step workflows for retrieval and comparison
- **REST API**: FastAPI with OpenAPI documentation

## Architecture

```
backend/
├── models/           # Pydantic models and data classes
├── services/         # Business logic services
├── agents/          # LangGraph agents for workflows
├── api/             # FastAPI routers
├── utils/           # Utility functions
└── data/            # Configuration files
```

## Quick Start

### 1. Install Dependencies

```bash
# Install Python dependencies
uv sync

# Or with pip
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create a `.env` file in the project root:

```env
# OpenAI API Key (required for LLM operations)
OPENAI_API_KEY=your_openai_api_key_here

# LangSmith API Key (optional, for tracing)
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=construction-spec-assistant

# API Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=false

# File Upload Configuration
MAX_FILE_SIZE_MB=100
UPLOAD_DIRECTORY=./uploads
```

### 3. Run the Server

```bash
# Using uvicorn directly
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Or using the main module
python -m backend.main
```

### 4. Access the API

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/v1/health
- **Status**: http://localhost:8000/api/v1/status

## API Usage

### Upload Documents

```bash
# Upload a specification document
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@specification.pdf" \
  -F "document_type=specification" \
  -F 'metadata={"project": "Building A"}'

# Upload a submittal document
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@submittal.pdf" \
  -F "document_type=submittal"
```

### Check Document Status

```bash
# Get document details
curl "http://localhost:8000/api/v1/documents/{document_id}"

# Check processing status
curl "http://localhost:8000/api/v1/documents/{document_id}/status"

# Get extracted facts (for specifications)
curl "http://localhost:8000/api/v1/documents/{document_id}/facts"
```

### Create Reviews

```bash
# Create a comparison review
curl -X POST "http://localhost:8000/api/v1/reviews" \
  -H "Content-Type: application/json" \
  -d '{
    "specification_document_id": "spec_doc_id",
    "submittal_document_id": "submittal_doc_id",
    "review_scope": ["14 24 00"],
    "llm_provider": "openai",
    "llm_model": "gpt-4o-mini"
  }'
```

### Get Review Results

```bash
# Get review details
curl "http://localhost:8000/api/v1/reviews/{review_id}"

# Get findings
curl "http://localhost:8000/api/v1/reviews/{review_id}/findings"

# Filter by finding type
curl "http://localhost:8000/api/v1/reviews/{review_id}/findings?finding_type=inconsistent"
```

## Core Services

### Document Parser

Processes PDF documents using Docling with CSI-aware section extraction:

```python
from backend.services import DocumentParser

parser = DocumentParser()
doc_info = parser.parse_document_with_docling(
    pdf_path="specification.pdf",
    is_csi_spec=True,
    write_artifacts=True
)
```

### Fact Extractor

Extracts structured facts from document chunks using LLM:

```python
from backend.services import FactExtractor

extractor = FactExtractor(model="gpt-4o-mini")
facts = extractor.harvest_facts_for_doc(
    doc_info=doc_info,
    entity_hints={"default": "elevator"},
    normalize=True
)
```

### Vector Store Manager

Manages document indexing and retrieval:

```python
from backend.services import VectorStoreManager

vectorstore = VectorStoreManager()
vectorstore.create_collection("submittals", hybrid=True)
vectorstore.add_documents(
    collection_name="submittals",
    documents=chunk_texts
)
```

### LangGraph Agents

Multi-step workflows for retrieval and comparison:

```python
from backend.agents import RetrievalAgent, ComparatorAgent

# Retrieve relevant chunks
retrieval_agent = RetrievalAgent(vectorstore)
candidates = retrieval_agent.retrieve(
    query="rated speed 120 fpm",
    collection_name="submittals",
    strategy=RetrievalStrategy.HYBRID
)

# Compare facts
comparator_agent = ComparatorAgent(retrieval_agent)
result = comparator_agent.compare(
    spec_fact=fact,
    collection_name="submittals",
    catalog=catalog
)
```

## Configuration

The backend uses Pydantic settings with environment variable support:

- **API Configuration**: Host, port, CORS settings
- **LLM Configuration**: Model selection, API keys
- **Document Processing**: Chunk sizes, token limits
- **Vector Store**: Embedding models, dimensions
- **Logging**: Log levels and formats

## Development

### Project Structure

- `models/`: Data models and schemas
- `services/`: Core business logic
- `agents/`: LangGraph workflows
- `api/`: FastAPI endpoints
- `utils/`: Helper functions
- `data/`: Configuration files

### Adding New Features

1. **Models**: Add new Pydantic models in `models/`
2. **Services**: Implement business logic in `services/`
3. **Agents**: Create LangGraph workflows in `agents/`
4. **API**: Add endpoints in `api/`
5. **Tests**: Write tests for new functionality

### Logging

The backend uses structured logging with configurable levels:

```python
import logging
logger = logging.getLogger(__name__)
logger.info("Processing document")
```

## Troubleshooting

### Common Issues

1. **OpenAI API Key**: Ensure `OPENAI_API_KEY` is set
2. **File Upload Size**: Check `MAX_FILE_SIZE_MB` setting
3. **Memory Usage**: Large documents may require more RAM
4. **OCR Performance**: GPU acceleration improves OCR speed

### Debug Mode

Enable debug mode for detailed logging:

```bash
DEBUG=true uvicorn backend.main:app --reload
```

## Production Deployment

For production deployment:

1. **Database**: Replace in-memory storage with persistent database
2. **Vector Store**: Use external Qdrant instance
3. **File Storage**: Use cloud storage for uploaded files
4. **Scaling**: Use multiple workers with load balancer
5. **Monitoring**: Add health checks and metrics
6. **Security**: Implement authentication and rate limiting

## License

This project is part of the Construction Spec Assistant system.
