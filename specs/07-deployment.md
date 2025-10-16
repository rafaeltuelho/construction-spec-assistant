# Deployment Specification

## Overview

This specification defines the deployment configuration for the Architectural Submittal Reviewer system, including Docker containers, docker-compose setup, and CLI development mode.

## Docker Configuration

### Multi-Stage Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Create app directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv sync --frozen

# Development stage
FROM base as development

# Install development dependencies
RUN uv sync --dev

# Copy source code
COPY . .

# Create uploads directory
RUN mkdir -p /app/uploads

# Expose port
EXPOSE 8000

# Development command
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production stage
FROM base as production

# Copy source code
COPY . .

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Create necessary directories
RUN mkdir -p /app/uploads /app/data && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production command
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Python Project Configuration

```toml
# pyproject.toml
[project]
name = "construction-spec-assistant"
version = "0.1.0"
description = "Architectural Submittal Reviewer Backend"
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
dependencies = [
    "fastapi>=0.104.1",
    "uvicorn[standard]>=0.24.0",
    "python-multipart>=0.0.6",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "motor>=3.3.0",
    "qdrant-client>=1.7.0",
    "sentence-transformers>=2.2.2",
    "langchain>=0.1.0",
    "langchain-openai>=0.0.5",
    "langchain-anthropic>=0.1.0",
    "langchain-community>=0.0.10",
    "langgraph>=0.0.62",
    "docling>=1.0.0",
    "openai>=1.3.0",
    "anthropic>=0.7.0",
    "ollama>=0.1.0",
    "rank-bm25>=0.2.2",
    "numpy>=1.24.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.6",
    "aiofiles>=23.2.0",
    "httpx>=0.25.0",
    "structlog>=23.2.0",
    "prometheus-client>=0.19.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "black>=23.7.0",
    "isort>=5.12.0",
    "flake8>=6.0.0",
    "mypy>=1.5.0",
    "pre-commit>=3.3.0",
    "httpx>=0.25.0",
    "faker>=19.6.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.black]
line-length = 88
target-version = ['py311']

[tool.isort]
profile = "black"
multi_line_output = 3

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

## Docker Compose Configuration

### Complete Stack

```yaml
# docker-compose.yml
version: '3.8'

services:
  # MongoDB Database
  mongodb:
    image: mongo:7.0
    container_name: construction-mongodb
    restart: unless-stopped
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: password123
      MONGO_INITDB_DATABASE: construction_specs
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
      - ./scripts/mongo-init.js:/docker-entrypoint-initdb.d/mongo-init.js:ro
    networks:
      - construction-network
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Qdrant Vector Database
  qdrant:
    image: qdrant/qdrant:v1.7.0
    container_name: construction-qdrant
    restart: unless-stopped
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      QDRANT__SERVICE__HTTP_PORT: 6333
      QDRANT__SERVICE__GRPC_PORT: 6334
    networks:
      - construction-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Ollama (Optional - for local LLM)
  ollama:
    image: ollama/ollama:latest
    container_name: construction-ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0
    networks:
      - construction-network
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    profiles:
      - local-llm

  # FastAPI Application
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
    container_name: construction-api
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      # Database Configuration
      MONGODB_URL: mongodb://admin:password123@mongodb:27017/construction_specs?authSource=admin
      QDRANT_URL: http://qdrant:6333
      
      # LLM Configuration
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
      DEFAULT_LLM_PROVIDER: ${DEFAULT_LLM_PROVIDER:-openai}
      DEFAULT_MODEL: ${DEFAULT_MODEL:-gpt-4-turbo}
      
      # Application Configuration
      API_HOST: 0.0.0.0
      API_PORT: 8000
      LOG_LEVEL: INFO
      DEBUG: "false"
      
      # File Upload Configuration
      MAX_FILE_SIZE_MB: 100
      UPLOAD_DIRECTORY: /app/uploads
      
      # Storage Configuration
      DOCUMENT_STORAGE_PATH: /app/data/documents
      
      # Feature Flags
      ENABLE_VERIFICATION: "true"
      ENABLE_HUMAN_REVIEW: "true"
      ENABLE_CACHING: "true"
      DEBUG_MODE: "false"
    volumes:
      - uploads_data:/app/uploads
      - documents_data:/app/data/documents
    depends_on:
      mongodb:
        condition: service_healthy
      qdrant:
        condition: service_healthy
    networks:
      - construction-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Nginx Reverse Proxy (Optional)
  nginx:
    image: nginx:alpine
    container_name: construction-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - api
    networks:
      - construction-network
    profiles:
      - production

  # Redis for Caching (Optional)
  redis:
    image: redis:7-alpine
    container_name: construction-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - construction-network
    profiles:
      - production

