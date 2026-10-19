"""Redis Vector Search semantic caching service with cosine similarity evaluation."""

import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import redis.asyncio as redis
from redis.commands.search.field import NumericField, TagField, TextField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query

from app.core.config import settings
from app.core.logging import logger


class SemanticCacheService:
    """
    Enterprise Semantic Caching engine using Redis Vector Similarity Search (RediSearch).
    
    Supports HNSW index with COSINE distance metric:
        Redis Distance = 1.0 - Cosine_Similarity
        Cosine_Similarity = 1.0 - Redis_Distance
    """

    def __init__(self, redis_url: str = settings.REDIS_URL):
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None
        self.index_name = settings.REDIS_INDEX_NAME
        self.prefix = settings.REDIS_PREFIX
        self.dimension = settings.VECTOR_DIMENSION
        self.threshold = settings.SIMILARITY_THRESHOLD
        self.ttl = settings.CACHE_TTL_SECONDS
        self._redisearch_available = False
        # In-memory vector fallback for environments without Redis Stack / RediSearch
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    async def connect(self) -> None:
        """Establish Redis connection pool and ensure vector search index exists."""
        try:
            self.client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,  # Binary mode for raw vector bytes
            )
            await self.client.ping()
            await self._ensure_index()
            logger.info("Connected to Redis vector store successfully.")
        except Exception as exc:
            logger.warning(
                f"Redis connection / index initialization notice: {exc}. Operating with resilient memory vector fallback."
            )

    async def close(self) -> None:
        """Close Redis connection."""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def _ensure_index(self) -> None:
        """Verify or create Redis Vector Search HNSW index."""
        if not self.client:
            return

        try:
            # Check if index already exists
            await self.client.ft(self.index_name).info()
            self._redisearch_available = True
            logger.info(f"Redis vector index '{self.index_name}' is active.")
        except Exception:
            # Index does not exist or RediSearch module not loaded
            try:
                schema = (
                    TextField("prompt"),
                    TextField("response"),
                    TagField("model"),
                    NumericField("tier"),
                    NumericField("prompt_tokens"),
                    NumericField("completion_tokens"),
                    NumericField("created_at"),
                    VectorField(
                        "embedding",
                        "HNSW",
                        {
                            "TYPE": "FLOAT32",
                            "DIM": self.dimension,
                            "DISTANCE_METRIC": "COSINE",
                            "M": 16,
                            "EF_CONSTRUCTION": 200,
                        },
                    ),
                )
                definition = IndexDefinition(prefix=[self.prefix], index_type=IndexType.HASH)
                await self.client.ft(self.index_name).create_index(schema, definition=definition)
                self._redisearch_available = True
                logger.info(f"Created Redis Vector Search index: {self.index_name}")
            except Exception as create_exc:
                logger.warning(
                    f"RediSearch module unavailable on Redis server ({create_exc}). Using vector memory fallback."
                )
                self._redisearch_available = False

    def _vector_to_bytes(self, vector: List[float]) -> bytes:
        """Serialize float list to raw binary float32 bytes for Redis Vector."""
        return np.array(vector, dtype=np.float32).tobytes()

    async def find_similar(
        self,
        vector: List[float],
        threshold: Optional[float] = None,
        top_k: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Query vector index for nearest neighbors using cosine similarity.
        
        Returns matching records with computed similarity scores.
        """
        target_threshold = threshold if threshold is not None else self.threshold

        # 1. Try Redis Vector Search if available
        if self.client and self._redisearch_available:
            try:
                query_vec = self._vector_to_bytes(vector)
                # Redis query: Return K nearest neighbors based on vector distance
                q = (
                    Query(f"*=>[KNN {top_k} @embedding $vec AS score]")
                    .sort_by("score")
                    .return_fields(
                        "prompt",
                        "response",
                        "model",
                        "tier",
                        "prompt_tokens",
                        "completion_tokens",
                        "created_at",
                        "score",
                    )
                    .dialect(2)
                )

                res = await self.client.ft(self.index_name).search(q, query_params={"vec": query_vec})
                matches = []
                for doc in res.docs:
                    # In RediSearch COSINE metric: score is distance (1.0 - cosine_similarity)
                    distance = float(doc.score)
                    similarity = max(0.0, min(1.0, 1.0 - distance))

                    if similarity >= target_threshold:
                        matches.append({
                            "prompt": getattr(doc, "prompt", ""),
                            "response": getattr(doc, "response", ""),
                            "model": getattr(doc, "model", ""),
                            "tier": int(getattr(doc, "tier", 1)),
                            "prompt_tokens": int(getattr(doc, "prompt_tokens", 0)),
                            "completion_tokens": int(getattr(doc, "completion_tokens", 0)),
                            "created_at": float(getattr(doc, "created_at", 0.0)),
                            "distance": distance,
                            "similarity_score": similarity,
                        })
                return matches
            except Exception as exc:
                logger.warning(f"RediSearch query failed: {exc}. Falling back to memory vector lookup.")

        # 2. Resilient In-Memory Vector Search Fallback
        query_np = np.array(vector, dtype=np.float32)
        norm_q = np.linalg.norm(query_np)
        if norm_q > 1e-9:
            query_np = query_np / norm_q

        candidates = []
        now = time.time()

        for key, entry in list(self._memory_cache.items()):
            # Check expiration
            if entry.get("expires_at", 0) < now:
                self._memory_cache.pop(key, None)
                continue

            entry_vec = entry.get("vector_np")
            if entry_vec is not None:
                # Cosine similarity for normalized vectors is the dot product
                sim = float(np.dot(query_np, entry_vec))
                dist = 1.0 - sim
                if sim >= target_threshold:
                    candidates.append({
                        "prompt": entry["prompt"],
                        "response": entry["response"],
                        "model": entry["model"],
                        "tier": entry["tier"],
                        "prompt_tokens": entry["prompt_tokens"],
                        "completion_tokens": entry["completion_tokens"],
                        "created_at": entry["created_at"],
                        "distance": dist,
                        "similarity_score": sim,
                    })

        candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
        return candidates[:top_k]

    async def store(
        self,
        prompt: str,
        vector: List[float],
        response: str,
        model: str,
        tier: int,
        prompt_tokens: int,
        completion_tokens: int,
        ttl_seconds: Optional[int] = None,
    ) -> str:
        """Store prompt embedding and completion in Redis semantic cache."""
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl
        prompt_hash = hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()
        key = f"{self.prefix}{prompt_hash}"
        now = time.time()

        vec_bytes = self._vector_to_bytes(vector)
        mapping = {
            "prompt": prompt,
            "response": response,
            "model": model,
            "tier": tier,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "created_at": now,
            "embedding": vec_bytes,
        }

        # Save to Redis
        if self.client:
            try:
                await self.client.hset(key, mapping=mapping)
                await self.client.expire(key, ttl)
            except Exception as exc:
                logger.warning(f"Failed to persist cache key {key} in Redis: {exc}")

        # Always update memory fallback for high resilience
        vec_np = np.array(vector, dtype=np.float32)
        norm = np.linalg.norm(vec_np)
        if norm > 1e-9:
            vec_np = vec_np / norm

        self._memory_cache[key] = {
            "prompt": prompt,
            "response": response,
            "model": model,
            "tier": tier,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "created_at": now,
            "expires_at": now + ttl,
            "vector_np": vec_np,
        }

        return key

    async def purge(self) -> int:
        """Purge all semantic cache keys."""
        purged = 0
        if self.client:
            try:
                keys = []
                async for key in self.client.scan_iter(f"{self.prefix}*"):
                    keys.append(key)
                if keys:
                    purged = await self.client.delete(*keys)
            except Exception as exc:
                logger.warning(f"Error purging Redis keys: {exc}")

        purged += len(self._memory_cache)
        self._memory_cache.clear()
        return purged

    async def get_stats(self) -> Dict[str, Any]:
        """Fetch operational cache statistics."""
        doc_count = len(self._memory_cache)
        connected = False

        if self.client:
            try:
                await self.client.ping()
                connected = True
                if self._redisearch_available:
                    info = await self.client.ft(self.index_name).info()
                    doc_count = int(info.get("num_docs", doc_count))
            except Exception:
                connected = False

        return {
            "index_name": self.index_name,
            "total_documents": doc_count,
            "similarity_threshold": self.threshold,
            "ttl_seconds": self.ttl,
            "redis_connected": connected,
            "redisearch_active": self._redisearch_available,
        }


# Global singleton instance
semantic_cache = SemanticCacheService()
