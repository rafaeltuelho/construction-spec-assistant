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

# From the project root directory
cd /path/to/construction-spec-assistant

# Install all dependencies (including dev extras)
uv sync --extra dev
```

**Note**: The project uses a unified `pyproject.toml` at the root level. All dependencies are managed from the project root, not from the `backend` directory.

### Alternative: Using pip with virtual environment

```bash
# From the project root directory
cd /path/to/construction-spec-assistant

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

## Setting Up Dependencies with Docker

### MongoDB and Qdrant with Docker Compose

The easiest way to run MongoDB and Qdrant is using Docker Compose. This provides persistent storage and easy management.

#### 1. Create `docker-compose.yml`

Create a `docker-compose.yml` file in the project root:

```yaml
version: '3.8'

services:
  mongodb:
    image: mongo:7
    container_name: mongodb
    ports:
      - "27017:27017"
    volumes:
      - ./mongodb_data:/data/db
    environment:
      - MONGO_INITDB_DATABASE=construction_spec_assistant
    restart: unless-stopped

  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant
    ports:
      - "6333:6333"  # HTTP API
      - "6334:6334"  # gRPC (optional)
    volumes:
      - ./qdrant_storage:/qdrant/storage:z
    environment:
      - QDRANT__SERVICE__HTTP_PORT=6333
      - QDRANT__SERVICE__GRPC_PORT=6334
    restart: unless-stopped
```

#### 2. Start Services

```bash
# Start both MongoDB and Qdrant
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove data volumes
docker-compose down -v
```

#### 3. Verify Services

**MongoDB**:
```bash
# Check MongoDB connection
mongosh --eval "db.adminCommand('ping')"

# Expected output: { ok: 1 }
```

**Qdrant**:
```bash
# Check Qdrant health
curl http://localhost:6333/

# Expected output: {"title":"qdrant - vector search engine","version":"1.x.x"}

# Access Qdrant Web UI
open http://localhost:6333/dashboard
```

#### 4. Useful Docker Commands

```bash
# View logs for specific service
docker-compose logs -f mongodb
docker-compose logs -f qdrant

# Restart a service
docker-compose restart mongodb
docker-compose restart qdrant

# Stop a specific service
docker-compose stop mongodb

# Remove containers but keep data
docker-compose down

# Backup MongoDB data
docker exec mongodb mongodump --out=/data/db/backup

# Backup Qdrant data
tar -czf qdrant_backup_$(date +%Y%m%d).tar.gz qdrant_storage/
```

### Alternative: Individual Docker Containers

If you prefer to run containers individually:

**MongoDB**:
```bash
docker run -d \
  --name mongodb \
  -p 27017:27017 \
  -v $(pwd)/mongodb_data:/data/db \
  mongo:7
```

**Qdrant**:
```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant:latest
```

## Configuration

1. Copy the example environment file:

```bash
# From the project root
cp backend/.env.example backend/.env
```

2. Edit `.env` and set your configuration:

**For Docker Compose setup (persistent storage)**:
```bash
# Required
OPENAI_API_KEY="your-openai-api-key-here"

# MongoDB Configuration
MONGODB_URL="mongodb://localhost:27017"
MONGODB_DB_NAME="construction_spec_assistant"

# Qdrant Configuration (Persistent)
QDRANT_USE_MEMORY=false
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=construction_docs

# Logging
LOG_LEVEL="INFO"
```

**For development without Docker (in-memory)**:
```bash
# Required
OPENAI_API_KEY="your-openai-api-key-here"

# MongoDB Configuration (requires local MongoDB)
MONGODB_URL="mongodb://localhost:27017"

# Qdrant Configuration (In-Memory)
QDRANT_USE_MEMORY=true

# Logging
LOG_LEVEL="INFO"
```

## Running the Application

### Development Mode

#### Option 1: Using `uv run` (recommended)

```bash
# From the project root directory
uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Option 2: With activated virtual environment

```bash
# From the project root directory
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Run with uvicorn
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Option 3: Using Python module

```bash
# From the project root with activated venv
cd backend
python -m app.main
```

### Production Mode

```bash
# Set environment to production
export ENVIRONMENT=production

# From the project root
uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 4
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

### Utility Scripts

The `backend/scripts/` directory contains utility scripts for development and testing.

#### MongoDB Cleanup Script

Clean up MongoDB collections for testing purposes:

```bash
# From project root - Interactive mode (with confirmation)
uv run python backend/scripts/cleanup_mongodb.py

# From project root - Non-interactive mode (skip confirmation)
uv run python backend/scripts/cleanup_mongodb.py --yes

# From backend directory
cd backend
uv run python scripts/cleanup_mongodb.py
```

This script will:
- Connect to MongoDB using your application configuration
- Display current document counts for all collections
- Delete all documents from: chunks, document_comparison_results, documents, facts, sections
- Provide a summary of deleted documents

See `backend/scripts/README.md` for more details.

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
docker-compose ps mongodb

# Check MongoDB logs
docker-compose logs -f mongodb

# Test connection
mongosh --eval "db.adminCommand('ping')"

# Restart MongoDB
docker-compose restart mongodb

# If using Docker Compose, ensure services are running
docker-compose up -d
```

### Qdrant Connection Issues

```bash
# Check if Qdrant is running
docker-compose ps qdrant

# Check Qdrant logs
docker-compose logs -f qdrant

# Test connection
curl http://localhost:6333/

# Access Qdrant dashboard
open http://localhost:6333/dashboard

# Restart Qdrant
docker-compose restart qdrant
```

### Port Already in Use

If you get "port already in use" errors:

```bash
# Check what's using the port
lsof -i :27017  # MongoDB
lsof -i :6333   # Qdrant
lsof -i :8000   # FastAPI

# Stop conflicting services
docker-compose down

# Or kill specific process
kill -9 <PID>
```

### Data Persistence Issues

```bash
# Check if data directories exist
ls -la mongodb_data/
ls -la qdrant_storage/

# Fix permissions (Linux/Mac)
sudo chown -R $USER:$USER mongodb_data/ qdrant_storage/

# Reset data (WARNING: deletes all data)
docker-compose down -v
rm -rf mongodb_data/ qdrant_storage/
docker-compose up -d
```

### Import Errors

Make sure you're in the project root directory and the virtual environment is activated:

```bash
cd /path/to/construction-spec-assistant
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Collection Not Found Error

If you get "Collection construction_docs not found":

```bash
# The collection is created automatically on first document indexing
# Or restart the backend to trigger collection creation on startup
docker-compose restart

# Check Qdrant collections
curl http://localhost:6333/collections
```

## License

See the main project LICENSE file.