volumes:
  mongodb_data:
    driver: local
  qdrant_data:
    driver: local
  ollama_data:
    driver: local
  uploads_data:
    driver: local
  documents_data:
    driver: local
  redis_data:
    driver: local

networks:
  construction-network:
    driver: bridge
```

### Development Docker Compose

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  # MongoDB for Development
  mongodb:
    image: mongo:7.0
    container_name: construction-mongodb-dev
    restart: unless-stopped
    ports:
      - "27017:27017"
    volumes:
      - mongodb_dev_data:/data/db
    networks:
      - construction-dev-network

  # Qdrant for Development
  qdrant:
    image: qdrant/qdrant:v1.7.0
    container_name: construction-qdrant-dev
    restart: unless-stopped
    ports:
      - "6333:6333"
    volumes:
      - qdrant_dev_data:/qdrant/storage
    networks:
      - construction-dev-network

  # Development API
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: development
    container_name: construction-api-dev
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      MONGODB_URL: mongodb://localhost:27017/construction_specs
      QDRANT_URL: http://localhost:6333
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
      DEBUG: "true"
      LOG_LEVEL: DEBUG
    volumes:
      - .:/app
      - uploads_dev_data:/app/uploads
    depends_on:
      - mongodb
      - qdrant
    networks:
      - construction-dev-network

volumes:
  mongodb_dev_data:
    driver: local
  qdrant_dev_data:
    driver: local
  uploads_dev_data:
    driver: local

networks:
  construction-dev-network:
    driver: bridge
```

## Environment Configuration

### Environment Variables

```bash
# .env.example
# Copy this file to .env and fill in your values

# Database Configuration
MONGODB_URL=mongodb://admin:password123@localhost:27017/construction_specs?authSource=admin
QDRANT_URL=http://localhost:6333

# LLM Provider API Keys
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Default LLM Configuration
DEFAULT_LLM_PROVIDER=openai
DEFAULT_MODEL=gpt-4-turbo

# Application Configuration
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
DEBUG=false

# File Upload Configuration
MAX_FILE_SIZE_MB=100
UPLOAD_DIRECTORY=./uploads

# Storage Configuration
DOCUMENT_STORAGE_PATH=./data/documents

# Feature Flags
ENABLE_VERIFICATION=true
ENABLE_HUMAN_REVIEW=true
ENABLE_CACHING=true
DEBUG_MODE=false

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Security Configuration (for future use)
SECRET_KEY=your_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Monitoring Configuration
ENABLE_METRICS=true
METRICS_PORT=9090
```

### Development Environment

```bash
# .env.dev
# Development-specific environment variables

MONGODB_URL=mongodb://localhost:27017/construction_specs
QDRANT_URL=http://localhost:6333

# Use local LLM for development
DEFAULT_LLM_PROVIDER=ollama
DEFAULT_MODEL=llama2

DEBUG=true
LOG_LEVEL=DEBUG
ENABLE_VERIFICATION=false
ENABLE_CACHING=false
DEBUG_MODE=true

# Sample data paths for testing
SAMPLE_DATA_PATH=./data/
SAMPLE_SPECIFICATION=./data/Spec 14 24 00 - Hydraulic Elevators.pdf
SAMPLE_DRAWINGS=./data/Architectural Drawings.pdf
SAMPLE_SUBMITTAL=./data/Submittal and Product Description.pdf
```

