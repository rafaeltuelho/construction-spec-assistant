"""
Token counting utilities for text chunking and LLM context management.

This module provides functions for counting tokens using tiktoken,
which is essential for managing chunk sizes and LLM context windows.
"""

from typing import List, Optional
from functools import lru_cache
import tiktoken

from app.utils.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=10)
def get_encoding_for_model(model: str = "gpt-4") -> tiktoken.Encoding:
    """
    Get tiktoken encoding for a specific model (cached).

    Args:
        model: Model name (e.g., "gpt-4", "gpt-3.5-turbo")

    Returns:
        tiktoken.Encoding instance
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
        return encoding
    except KeyError:
        logger.warning(f"Model {model} not found, using cl100k_base encoding")
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Count the number of tokens in a text string.

    Args:
        text: Text to count tokens for
        model: Model name for tokenization

    Returns:
        Number of tokens
    """
    if not text:
        return 0

    encoding = get_encoding_for_model(model)
    tokens = encoding.encode(text)
    return len(tokens)


def truncate_text_to_tokens(text: str, max_tokens: int, model: str = "gpt-4") -> str:
    """
    Truncate text to a maximum number of tokens.

    Args:
        text: Text to truncate
        max_tokens: Maximum number of tokens
        model: Model name for tokenization

    Returns:
        Truncated text
    """
    if not text:
        return ""

    encoding = get_encoding_for_model(model)
    tokens = encoding.encode(text)

    if len(tokens) <= max_tokens:
        return text

    truncated_tokens = tokens[:max_tokens]
    return encoding.decode(truncated_tokens)


def estimate_tokens(text: str) -> int:
    """
    Fast estimation of token count without tiktoken.

    Uses a simple heuristic: ~4 characters per token.
    Useful for quick checks before expensive tokenization.

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated number of tokens
    """
    if not text:
        return 0

    # Rough estimate: 4 characters per token
    return len(text) // 4


def get_token_budget(
    max_tokens: int, reserved_tokens: int = 100, safety_margin: float = 0.9
) -> int:
    """
    Calculate available token budget with safety margin.

    Args:
        max_tokens: Maximum tokens allowed
        reserved_tokens: Tokens reserved for system/formatting
        safety_margin: Safety margin (0.0-1.0)

    Returns:
        Available token budget
    """
    available = max_tokens - reserved_tokens
    return int(available * safety_margin)


def split_text_by_tokens(
    text: str, max_tokens: int, model: str = "gpt-4", overlap_tokens: int = 0
) -> List[str]:
    """
    Split text into chunks by token count.

    Args:
        text: Text to split
        max_tokens: Maximum tokens per chunk
        model: Model name for tokenization
        overlap_tokens: Number of tokens to overlap between chunks

    Returns:
        List of text chunks
    """
    if not text:
        return []

    encoding = get_encoding_for_model(model)
    tokens = encoding.encode(text)

    if len(tokens) <= max_tokens:
        return [text]

    chunks = []
    start = 0

    while start < len(tokens):
        end = start + max_tokens
        chunk_tokens = tokens[start:end]
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)

        # Move start position with overlap
        start = end - overlap_tokens

        # Prevent infinite loop
        if start >= len(tokens):
            break

    return chunks


def validate_token_count(text: str, max_tokens: int, model: str = "gpt-4") -> bool:
    """
    Validate that text is within token limit.

    Args:
        text: Text to validate
        max_tokens: Maximum allowed tokens
        model: Model name for tokenization

    Returns:
        True if within limit, False otherwise
    """
    token_count = count_tokens(text, model)
    return token_count <= max_tokens


def analyze_document_token_limits(sections: List[str], model: str = "gpt-4") -> dict:
    """
    Analyze token distribution across document sections.

    Args:
        sections: List of section texts
        model: Model name for tokenization

    Returns:
        Dictionary with token statistics
    """
    token_counts = [count_tokens(section, model) for section in sections]

    return {
        "total_tokens": sum(token_counts),
        "num_sections": len(sections),
        "min_tokens": min(token_counts) if token_counts else 0,
        "max_tokens": max(token_counts) if token_counts else 0,
        "avg_tokens": sum(token_counts) / len(token_counts) if token_counts else 0,
        "token_counts": token_counts,
    }
