"""Integration tests for chat completions and generation endpoints."""

import pytest
import httpx


@pytest.mark.asyncio
async def test_chat_completion_cache_miss_then_cache_hit(async_client: httpx.AsyncClient):
    """
    Full semantic caching lifecycle:
    1. First call causes a cache MISS, routes model, calls upstream, and caches vector.
    2. Second call with semantically identical prompt causes a cache HIT, bypassing upstream.
    """
    payload = {
        "messages": [
            {"role": "user", "content": "What is the capital of France?"}
        ],
        "temperature": 0.5,
    }

    # 1. First call -> Cache MISS
    resp1 = await async_client.post("/v1/chat/completions", json=payload)
    assert resp1.status_code == 200
    data1 = resp1.json()

    assert resp1.headers.get("X-Cache") == "MISS"
    assert "X-Trace-Id" in resp1.headers
    assert "X-Routed-Model" in resp1.headers
    assert data1["tokenops"]["cache_hit"] is False
    assert data1["tokenops"]["tokens_saved"] == 0
    assert len(data1["choices"]) == 1

    # 2. Second call -> Cache HIT
    resp2 = await async_client.post("/v1/chat/completions", json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert resp2.headers.get("X-Cache") == "HIT"
    assert "X-Similarity-Score" in resp2.headers
    assert float(resp2.headers["X-Similarity-Score"]) >= 0.88
    assert data2["tokenops"]["cache_hit"] is True
    assert data2["tokenops"]["tokens_saved"] > 0
    assert data2["tokenops"]["actual_cost_usd"] == 0.0
    assert data2["tokenops"]["cost_saved_usd"] > 0.0
    assert data2["choices"][0]["message"]["content"] == data1["choices"][0]["message"]["content"]


@pytest.mark.asyncio
async def test_bypass_cache_flag(async_client: httpx.AsyncClient):
    """When bypass_cache is true, the gateway must bypass cache and hit upstream."""
    payload = {
        "messages": [{"role": "user", "content": "Tell me a fun fact"}],
        "bypass_cache": False,
    }

    # Seed the cache
    r1 = await async_client.post("/v1/chat/completions", json=payload)
    assert r1.status_code == 200

    # Repeat with bypass_cache = True
    payload["bypass_cache"] = True
    r2 = await async_client.post("/v1/chat/completions", json=payload)
    assert r2.status_code == 200
    assert r2.headers.get("X-Cache") == "MISS"
    assert r2.json()["tokenops"]["cache_hit"] is False


@pytest.mark.asyncio
async def test_custom_trace_id_propagation(async_client: httpx.AsyncClient):
    """Trace ID provided in request header must be preserved in response and telemetry."""
    custom_trace = "enterprise-trace-xyz-987"
    payload = {
        "messages": [{"role": "user", "content": "Ping trace test"}],
    }

    resp = await async_client.post(
        "/v1/chat/completions",
        json=payload,
        headers={"X-Trace-Id": custom_trace},
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-Trace-Id") == custom_trace
    assert resp.json()["tokenops"]["trace_id"] == custom_trace


@pytest.mark.asyncio
async def test_force_tier_override(async_client: httpx.AsyncClient):
    """Caller can enforce specific tier in request body."""
    payload = {
        "messages": [{"role": "user", "content": "Simple message"}],
        "force_tier": 3,
    }

    resp = await async_client.post("/v1/chat/completions", json=payload)
    assert resp.status_code == 200
    assert resp.headers.get("X-Tier") == "3"
    assert resp.json()["tokenops"]["model_tier"] == 3


@pytest.mark.asyncio
async def test_raw_generate_endpoint(async_client: httpx.AsyncClient):
    """Verify /v1/generate accepts simple string prompt."""
    payload = {
        "prompt": "Explain semantic caching in one sentence.",
    }

    resp = await async_client.post("/v1/generate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["choices"]) == 1
    assert "tokenops" in data


@pytest.mark.asyncio
async def test_empty_messages_validation_error(async_client: httpx.AsyncClient):
    """Request with empty messages array must return 422 Unprocessable Entity."""
    resp = await async_client.post("/v1/chat/completions", json={"messages": []})
    assert resp.status_code == 422