## Sample Data Integration

### Test Data Setup

The system includes sample construction documents in the `data/` folder for testing and development:

#### Available Sample Documents

1. **Specification Document**
   - **File**: `data/Spec 14 24 00 - Hydraulic Elevators.pdf`
   - **Type**: Construction specification (CSI Division 14 24 00)
   - **Pages**: 6 pages
   - **Format**: Bluebeam Revu x64, PDF 1.7
   - **Content**: Hydraulic elevator specifications with capacity, speed, and installation requirements

2. **Architectural Drawings**
   - **File**: `data/Architectural Drawings.pdf`
   - **Type**: Architectural drawing set
   - **Pages**: 8 pages
   - **Format**: PDF 1.4, large format (2160 x 3024 points)
   - **Content**: Floor plans with elevator locations, dimensions, and annotations

3. **Submittal Document**
   - **File**: `data/Submittal and Product Description.pdf`
   - **Type**: Contractor submittal
   - **Format**: Binary PDF with manufacturer data
   - **Content**: Product specifications and technical data sheets

### Sample Data Loading Script

```bash
#!/bin/bash
# scripts/load_sample_data.sh

echo "Loading sample construction documents..."

# Check if sample data exists
if [ ! -d "data" ]; then
    echo "Error: data/ directory not found"
    exit 1
fi

# Upload sample specification
echo "Uploading hydraulic elevator specification..."
curl -X POST "http://localhost:8000/documents/upload" \
  -F "file=@data/Spec 14 24 00 - Hydraulic Elevators.pdf" \
  -F "document_type=specification" \
  -F "metadata={\"csi_division\":\"14 24 00\",\"project_name\":\"Sample Project\"}"

# Upload sample drawings
echo "Uploading architectural drawings..."
curl -X POST "http://localhost:8000/documents/upload" \
  -F "file=@data/Architectural Drawings.pdf" \
  -F "document_type=drawing" \
  -F "metadata={\"csi_division\":\"14 24 00\",\"drawing_type\":\"floor_plan\"}"

# Upload sample submittal
echo "Uploading submittal document..."
curl -X POST "http://localhost:8000/documents/upload" \
  -F "file=@data/Submittal and Product Description.pdf" \
  -F "document_type=submittal" \
  -F "metadata={\"csi_division\":\"14 24 00\",\"manufacturer\":\"Sample Manufacturer\"}"

echo "Sample data loading completed!"
```

### Expected Processing Results

After processing the sample documents, the system should extract:

#### From Hydraulic Elevator Specification:
```json
{
  "document_id": "doc_spec_14_24_00_001",
  "facts_extracted": [
    {
      "topic": "hydraulic_elevator",
      "attribute": "capacity_lbs",
      "value": 2500,
      "unit": "lbs",
      "csi_division": "14 24 00"
    },
    {
      "topic": "hydraulic_elevator", 
      "attribute": "travel_speed_fpm",
      "value": 150,
      "unit": "fpm",
      "csi_division": "14 24 00"
    }
  ],
  "sections": ["Part 1 - General", "Part 2 - Products", "Part 3 - Execution"]
}
```

#### From Architectural Drawings:
```json
{
  "document_id": "doc_drawings_001",
  "page_count": 8,
  "page_rotation": 90,
  "media_box": {"width": 2160, "height": 3024},
  "annotation_count": 97,
  "xobject_count": 5,
  "csi_divisions": ["14 24 00"]
}
```

### Test Scenarios

#### 1. Document Upload Test
```bash
# Test uploading each sample document
python -m pytest tests/test_document_upload.py -v
```

