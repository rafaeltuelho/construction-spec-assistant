"""
Intelligent text chunker with token-aware splitting.

This module provides chunking functionality that respects:
- Token limits (using tiktoken)
- Sentence boundaries (semantic coherence)
- Section context (preserves hierarchy)
- Overlap between chunks (for better retrieval)
"""

import re
import hashlib
from typing import List, Optional
from pydantic import BaseModel, Field

from app.core.sectionizer import Section
from app.utils.token_counter import count_tokens, split_text_by_tokens
from app.utils.logging import get_logger

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
    sentence_pattern = r'(?<=[.!?])\s+'
    sentences = re.split(sentence_pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def _chunk_text(
    text: str,
    max_tokens: int = 500,
    overlap_tokens: int = 50,
    model: str = "gpt-4"
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
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_tokens = 0
            
            # Split long sentence by tokens
            token_chunks = split_text_by_tokens(sentence, max_tokens, model, overlap_tokens)
            chunks.extend(token_chunks)
            continue
        
        # Check if adding sentence would exceed limit
        if current_tokens + sentence_tokens > max_tokens:
            if current_chunk:
                chunks.append(' '.join(current_chunk))
            
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
        chunks.append(' '.join(current_chunk))
    
    return chunks


def generate_chunk_id(section_title: str, chunk_index: int, content: str) -> str:
    """Generate unique chunk ID."""
    content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
    return f"{section_title.replace(' ', '_')}_{chunk_index}_{content_hash}"


def chunk_section(
    section: Section,
    max_tokens: int = 500,
    overlap_tokens: int = 50,
    model: str = "gpt-4"
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
            total_chunks=len(text_chunks)
        )
        section_chunks.append(chunk)
    
    return section_chunks


def chunk_sections(
    sections: List[Section],
    max_tokens: int = 500,
    overlap_tokens: int = 50,
    model: str = "gpt-4"
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
            "max_tokens": 0
        }
    
    token_counts = [chunk.token_count for chunk in chunks]
    
    return {
        "total_chunks": len(chunks),
        "total_tokens": sum(token_counts),
        "avg_tokens": sum(token_counts) / len(token_counts),
        "min_tokens": min(token_counts),
        "max_tokens": max(token_counts)
    }

