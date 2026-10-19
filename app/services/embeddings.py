"""Asynchronous vector embedding services supporting OpenAI and deterministic offline simulation."""

import abc
import hashlib
import re
from typing import List
import httpx
import numpy as np

from app.core.config import settings
from app.core.logging import logger


class BaseEmbeddingService(abc.ABC):
    """Abstract interface for generating vector embeddings."""

    @abc.abstractmethod
    async def embed_query(self, text: str) -> List[float]:
        """Generate a normalized 1D embedding vector for input text."""
        pass


class DeterministicSimEmbeddingService(BaseEmbeddingService):
    """
    High-performance, offline deterministic embedding generator.
    
    Uses n-gram term hashing, position weighting, and L2 normalization to produce
    1536-dimensional float32 vectors. Preserves cosine similarity for identical and
    semantically overlapping texts without requiring external API calls or large model weights.
    """

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension

    def _tokenize(self, text: str) -> List[str]:
        # Normalize and tokenize into words and subwords
        clean = text.lower().strip()
        words = re.findall(r"\b\w+\b", clean)
        # Add character tri-grams for subword similarity
        trigrams = [clean[i:i+3] for i in range(max(0, len(clean) - 2))]
        return words + trigrams[:50]

    async def embed_query(self, text: str) -> List[float]:
        tokens = self._tokenize(text)
        vec = np.zeros(self.dimension, dtype=np.float32)

        if not tokens:
            # Return unit vector pointing along first dimension for empty string
            vec[0] = 1.0
            return vec.tolist()

        for idx, token in enumerate(tokens):
            # Compute stable hash
            token_hash = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            bucket = token_hash % self.dimension
            weight = 1.0 / (1.0 + 0.05 * idx)
            # Alternating sign from higher bits for zero-mean distribution
            sign = 1.0 if ((token_hash >> 16) & 1) else -1.0
            vec[bucket] += sign * weight

        # L2 normalize so cosine similarity is simply the dot product
        norm = np.linalg.norm(vec)
        if norm > 1e-9:
            vec = vec / norm
        else:
            vec[0] = 1.0

        return vec.tolist()


class OpenAIEmbeddingService(BaseEmbeddingService):
    """Asynchronous OpenAI API embedding client."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 10.0,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def embed_query(self, text: str) -> List[float]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": text,
            "model": self.model,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data["data"][0]["embedding"]
            except httpx.HTTPError as exc:
                logger.error(f"OpenAI embedding request failed: {exc}", exc_info=True)
                raise RuntimeError(f"Embedding generation failed: {exc}") from exc


def get_embedding_service() -> BaseEmbeddingService:
    """Factory creating configured embedding service instance."""
    if settings.EMBEDDING_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        return OpenAIEmbeddingService(
            api_key=settings.OPENAI_API_KEY,
            model=settings.EMBEDDING_MODEL,
            base_url=settings.OPENAI_BASE_URL,
        )
    return DeterministicSimEmbeddingService(dimension=settings.VECTOR_DIMENSION)
