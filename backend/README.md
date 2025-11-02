# Construction Spec Assistant - Backend

FastAPI backend for the Construction Spec Assistant, an AI-powered system for reviewing construction specifications and submittals.

## Features

- **Document Processing**: PDF parsing with OCR using Docling
- **Fact Extraction**: LLM-based structured fact extraction with EAV schema
- **Vector Search**: Hybrid dense + sparse retrieval with Qdrant
- **Agentic Workflows**: LangGraph-powered comparison agents
- **Multi-LLM Support**: OpenAI, Anthropic, and Ollama integration

## Prerequisites

- Python 3.13+
- MongoDB (local or remote)
- Qdrant (optional - can use in-memory mode)
- OpenAI API key (or Anthropic/Ollama)

## Installation

### Using uv (recommended)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
cd backend
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

### Using pip

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Configuration

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and set your configuration:

```bash
# Required
OPENAI_API_KEY="your-openai-api-key-here"

# Optional (defaults are fine for development)
MONGODB_URL="mongodb://localhost:27017"
QDRANT_USE_MEMORY=true
LOG_LEVEL="INFO"
```

## Running the Application

### Development Mode

```bash
# From the backend directory
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or using the Python script:

```bash
python -m app.main
```

### Production Mode

```bash
# Set environment to production
export ENVIRONMENT=production

# Run with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

Once the server is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/api/v1/docs
- **ReDoc**: http://localhost:8000/api/v1/redoc
- **OpenAPI JSON**: http://localhost:8000/api/v1/openapi.json

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI application entry point
│   ├── config.py                    # Configuration management
│   ├── dependencies.py              # FastAPI dependencies
│   │
│   ├── api/                         # API layer
│   │   ├── v1/
│   │   │   ├── health.py            # Health check endpoints
│   │   │   ├── documents.py         # Document processing endpoints (TODO)
│   │   │   ├── facts.py             # Fact extraction endpoints (TODO)
│   │   │   └── comparison.py        # Comparison agent endpoints (TODO)
│   │   └── schemas/                 # Request/Response schemas
│   │       └── common.py            # Common schemas
│   │
│   ├── services/                    # Business logic layer (TODO)
│   ├── models/                      # Domain models (TODO)
│   ├── core/                        # Core utilities (TODO)
│   ├── agents/                      # LangGraph agents (TODO)
│   ├── retrievers/                  # RAG retrievers (TODO)
│   ├── db/                          # Database layer (TODO)
│   │
│   └── utils/                       # Shared utilities
│       ├── logging.py               # Logging configuration
│       └── exceptions.py            # Custom exceptions
│
├── tests/                           # Unit and integration tests (TODO)
├── pyproject.toml                   # Project dependencies
├── .env.example                     # Example environment variables
└── README.md                        # This file
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_api/test_health.py
```

## Development

### Code Formatting

```bash
# Format code with black
black app tests

# Lint with ruff
ruff check app tests

# Type check with mypy
mypy app
```

### Adding Dependencies

```bash
# Using uv
uv pip install package-name

# Using pip
pip install package-name

# Don't forget to update pyproject.toml
```

## Health Check

Check if the application is running:

```bash
curl http://localhost:8000/api/v1/health
```

Expected response:

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2024-01-01T12:00:00Z",
  "services": {
    "mongodb": "connected",
    "qdrant": "connected",
    "openai": "configured"
  }
}
```

## Environment Variables

See `.env.example` for all available configuration options.

### Key Variables

- `OPENAI_API_KEY`: OpenAI API key (required)
- `MONGODB_URL`: MongoDB connection URL
- `QDRANT_USE_MEMORY`: Use in-memory Qdrant (true for development)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `ENVIRONMENT`: Environment (development, staging, production)

## Troubleshooting

### MongoDB Connection Issues

```bash
# Check if MongoDB is running
mongosh --eval "db.adminCommand('ping')"

# Start MongoDB (if using Docker)
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

### Import Errors

Make sure you're in the backend directory and the virtual environment is activated:

```bash
cd backend
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

## Next Steps

This is **Phase 1: Core Infrastructure**. The following phases will implement:

- **Phase 2**: Document processing (Docling, sectionizer, chunker)
- **Phase 3**: Fact extraction (LLM-based extraction, unit normalization)
- **Phase 4**: RAG & Agents (retrievers, LangGraph comparison agent)
- **Phase 5**: Testing & Documentation

## License

See the main project LICENSE file.