#### 2. Fact Extraction Test
```bash
# Test fact extraction from elevator specification
python -m pytest tests/test_fact_extraction.py::test_elevator_facts -v
```

#### 3. Search Test
```bash
# Test CSI division search
python -m pytest tests/test_search.py::test_csi_search -v
```

#### 4. Document Comparison Test
```bash
# Test comparing specification with submittal
python -m pytest tests/test_comparison.py::test_elevator_comparison -v
```

## CLI Development Mode

### CLI Application Setup

```python
# src/cli.py
import asyncio
import typer
from typing import Optional, List
from pathlib import Path
import uvicorn
from .services import initialize_services
from .config import Settings

app = typer.Typer(help="Construction Spec Assistant CLI")

@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
    workers: int = typer.Option(1, help="Number of worker processes"),
    log_level: str = typer.Option("info", help="Log level")
):
    """Start the development server"""
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level=log_level
    )

@app.command()
async def process_document(
    file_path: Path = typer.Argument(..., help="Path to PDF file"),
    document_type: str = typer.Option("specification", help="Document type"),
    output_dir: Optional[Path] = typer.Option(None, help="Output directory")
):
    """Process a single document"""
    settings = Settings()
    services = await initialize_services(settings)
    
    try:
        typer.echo(f"Processing document: {file_path}")
        
        # Upload document
        with open(file_path, "rb") as f:
            document_id = await services.document_manager.upload_document(
                file=f,
                filename=file_path.name,
                document_type=document_type
            )
        
        typer.echo(f"Document uploaded with ID: {document_id}")
        
        # Process document
        await services.document_manager.process_document(document_id)
        
        typer.echo("Document processing completed")
        
        # Get results
        document = await services.document_manager.get_document(document_id)
        typer.echo(f"Document status: {document.status}")
        
        if output_dir:
            # Export results
            await export_document_results(services, document_id, output_dir)
            typer.echo(f"Results exported to: {output_dir}")
        
    except Exception as e:
        typer.echo(f"Error processing document: {e}", err=True)
    finally:
        await services.cleanup()

@app.command()
async def compare_documents(
    spec_file: Path = typer.Argument(..., help="Path to specification PDF"),
    submittal_file: Path = typer.Argument(..., help="Path to submittal PDF"),
    output_file: Optional[Path] = typer.Option(None, help="Output file for results"),
    review_scope: Optional[List[str]] = typer.Option(None, help="CSI divisions to review")
):
    """Compare two documents"""
    settings = Settings()
    services = await initialize_services(settings)
    
    try:
        typer.echo("Processing documents...")
        
        # Upload and process specification
        with open(spec_file, "rb") as f:
            spec_id = await services.document_manager.upload_document(
                file=f,
                filename=spec_file.name,
                document_type="specification"
            )
        
        # Upload and process submittal
        with open(submittal_file, "rb") as f:
            submittal_id = await services.document_manager.upload_document(
                file=f,
                filename=submittal_file.name,
                document_type="submittal"
            )
        
        # Wait for processing
        await wait_for_document_processing(services, spec_id)
        await wait_for_document_processing(services, submittal_id)
        
        typer.echo("Starting document comparison...")
        
        # Create review
        review_id = await services.review_manager.create_review({
            "specification_document_id": spec_id,
            "submittal_document_id": submittal_id,
            "review_scope": review_scope or []
        })
        
        # Process review
        review_result = await services.review_manager.process_review(review_id)
        
        typer.echo(f"Review completed: {review_result.status}")
        
        if output_file:
            # Export results
            await export_review_results(review_result, output_file)
            typer.echo(f"Results exported to: {output_file}")
        else:
            # Print summary
            print_review_summary(review_result)
        
    except Exception as e:
        typer.echo(f"Error comparing documents: {e}", err=True)
    finally:
        await services.cleanup()

@app.command()
async def search(
    query: str = typer.Argument(..., help="Search query"),
    document_types: Optional[List[str]] = typer.Option(None, help="Document types to search"),
    limit: int = typer.Option(10, help="Maximum number of results")
):
    """Search documents"""
    settings = Settings()
    services = await initialize_services(settings)
    
    try:
        typer.echo(f"Searching for: {query}")
        
        results = await services.search_engine.search(
            query=query,
            document_types=document_types,
            limit=limit
        )
        
        typer.echo(f"Found {len(results)} results:")
        
        for i, result in enumerate(results, 1):
            typer.echo(f"\n{i}. {result['title'] or 'Untitled'}")
            typer.echo(f"   Document: {result['document_id']}")
            typer.echo(f"   Page: {result['page_number']}")
            typer.echo(f"   Score: {result['combined_score']:.3f}")
            typer.echo(f"   Text: {result['text'][:200]}...")
        
    except Exception as e:
        typer.echo(f"Error searching: {e}", err=True)
    finally:
        await services.cleanup()

@app.command()
def health():
    """Check system health"""
    typer.echo("Checking system health...")
    
    # Check MongoDB
    try:
        import pymongo
        client = pymongo.MongoClient(settings.mongodb_url)
        client.admin.command('ping')
        typer.echo("✓ MongoDB: Healthy")
    except Exception as e:
        typer.echo(f"✗ MongoDB: {e}")
    
    # Check Qdrant
    try:
        import requests
        response = requests.get(f"{settings.qdrant_url}/health")
        if response.status_code == 200:
            typer.echo("✓ Qdrant: Healthy")
        else:
            typer.echo("✗ Qdrant: Unhealthy")
    except Exception as e:
        typer.echo(f"✗ Qdrant: {e}")
    
    # Check LLM providers
    try:
        # This would need to be implemented in the services
        typer.echo("✓ LLM Providers: Check not implemented")
    except Exception as e:
        typer.echo(f"✗ LLM Providers: {e}")

# Helper functions
async def wait_for_document_processing(services, document_id: str, timeout: int = 300):
    """Wait for document processing to complete"""
    import time
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        document = await services.document_manager.get_document(document_id)
        if document.status in ["indexed", "failed"]:
            break
        await asyncio.sleep(5)
    else:
        raise TimeoutError(f"Document processing timeout for {document_id}")

async def export_document_results(services, document_id: str, output_dir: Path):
    """Export document processing results"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get document data
    document = await services.document_manager.get_document(document_id)
    passages = await services.document_manager.get_document_passages(document_id)
    
    # Export to JSON
    import json
    results = {
        "document": document.dict(),
        "passages": [passage.dict() for passage in passages]
    }
    
    output_file = output_dir / f"{document_id}_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

async def export_review_results(review_result, output_file: Path):
    """Export review results to file"""
    import json
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(review_result.dict(), f, indent=2, default=str)

def print_review_summary(review_result):
    """Print review summary to console"""
    typer.echo(f"\nReview Summary:")
    typer.echo(f"Status: {review_result.status}")
    typer.echo(f"Findings: {len(review_result.findings)}")
    typer.echo(f"Confidence: {review_result.confidence_score:.2f}")
    
    if review_result.summary:
        typer.echo(f"\nSummary:\n{review_result.summary}")
    
    if review_result.findings:
        typer.echo(f"\nFindings:")
        for i, finding in enumerate(review_result.findings, 1):
            typer.echo(f"{i}. {finding.title} ({finding.finding_type})")
            typer.echo(f"   Confidence: {finding.confidence:.2f}")
            if finding.recommendation:
                typer.echo(f"   Recommendation: {finding.recommendation}")

if __name__ == "__main__":
    app()
```

