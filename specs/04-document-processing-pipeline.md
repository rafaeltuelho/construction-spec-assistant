# Document Processing Pipeline Specification

## Purpose

This document specifies the implementation details for the document processing pipeline, including Docling integration, CSI-aware sectionization, and intelligent chunking.

## Pipeline Overview

```
┌──────────────┐
│  PDF Upload  │
└──────┬───────┘
       │
       ▼
┌──────────────────────┐
│  Docling Parsing     │
│  (with OCR)          │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Markdown Output     │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  CSI Sectionization  │
│  (Hierarchical)      │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Intelligent         │
│  Chunking            │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Storage             │
│  (MongoDB + Qdrant)  │
└──────────────────────┘
```

---

## 1. Docling Integration

### Module: `backend/app/core/docling_parser.py`

### Notebook Reference
- **Lines**: 449-615
- **Key Functions**: `create_docling_config()`, `parse_document_with_docling()`

### Implementation

#### Configuration

```python
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.backend.docling_parse_backend import DoclingParseDocumentBackend

def create_docling_config(
    use_ocr: bool = True,
    ocr_engine: str = "easyocr"
) -> DocumentConverter:
    """
    Create Docling document converter with OCR configuration.
    
    Args:
        use_ocr: Enable OCR for scanned documents
        ocr_engine: OCR engine to use ("easyocr" or "tesseract")
    
    Returns:
        Configured DocumentConverter instance
    """
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = use_ocr
    pipeline_options.ocr_options.engine = ocr_engine
    
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: pipeline_options
        }
    )
    
    return converter
```

#### Document Parsing

```python
from pathlib import Path
from typing import Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)

async def parse_document_with_docling(
    file_path: str,
    use_ocr: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """
    Parse PDF document to markdown using Docling.
    
    Args:
        file_path: Path to PDF file
        use_ocr: Enable OCR for scanned documents
    
    Returns:
        Tuple of (markdown_content, metadata)
    
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is not a valid PDF
        RuntimeError: If parsing fails
    """
    try:
        # Validate file exists
        pdf_path = Path(file_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not pdf_path.suffix.lower() == '.pdf':
            raise ValueError(f"File must be PDF, got: {pdf_path.suffix}")
        
        # Create converter
        converter = create_docling_config(use_ocr=use_ocr)
        
        # Parse document
        logger.info(f"Parsing document: {file_path} (OCR: {use_ocr})")
        result = converter.convert(file_path)
        
        # Extract markdown
        markdown = result.document.export_to_markdown()
        
        # Extract metadata
        metadata = {
            "page_count": len(result.document.pages),
            "title": result.document.name,
            "ocr_used": use_ocr,
            "file_size_bytes": pdf_path.stat().st_size,
        }
        
        logger.info(f"Successfully parsed document: {metadata['page_count']} pages")
        
        return markdown, metadata
        
    except Exception as e:
        logger.error(f"Failed to parse document {file_path}: {str(e)}")
        raise RuntimeError(f"Document parsing failed: {str(e)}") from e
```

### Error Handling

- **FileNotFoundError**: File doesn't exist
- **ValueError**: Invalid file type
- **RuntimeError**: Docling parsing failure
- **OCR Errors**: Log warning and retry without OCR

---

## 2. CSI-Aware Sectionization

### Module: `backend/app/core/sectionizer.py`

### Notebook Reference
- **Lines**: 186-431
- **Key Functions**: `sectionize_markdown()`

### CSI Format Understanding

Construction Specifications Institute (CSI) documents follow a hierarchical structure:

```
PART 1 - GENERAL
  1.1 SUMMARY
    A. Section Includes
    B. Related Requirements
  1.2 REFERENCES
    A. Standards
    
PART 2 - PRODUCTS
  2.1 MANUFACTURERS
    A. Acceptable Manufacturers
  2.2 MATERIALS
    A. Material Specifications
```

### Implementation

