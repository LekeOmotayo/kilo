"""Unit tests for semantic caching and vector search evaluation."""

import time
import numpy as np
import pytest

from app.services.cache import SemanticCacheService


@pytest.fixture
def cache():
    # Dedicated instance for unit tests using in-memory vector store
    instance = SemanticCacheService()
    return instance


@pytest.mark.asyncio
async def test_cache_store_and_hit(cache):
    """Store prompt vector and retrieve via cosine similarity search."""
    # Create normalized random vector
    vec = np.random.randn(1536).astype(np.float32)
    vec = (vec / np.linalg.norm(vec)).tolist()

    key = await cache.store(
        prompt="What is enterprise semantic caching?",
        vector=vec,
        response="Semantic caching stores vector embeddings of prompts to eliminate redundant LLM calls.",
        model="gpt-4o",
        tier=2,
        prompt_tokens=10,
        completion_tokens=20,
    )
    assert key.startswith(cache.prefix)

    # Search with exact same vector
    matches = await cache.find_similar(vector=vec, threshold=0.88, top_k=1)
    assert len(matches) == 1
    match = matches[0]
    assert match["prompt"] == "What is enterprise semantic caching?"
    assert pytest.approx(match["similarity_score"], rel=1e-3) == 1.0
    assert match["model"] == "gpt-4o"
    assert match["tier"] == 2


@pytest.mark.asyncio
async def test_cache_miss_on_low_similarity(cache):
    """Vector with low similarity below threshold must return no matches."""
    vec1 = np.zeros(1536, dtype=np.float32)
    vec1[0] = 1.0

    await cache.store(
        prompt="Query A",
        vector=vec1.tolist(),
        response="Response A",
        model="gpt-4o-mini",
        tier=1,
        prompt_tokens=5,
        completion_tokens=5,
    )

    # Orthogonal query vector
    vec2 = np.zeros(1536, dtype=np.float32)
    vec2[1] = 1.0  # Dot product with vec1 is 0.0

    matches = await cache.find_similar(vector=vec2.tolist(), threshold=0.88)
    assert len(matches) == 0


@pytest.mark.asyncio
async def test_cache_threshold_boundary(cache):
    """Verify behavior right around the similarity threshold."""
    # Construct two vectors with controlled cosine similarity
    # v1 = [1, 0], v2 = [cos(theta), sin(theta)]
    theta = 0.35  # cos(0.35) ~= 0.939 > 0.88
    v1 = np.zeros(1536, dtype=np.float32)
    v1[0] = 1.0

    v2 = np.zeros(1536, dtype=np.float32)
    v2[0] = np.cos(theta)
    v2[1] = np.sin(theta)

    await cache.store(
        prompt="Boundary Query",
        vector=v1.tolist(),
        response="Boundary Response",
        model="gpt-4o",
        tier=2,
        prompt_tokens=8,
        completion_tokens=12,
    )

    # With threshold 0.88, it should hit
    hit_matches = await cache.find_similar(vector=v2.tolist(), threshold=0.88)
    assert len(hit_matches) == 1
    assert hit_matches[0]["similarity_score"] >= 0.88

    # With strict threshold 0.98, it should miss
    miss_matches = await cache.find_similar(vector=v2.tolist(), threshold=0.98)
    assert len(miss_matches) == 0


@pytest.mark.asyncio
async def test_cache_purge_and_stats(cache):
    """Verify purge clears all cached items."""
    vec = [1.0] + [0.0] * 1535
    await cache.store("P1", vec, "R1", "m", 1, 5, 5)
    await cache.store("P2", vec, "R2", "m", 1, 5, 5)

    stats = await cache.get_stats()
    assert stats["total_documents"] == 2

    purged = await cache.purge()
    assert purged >= 2

    stats_after = await cache.get_stats()
    assert stats_after["total_documents"] == 0
