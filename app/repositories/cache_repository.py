"""
Cache Repository for semantic vector store operations.
Encapsulates Redis Vector Search and resilient fallback persistence.
"""

from typing import Any, Dict, List, Optional, Tuple
from app.services.cache import semantic_cache


class CacheRepository:
    """Repository managing vector embeddings and cached prompt-response pairs."""

    def __init__(self, cache_service=semantic_cache):
        self.cache = cache_service

    async def get_match(
        self, embedding: List[float], threshold: Optional[float] = None
    ) -> Optional[Tuple[Dict[str, Any], float]]:
        """Search vector repository for nearest match above cosine similarity threshold."""
        return await self.cache.get_match(embedding, threshold=threshold)

    async def save(
        self,
        prompt: str,
        embedding: List[float],
        response: Dict[str, Any],
        model: str,
        ttl_seconds: Optional[int] = None,
    ) -> str:
        """Store semantic vector cache record."""
        return await self.cache.set(prompt, embedding, response, model, ttl_seconds)

    async def purge(self) -> int:
        """Purge all cached embeddings."""
        return await self.cache.purge()

    async def get_stats(self) -> Dict[str, Any]:
        """Retrieve vector index and cache health statistics."""
        return await self.cache.stats()

    async def inspect_nearest(
        self, embedding: List[float], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve top-K nearest neighbors for analysis."""
        return await self.cache.inspect_neighbors(embedding, top_k=top_k)