```python
from typing import List
from pydantic import BaseModel
import re
import logging

logger = logging.getLogger(__name__)

class Section(BaseModel):
    """Hierarchical document section."""
    level: int
    title: str
    content: str
    children: List['Section'] = []
    
    class Config:
        # Allow recursive model
        arbitrary_types_allowed = True

def sectionize_markdown(markdown: str) -> List[Section]:
    """
    Parse markdown into hierarchical CSI-aware sections.
    
    Args:
        markdown: Markdown content from Docling
    
    Returns:
        List of top-level Section objects with nested children
    
    CSI Hierarchy:
        Level 1: PART X - TITLE (e.g., "PART 1 - GENERAL")
        Level 2: X.X TITLE (e.g., "1.1 SUMMARY")
        Level 3: A. Title (e.g., "A. Section Includes")
        Level 4: 1. Title (e.g., "1. Item description")
        Level 5: a. Title (e.g., "a. Sub-item")
    """
    lines = markdown.split('\n')
    sections = []
    current_stack = []  # Stack to track current section hierarchy
    
    # Regex patterns for CSI sections
    patterns = {
        1: re.compile(r'^#+\s*PART\s+\d+\s*-\s*(.+)$', re.IGNORECASE),
        2: re.compile(r'^#+\s*(\d+\.\d+)\s+(.+)$'),
        3: re.compile(r'^#+\s*([A-Z])\.\s+(.+)$'),
        4: re.compile(r'^#+\s*(\d+)\.\s+(.+)$'),
        5: re.compile(r'^#+\s*([a-z])\.\s+(.+)$'),
    }
    
    current_content = []
    
    for line in lines:
        # Check if line matches any section pattern
        matched = False
        for level, pattern in patterns.items():
            match = pattern.match(line)
            if match:
                # Save previous section's content
                if current_stack:
                    current_stack[-1].content = '\n'.join(current_content).strip()
                    current_content = []
                
                # Create new section
                title = match.group(1) if level == 1 else match.group(2)
                section = Section(
                    level=level,
                    title=title.strip(),
                    content="",
                    children=[]
                )
                
                # Add to hierarchy
                while current_stack and current_stack[-1].level >= level:
                    current_stack.pop()
                
                if current_stack:
                    current_stack[-1].children.append(section)
                else:
                    sections.append(section)
                
                current_stack.append(section)
                matched = True
                break
        
        if not matched:
            # Add line to current section's content
            current_content.append(line)
    
    # Save final section's content
    if current_stack:
        current_stack[-1].content = '\n'.join(current_content).strip()
    
    logger.info(f"Sectionized document into {len(sections)} top-level sections")
    
    return sections
```

### Section Validation

```python
def validate_sections(sections: List[Section]) -> bool:
    """
    Validate section hierarchy and structure.
    
    Args:
        sections: List of sections to validate
    
    Returns:
        True if valid, raises ValueError otherwise
    """
    def validate_recursive(section: Section, parent_level: int = 0):
        if section.level <= parent_level:
            raise ValueError(
                f"Invalid section hierarchy: level {section.level} "
                f"under parent level {parent_level}"
            )
        for child in section.children:
            validate_recursive(child, section.level)
    
    for section in sections:
        validate_recursive(section)
    
    return True
```

---

## 3. Intelligent Chunking

### Module: `backend/app/core/chunker.py`

### Notebook Reference
- **Lines**: 186-431
- **Key Functions**: `chunk_sections()`

### Chunking Strategy

