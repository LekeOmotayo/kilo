"""Unit tests for embedding services."""

import numpy as np
import pytest

from app.services.embeddings import (
    DeterministicSimEmbeddingService,
    OpenAIEmbeddingService,
    get_embedding_service,
)


@pytest.mark.asyncio
async def test_deterministic_embedding_dimension_and_norm():
    """Verify embedding vector length is 1536 and L2 normalized to 1.0."""
    service = DeterministicSimEmbeddingService(dimension=1536)
    vec = await service.embed_query("Enterprise semantic cache test prompt.")

    assert len(vec) == 1536
    norm = np.linalg.norm(np.array(vec, dtype=np.float32))
    assert pytest.approx(norm, rel=1e-3) == 1.0


@pytest.mark.asyncio
async def test_deterministic_identical_prompts_cosine_similarity():
    """Identical prompts must have a cosine similarity of 1.0."""
    service = DeterministicSimEmbeddingService(dimension=1536)
    v1 = await service.embed_query("What is the capital of France?")
    v2 = await service.embed_query("What is the capital of France?")

    sim = float(np.dot(np.array(v1), np.array(v2)))
    assert pytest.approx(sim, rel=1e-3) == 1.0


@pytest.mark.asyncio
async def test_deterministic_overlapping_vs_distinct_prompts():
    """Overlapping prompts must yield high similarity, while distinct prompts yield low similarity."""
    service = DeterministicSimEmbeddingService(dimension=1536)

    prompt_base = "What is the capital of France?"
    prompt_near = "What is the capital of France, please?"
    prompt_different = "How do I configure a Kubernetes ingress controller with TLS certificates?"

    v_base = np.array(await service.embed_query(prompt_base))
    v_near = np.array(await service.embed_query(prompt_near))
    v_diff = np.array(await service.embed_query(prompt_different))

    sim_near = float(np.dot(v_base, v_near))
    sim_diff = float(np.dot(v_base, v_diff))

    assert sim_near >= 0.85, f"Expected high similarity for near prompts, got {sim_near}"
    assert sim_diff < 0.60, f"Expected low similarity for disparate prompts, got {sim_diff}"
    assert sim_near > sim_diff


@pytest.mark.asyncio
async def test_deterministic_empty_prompt():
    """Empty or whitespace prompts must return valid normalized vector without errors."""
    service = DeterministicSimEmbeddingService(dimension=1536)
    vec = await service.embed_query("   ")
    assert len(vec) == 1536
    assert pytest.approx(np.linalg.norm(vec), rel=1e-3) == 1.0


def test_get_embedding_service_factory():
    """Verify factory returns appropriate embedding instance."""
    service = get_embedding_service()
    assert isinstance(service, DeterministicSimEmbeddingService)