### CLI Entry Point

```python
# src/__main__.py
import asyncio
from .cli import app

if __name__ == "__main__":
    # Handle async commands
    try:
        app()
    except Exception as e:
        print(f"Error: {e}")
```

## Deployment Scripts

### Startup Scripts

```bash
#!/bin/bash
# scripts/start.sh

set -e

echo "Starting Construction Spec Assistant..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

# Load environment variables
source .env

# Start services
echo "Starting services with docker-compose..."
docker-compose up -d

# Wait for services to be healthy
echo "Waiting for services to be healthy..."
sleep 30

# Check health
echo "Checking service health..."
curl -f http://localhost:8000/health || {
    echo "Error: API health check failed"
    exit 1
}

echo "Construction Spec Assistant started successfully!"
echo "API available at: http://localhost:8000"
echo "API documentation at: http://localhost:8000/docs"
```

### Development Script

```bash
#!/bin/bash
# scripts/dev.sh

set -e

echo "Starting Construction Spec Assistant in development mode..."

# Check if .env.dev file exists
if [ ! -f .env.dev ]; then
    echo "Error: .env.dev file not found. Please copy .env.example to .env.dev and configure it."
    exit 1
fi

# Load environment variables
source .env.dev

# Start development services
echo "Starting development services..."
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d mongodb qdrant

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Start API in development mode
echo "Starting API in development mode..."
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### Production Script

```bash
#!/bin/bash
# scripts/prod.sh

