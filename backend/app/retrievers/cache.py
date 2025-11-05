"""
Retriever caching module.

This module provides caching for retrievers to avoid rebuilding BM25 indices
and ParentDocument collections on every comparison.
"""

import time
import logging
from typing import Dict, Optional, Tuple
from collections import OrderedDict

from app.retrievers.base import BaseRetriever

logger = logging.getLogger(__name__)


class RetrieverCache:
    """
    LRU cache with TTL for retrievers.

    This cache stores retrievers (especially BM25 and ParentDocument) to avoid
    rebuilding indices on every comparison. It uses:
    - LRU eviction: Least recently used items are evicted first
    - TTL: Items expire after a certain time
    - Size limit: Maximum number of items in cache
    """

    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        """
        Initialize retriever cache.

        Args:
            max_size: Maximum number of retrievers to cache
            ttl_seconds: Time-to-live in seconds (default: 1 hour)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, Tuple[BaseRetriever, float]] = OrderedDict()
        logger.info(f"Initialized RetrieverCache: max_size={max_size}, ttl={ttl_seconds}s")

    def get(self, key: str) -> Optional[BaseRetriever]:
        """
        Get retriever from cache.

        Args:
            key: Cache key (e.g., "sparse_{document_id}" or "parent_{document_id}")

        Returns:
            Retriever if found and not expired, None otherwise
        """
        if key not in self._cache:
            logger.debug(f"Cache miss: {key}")
            return None

        retriever, timestamp = self._cache[key]

        # Check if expired
        if time.time() - timestamp > self.ttl_seconds:
            logger.debug(f"Cache expired: {key}")
            del self._cache[key]
            return None

        # Move to end (mark as recently used)
        self._cache.move_to_end(key)
        logger.debug(f"Cache hit: {key}")
        return retriever

    def set(self, key: str, retriever: BaseRetriever) -> None:
        """
        Store retriever in cache.

        Args:
            key: Cache key
            retriever: Retriever instance to cache
        """
        # Remove if already exists (to update timestamp)
        if key in self._cache:
            del self._cache[key]

        # Add to cache
        self._cache[key] = (retriever, time.time())
        logger.debug(f"Cache set: {key}")

        # Evict oldest if over size limit
        if len(self._cache) > self.max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug(f"Cache evicted (size limit): {oldest_key}")

    def invalidate(self, key: str) -> None:
        """
        Invalidate a cache entry.

        Args:
            key: Cache key to invalidate
        """
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache invalidated: {key}")

    def clear(self) -> None:
        """Clear all cache entries."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cache cleared: {count} entries removed")

    def get_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats (size, max_size, expired_count)
        """
        # Count expired entries
        current_time = time.time()
        expired_count = sum(
            1
            for _, timestamp in self._cache.values()
            if current_time - timestamp > self.ttl_seconds
        )

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "expired_count": expired_count,
            "ttl_seconds": self.ttl_seconds,
        }

    def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        current_time = time.time()
        expired_keys = [
            key
            for key, (_, timestamp) in self._cache.items()
            if current_time - timestamp > self.ttl_seconds
        ]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

        return len(expired_keys)


# Global cache instance
_retriever_cache: Optional[RetrieverCache] = None


def get_retriever_cache() -> RetrieverCache:
    """
    Get or create global retriever cache.

    Returns:
        Global RetrieverCache instance
    """
    global _retriever_cache
    if _retriever_cache is None:
        _retriever_cache = RetrieverCache(max_size=100, ttl_seconds=3600)
    return _retriever_cache


def clear_retriever_cache() -> None:
    """Clear the global retriever cache."""
    cache = get_retriever_cache()
    cache.clear()