**Goals**:
1. Respect token limits for LLM context windows
2. Maintain semantic coherence (don't split mid-sentence)
3. Preserve section context in each chunk
4. Add overlap between chunks for continuity

### Implementation

```python
from typing import List
from pydantic import BaseModel
from app.core.token_counter import count_tokens
import logging

logger = logging.getLogger(__name__)

class SectionChunk(BaseModel):
    """Document chunk with section context."""
    chunk_id: str
    section_path: str  # e.g., "PART 1 - GENERAL > 1.1 SUMMARY > A. Section Includes"
    content: str
    chunk_index: int
    token_count: int
    section_level: int

def chunk_sections(
    sections: List[Section],
    max_tokens: int = 500,
    overlap_tokens: int = 50,
    model: str = "gpt-4"
) -> List[SectionChunk]:
    """
    Chunk sections into token-limited pieces with overlap.
    
    Args:
        sections: List of sections to chunk
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Overlap between consecutive chunks
        model: Model name for token counting
    
    Returns:
        List of SectionChunk objects
    """
    chunks = []
    chunk_counter = 0
    
    def chunk_section_recursive(
        section: Section,
        path: str = ""
    ):
        nonlocal chunk_counter
        
        # Build section path
        current_path = f"{path} > {section.title}" if path else section.title
        
        # Chunk this section's content
        if section.content:
            content_chunks = _chunk_text(
                text=section.content,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens,
                model=model
            )
            
            for idx, chunk_text in enumerate(content_chunks):
                chunk = SectionChunk(
                    chunk_id=f"chunk_{chunk_counter:06d}",
                    section_path=current_path,
                    content=chunk_text,
                    chunk_index=idx,
                    token_count=count_tokens(chunk_text, model),
                    section_level=section.level
                )
                chunks.append(chunk)
                chunk_counter += 1
        
        # Recursively chunk children
        for child in section.children:
            chunk_section_recursive(child, current_path)
    
    for section in sections:
        chunk_section_recursive(section)
    
    logger.info(f"Created {len(chunks)} chunks from {len(sections)} sections")
    
    return chunks

def _chunk_text(
    text: str,
    max_tokens: int,
    overlap_tokens: int,
    model: str
) -> List[str]:
    """
    Split text into chunks with overlap.
    
    Strategy:
    1. Split by sentences
    2. Accumulate sentences until max_tokens
    3. Add overlap from previous chunk
    """
    # Split into sentences (simple approach)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = []
    current_tokens = 0
    overlap_sentences = []
    
    for sentence in sentences:
        sentence_tokens = count_tokens(sentence, model)
        
        if current_tokens + sentence_tokens > max_tokens and current_chunk:
            # Save current chunk
            chunk_text = ' '.join(current_chunk)
            chunks.append(chunk_text)
            
            # Start new chunk with overlap
            overlap_text = ' '.join(overlap_sentences)
            overlap_token_count = count_tokens(overlap_text, model)
            
            current_chunk = overlap_sentences.copy()
            current_tokens = overlap_token_count
            overlap_sentences = []
        
        current_chunk.append(sentence)
        current_tokens += sentence_tokens
        
        # Track sentences for overlap
        overlap_sentences.append(sentence)
        overlap_text = ' '.join(overlap_sentences)
        if count_tokens(overlap_text, model) > overlap_tokens:
            overlap_sentences.pop(0)
    
    # Add final chunk
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks
```

---

## 4. Storage

### MongoDB Storage

Store sections and chunks in MongoDB for retrieval and management.

```python
# In backend/app/db/mongodb.py

async def store_document_sections(
    document_id: str,
    sections: List[Section]
) -> None:
    """Store document sections in MongoDB."""
    collection = db["document_sections"]
    
    await collection.insert_one({
        "document_id": document_id,
        "sections": [s.dict() for s in sections],
        "created_at": datetime.utcnow()
    })

async def store_document_chunks(
    document_id: str,
    chunks: List[SectionChunk]
) -> None:
    """Store document chunks in MongoDB."""
    collection = db["document_chunks"]
    
    documents = [
        {
            **chunk.dict(),
            "document_id": document_id,
            "created_at": datetime.utcnow()
        }
        for chunk in chunks
    ]
    
    await collection.insert_many(documents)
```

### Qdrant Indexing

Index chunks in Qdrant for vector search.

```python
# In backend/app/db/qdrant.py

async def index_chunks_in_qdrant(
    document_id: str,
    chunks: List[SectionChunk],
    collection_name: str = "construction_docs"
) -> None:
    """Index chunks in Qdrant vector store."""
    from qdrant_client.models import PointStruct
    from fastembed import TextEmbedding
    
    # Generate embeddings
    embedding_model = TextEmbedding()
    texts = [chunk.content for chunk in chunks]
    embeddings = list(embedding_model.embed(texts))
    
    # Create points
    points = [
        PointStruct(
            id=chunk.chunk_id,
            vector=embedding,
            payload={
                "document_id": document_id,
                "section_path": chunk.section_path,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content
            }
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]
    
    # Upload to Qdrant
    client = await get_qdrant_client()
    await client.upsert(
        collection_name=collection_name,
        points=points
    )
```

---

## Next Steps

Refer to the following specification documents:

1. **05-fact-extraction.md**: Fact extraction from chunks
2. **06-rag-and-agents.md**: RAG retrieval and comparison agents