set -e

echo "Starting Construction Spec Assistant in production mode..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

# Load environment variables
source .env

# Build production images
echo "Building production images..."
docker-compose build --no-cache

# Start production services
echo "Starting production services..."
docker-compose --profile production up -d

# Wait for services to be healthy
echo "Waiting for services to be healthy..."
sleep 60

# Check health
echo "Checking service health..."
curl -f http://localhost:8000/health || {
    echo "Error: API health check failed"
    exit 1
}

echo "Construction Spec Assistant started successfully in production mode!"
echo "API available at: http://localhost:8000"
echo "API documentation at: http://localhost:8000/docs"
```

### Stop Script

```bash
#!/bin/bash
# scripts/stop.sh

echo "Stopping Construction Spec Assistant..."

# Stop all services
docker-compose down

# Optionally remove volumes (uncomment if needed)
# docker-compose down -v

echo "Construction Spec Assistant stopped."
```

## Nginx Configuration

### Production Nginx Config

```nginx
# nginx/nginx.conf
events {
    worker_connections 1024;
}

http {
    upstream api {
        server api:8000;
    }

    server {
        listen 80;
        server_name localhost;

        # Redirect HTTP to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name localhost;

        # SSL Configuration
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;

        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        # Client max body size (for file uploads)
        client_max_body_size 100M;

        # API proxy
        location / {
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # WebSocket support
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            
            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # Health check endpoint
        location /health {
            proxy_pass http://api/health;
            access_log off;
        }
    }
}
```

## Monitoring and Logging

### Logging Configuration

```python
# src/logging_config.py
import structlog
import logging
from pathlib import Path

def configure_logging(log_level: str = "INFO", log_file: Path = None):
    """Configure structured logging"""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=None if log_file else None,
        filename=log_file,
        level=getattr(logging, log_level.upper()),
    )
    
    return structlog.get_logger()
```

### Health Check Script

```python
# scripts/health_check.py
import asyncio
import aiohttp
import sys
from typing import Dict, Any

async def check_health() -> Dict[str, Any]:
    """Check system health"""
    results = {}
    
    # Check API health
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8000/health") as response:
                if response.status == 200:
                    results["api"] = await response.json()
                else:
                    results["api"] = {"status": "unhealthy", "error": f"HTTP {response.status}"}
    except Exception as e:
        results["api"] = {"status": "unhealthy", "error": str(e)}
    
    return results

if __name__ == "__main__":
    results = asyncio.run(check_health())
    
    if results["api"]["status"] == "healthy":
        print("✓ System is healthy")
        sys.exit(0)
    else:
        print("✗ System is unhealthy")
        print(results)
        sys.exit(1)
```

This deployment specification provides a complete setup for running the Architectural Submittal Reviewer system in both development and production environments with Docker, including CLI tools for local development and debugging.
