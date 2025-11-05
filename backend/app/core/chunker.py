"""
Intelligent text chunker with token-aware splitting.

This module provides chunking functionality that respects:
- Token limits (using tiktoken)
- Sentence boundaries (semantic coherence)
- Section context (preserves hierarchy)
- Overlap between chunks (for better retrieval)
- Table preservation (using Docling's HybridChunker)
"""

import re
import hashlib
from typing import List, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field

from app.core.sectionizer import Section
from app.utils.token_counter import count_tokens, split_text_by_tokens
from app.utils.logging import get_logger

# Docling imports for HybridChunker
import tiktoken
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
from docling.chunking import HybridChunker
from docling_core.transforms.chunker.hierarchical_chunker import (
    ChunkingDocSerializer,
    ChunkingSerializerProvider,
)
from docling_core.transforms.serializer.markdown import MarkdownTableSerializer

if TYPE_CHECKING:
    from docling_core.types.doc import DoclingDocument

logger = get_logger(__name__)


class SectionChunk(BaseModel):
    """Chunk of text from a document section."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    section_title: str = Field(..., description="Parent section title")
    section_number: Optional[str] = Field(None, description="Section number")
    section_level: int = Field(..., description="Section level")
    content: str = Field(..., description="Chunk content")
    token_count: int = Field(..., description="Number of tokens in chunk")
    chunk_index: int = Field(..., description="Index of chunk within section")
    total_chunks: int = Field(..., description="Total chunks in section")


def _split_by_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    sentence_pattern = r"(?<=[.!?])\s+"
    sentences = re.split(sentence_pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def _chunk_text(
    text: str, max_tokens: int = 500, overlap_tokens: int = 50, model: str = "gpt-4"
) -> List[str]:
    """
    Split text into chunks respecting token limits and sentence boundaries.

    Args:
        text: Text to chunk
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Tokens to overlap between chunks
        model: Model for token counting

    Returns:
        List of text chunks
    """
    if not text:
        return []

    # Check if text fits in one chunk
    if count_tokens(text, model) <= max_tokens:
        return [text]

    # Split by sentences
    sentences = _split_by_sentences(text)

    chunks = []
    current_chunk = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = count_tokens(sentence, model)

        # If single sentence exceeds max_tokens, split by tokens
        if sentence_tokens > max_tokens:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_tokens = 0

            # Split long sentence by tokens
            token_chunks = split_text_by_tokens(sentence, max_tokens, model, overlap_tokens)
            chunks.extend(token_chunks)
            continue

        # Check if adding sentence would exceed limit
        if current_tokens + sentence_tokens > max_tokens:
            if current_chunk:
                chunks.append(" ".join(current_chunk))

            # Start new chunk with overlap
            if overlap_tokens > 0 and current_chunk:
                overlap_sentences = []
                overlap_token_count = 0
                for s in reversed(current_chunk):
                    s_tokens = count_tokens(s, model)
                    if overlap_token_count + s_tokens <= overlap_tokens:
                        overlap_sentences.insert(0, s)
                        overlap_token_count += s_tokens
                    else:
                        break
                current_chunk = overlap_sentences
                current_tokens = overlap_token_count
            else:
                current_chunk = []
                current_tokens = 0

        current_chunk.append(sentence)
        current_tokens += sentence_tokens

    # Add final chunk
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def generate_chunk_id(section_title: str, chunk_index: int, content: str) -> str:
    """Generate unique chunk ID."""
    content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
    return f"{section_title.replace(' ', '_')}_{chunk_index}_{content_hash}"


def chunk_section(
    section: Section, max_tokens: int = 500, overlap_tokens: int = 50, model: str = "gpt-4"
) -> List[SectionChunk]:
    """
    Chunk a single section's content.

    Args:
        section: Section to chunk
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Tokens to overlap between chunks
        model: Model for token counting

    Returns:
        List of section chunks
    """
    if not section.content:
        return []

    text_chunks = _chunk_text(section.content, max_tokens, overlap_tokens, model)

    section_chunks = []
    for idx, chunk_text in enumerate(text_chunks):
        chunk = SectionChunk(
            chunk_id=generate_chunk_id(section.title, idx, chunk_text),
            section_title=section.title,
            section_number=section.section_number,
            section_level=section.level,
            content=chunk_text,
            token_count=count_tokens(chunk_text, model),
            chunk_index=idx,
            total_chunks=len(text_chunks),
        )
        section_chunks.append(chunk)

    return section_chunks


def chunk_sections(
    sections: List[Section], max_tokens: int = 500, overlap_tokens: int = 50, model: str = "gpt-4"
) -> List[SectionChunk]:
    """
    Recursively chunk all sections and subsections.

    Args:
        sections: List of sections to chunk
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Tokens to overlap between chunks
        model: Model for token counting

    Returns:
        List of all chunks from all sections
    """
    all_chunks = []

    def _chunk_recursive(section: Section):
        # Chunk current section
        section_chunks = chunk_section(section, max_tokens, overlap_tokens, model)
        all_chunks.extend(section_chunks)

        # Recursively chunk subsections
        for subsection in section.subsections:
            _chunk_recursive(subsection)

    for section in sections:
        _chunk_recursive(section)

    logger.info(f"Created {len(all_chunks)} chunks from {len(sections)} sections")
    return all_chunks


def get_chunk_statistics(chunks: List[SectionChunk]) -> dict:
    """Get statistics about chunks."""
    if not chunks:
        return {
            "total_chunks": 0,
            "total_tokens": 0,
            "avg_tokens": 0,
            "min_tokens": 0,
            "max_tokens": 0,
        }

    token_counts = [chunk.token_count for chunk in chunks]

    return {
        "total_chunks": len(chunks),
        "total_tokens": sum(token_counts),
        "avg_tokens": sum(token_counts) / len(token_counts),
        "min_tokens": min(token_counts),
        "max_tokens": max(token_counts),
    }


def simple_chunk_markdown(
    markdown_text: str, max_tokens: int = 500, overlap_tokens: int = 50, model: str = "gpt-4"
) -> List[SectionChunk]:
    """
    Simple chunking for non-CSI documents (submittals, product descriptions, drawings).

    This function does NOT apply CSI hierarchical structure parsing.
    It simply splits the markdown text into chunks based on:
    - Paragraph boundaries (double newlines)
    - Token limits
    - Sentence boundaries
    - Overlap between chunks

    Args:
        markdown_text: Raw markdown text to chunk
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Tokens to overlap between chunks
        model: Model for token counting

    Returns:
        List of SectionChunk objects (with generic section info)
    """
    if not markdown_text or not markdown_text.strip():
        logger.warning("Empty markdown text provided for simple chunking")
        return []

    logger.info(f"Simple chunking markdown text ({count_tokens(markdown_text, model)} tokens)")

    # Split by paragraphs first (double newlines)
    paragraphs = [p.strip() for p in markdown_text.split("\n\n") if p.strip()]

    # Combine paragraphs into chunks respecting token limits
    chunks = []
    current_chunk_text = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = count_tokens(para, model)

        # If single paragraph exceeds max_tokens, split it by sentences
        if para_tokens > max_tokens:
            if current_chunk_text:
                # Save current chunk
                chunks.append("\n\n".join(current_chunk_text))
                current_chunk_text = []
                current_tokens = 0

            # Split long paragraph by sentences and tokens
            para_chunks = _chunk_text(para, max_tokens, overlap_tokens, model)
            chunks.extend(para_chunks)
            continue

        # Check if adding paragraph would exceed limit
        if current_tokens + para_tokens > max_tokens:
            if current_chunk_text:
                chunks.append("\n\n".join(current_chunk_text))

            # Start new chunk with overlap
            if overlap_tokens > 0 and current_chunk_text:
                overlap_paras = []
                overlap_token_count = 0
                for p in reversed(current_chunk_text):
                    p_tokens = count_tokens(p, model)
                    if overlap_token_count + p_tokens <= overlap_tokens:
                        overlap_paras.insert(0, p)
                        overlap_token_count += p_tokens
                    else:
                        break
                current_chunk_text = overlap_paras
                current_tokens = overlap_token_count
            else:
                current_chunk_text = []
                current_tokens = 0

        current_chunk_text.append(para)
        current_tokens += para_tokens

    # Add remaining text
    if current_chunk_text:
        chunks.append("\n\n".join(current_chunk_text))

    # Convert to SectionChunk objects
    section_chunks = []
    for idx, chunk_text in enumerate(chunks):
        chunk_id = hashlib.md5(f"{chunk_text}_{idx}".encode()).hexdigest()[:12]

        section_chunks.append(
            SectionChunk(
                chunk_id=chunk_id,
                section_title="Document Content",  # Generic title for non-CSI docs
                section_number=None,
                section_level=0,  # Flat structure
                content=chunk_text,
                token_count=count_tokens(chunk_text, model),
                chunk_index=idx,
                total_chunks=len(chunks),
            )
        )

    logger.info(f"Created {len(section_chunks)} simple chunks")
    return section_chunks


# ============================================================================
# HybridChunker Support (for submittal documents with tables)
# ============================================================================


class MDTableSerializerProvider(ChunkingSerializerProvider):
    """
    Custom serializer provider that uses MarkdownTableSerializer.

    This ensures tables are serialized to Markdown format instead of
    the default triplet notation, preserving table structure for better
    readability and LLM processing.
    """

    def get_serializer(self, doc: "DoclingDocument"):
        """Get serializer with Markdown table support."""
        return ChunkingDocSerializer(doc=doc, table_serializer=MarkdownTableSerializer())


def hybrid_chunk_document(
    docling_doc: "DoclingDocument",
    max_tokens: int = 512,
    merge_peers: bool = True,
    model: str = "gpt-4o",
) -> List[SectionChunk]:
    """
    Chunk a Docling document using HybridChunker with table preservation.

    This function uses Docling's HybridChunker which:
    - Preserves table structure in Markdown format
    - Respects document hierarchy
    - Handles complex layouts intelligently
    - Merges peer sections when beneficial

    Args:
        docling_doc: Docling DoclingDocument object
        max_tokens: Maximum tokens per chunk
        merge_peers: Whether to merge peer sections
        model: Model for token counting (default: gpt-4o)

    Returns:
        List of SectionChunk objects with preserved table structure

    Note:
        This is the preferred chunking method for submittal documents
        and product descriptions that contain tables.
    """
    logger.info(f"Hybrid chunking document with max_tokens={max_tokens}, merge_peers={merge_peers}")

    # Create OpenAI tokenizer
    tokenizer = OpenAITokenizer(
        tokenizer=tiktoken.encoding_for_model(model),
        max_tokens=128 * 1024,  # context window length required for OpenAI tokenizers
    )

    # Create HybridChunker with Markdown table serializer
    chunker = HybridChunker(
        tokenizer=tokenizer,
        max_tokens=max_tokens,
        merge_peers=merge_peers,
        serializer_provider=MDTableSerializerProvider(),
    )

    # Chunk the document
    chunk_iter = chunker.chunk(dl_doc=docling_doc)
    docling_chunks = list(chunk_iter)

    logger.info(f"HybridChunker produced {len(docling_chunks)} chunks")

    # Convert Docling chunks to SectionChunk objects
    section_chunks = []
    for idx, docling_chunk in enumerate(docling_chunks):
        # Extract chunk text
        chunk_text = docling_chunk.text

        # Generate chunk ID
        chunk_id = hashlib.md5(f"{chunk_text}_{idx}".encode()).hexdigest()[:12]

        # Extract metadata if available
        # Docling chunks have meta attribute with path information
        section_title = "Document Content"
        if hasattr(docling_chunk, "meta") and docling_chunk.meta:
            # Try to get heading path from metadata
            if hasattr(docling_chunk.meta, "headings") and docling_chunk.meta.headings:
                section_title = " > ".join(docling_chunk.meta.headings)
            elif hasattr(docling_chunk.meta, "doc_items") and docling_chunk.meta.doc_items:
                # Use first doc item as title
                first_item = docling_chunk.meta.doc_items[0]
                if hasattr(first_item, "label"):
                    section_title = first_item.label

        section_chunks.append(
            SectionChunk(
                chunk_id=chunk_id,
                section_title=section_title,
                section_number=None,
                section_level=0,  # Flat structure for hybrid chunks
                content=chunk_text,
                token_count=count_tokens(chunk_text, model),
                chunk_index=idx,
                total_chunks=len(docling_chunks),
            )
        )

    logger.info(f"Created {len(section_chunks)} hybrid chunks with table preservation")
    return section_chunks
