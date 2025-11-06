# LinkedIn Post

📐👷🏻‍♀️ 🚀 I'm excited to announce the launch of my latest project, an AI-powered assistant for reviewing construction specifications and submittals. 

For the past few weeks I haven been part of the AI Engineer Bootcamp - Cohort 08 at @AI Markerspace and I have been working on this project as my final certification challenge. In this project I was able to apply all the knowledge I have acquired during the bootcamp and build a end-to-end Agentic RAG Prototype.

This is an **agentic AI system** designed to help Construction Architects and Engineers reviewing construction documents and identify inconsistencies between original specifications/drawings and contractor submittal documents.

## The Problem
👨🏻‍💻 Construction Documents review is a tedious and time-consuming task that can take many hours or days to complete, depending on the complexity of the project and the number of documents involved. Architect spend a lot of time in front of their computer screens comparing complex documents full of heavy technical terminology and CAD drawings in search for inconsistencies and discrepancies. 

## The Solution
🤖 Enters The Constructions Spec Assistant! 🤖 
aAn AI-powered assistant for reviewing construction specifications and submittals. 
The system transforms unstructured construction documents into searchable, comparable data to automate the tedious process of submittal review for Architects.

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

</> Check out the project at https://github.com/rafaeltuelho/construction-spec-assistant
🎥 Check out a 5 min demo at https://www.loom.com/share/0ec858d262e34dd48b9a9cd644980e88

#Construction #Architecture #AI #Automation