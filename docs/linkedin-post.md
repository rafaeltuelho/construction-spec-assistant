# Construction Spec Assistant - Project Summary

This is an **agentic AI system** designed to help Construction Architects and Engineers reviewing construction documents and identify inconsistencies between original specifications/drawings and contractor submittal documents.

## Key Features
- **Document Processing**: PDF parsing using Docling with OCR support
- **Fact Extraction**: LLM-based extraction of structured facts from specifications
- **Vector Search**: Hybrid dense + sparse (BM25) search with in-memory Qdrant
- **Agentic Workflows**: LangGraph-powered multi-step comparison workflows
- **Multi-LLM Support**: OpenAI, Anthropic, and Ollama integration

## Architecture
- **Backend**: Python FastAPI with automatic OpenAPI docs
- **Frontend**: React + TypeScript + Vite with Tailwind UI
- **Storage**: MongoDB for facts/metadata, Qdrant for vectors
- **Processing**: Docling for PDF extraction
- **AI Workflows**: LangChain/LangGraph
- **Observability**: LangSmith for tracing and monitoring

## Workflow
1. Upload construction PDFs (specs, drawings, submittals)
2. Parse and extract structured "facts" with normalized units
3. Index content for hybrid search
4. AI agents compare specifications against submittals
5. Generate structured findings with citations
6. Human review with accept/reject feedback

The system transforms unstructured construction documents into searchable, comparable data to automate the tedious process of submittal review for architects.
