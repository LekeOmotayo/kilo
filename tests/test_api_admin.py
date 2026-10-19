"""Integration tests for administration, health, and observability endpoints."""

import pytest
import httpx


@pytest.mark.asyncio
async def test_health_and_readiness_endpoints(async_client: httpx.AsyncClient):
    """Verify health liveness and readiness probes return 200."""
    health_resp = await async_client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "healthy"

    ready_resp = await async_client.get("/v1/ready")
    assert ready_resp.status_code == 200
    assert ready_resp.json()["status"] in ("ready", "degraded")


@pytest.mark.asyncio
async def test_cache_stats_and_purge_endpoints(async_client: httpx.AsyncClient):
    """Verify cache statistics retrieval and purging."""
    # Seed cache with one request
    await async_client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "Cache stats test query"}]},
    )

    stats_resp = await async_client.get("/v1/cache/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_documents"] >= 1

    purge_resp = await async_client.post("/v1/cache/purge")
    assert purge_resp.status_code == 200
    assert purge_resp.json()["status"] == "success"

    stats_after = await async_client.get("/v1/cache/stats")
    assert stats_after.json()["total_documents"] == 0


@pytest.mark.asyncio
async def test_cache_inspect_endpoint(async_client: httpx.AsyncClient):
    """Verify vector inspect endpoint returns nearest neighbors."""
    prompt = "Enterprise architecture query"
    await async_client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": prompt}]},
    )

    inspect_resp = await async_client.post(
        "/v1/cache/inspect",
        json={"prompt": prompt, "top_k": 2},
    )
    assert inspect_resp.status_code == 200
    inspect_data = inspect_resp.json()
    assert len(inspect_data["matches"]) >= 1
    assert "similarity_score" in inspect_data["matches"][0]


@pytest.mark.asyncio
async def test_tokenops_summary_and_models(async_client: httpx.AsyncClient):
    """Verify TokenOps summary and pricing catalog endpoints."""
    summary_resp = await async_client.get("/v1/tokenops/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert "total_requests" in summary
    assert "savings_percentage" in summary

    models_resp = await async_client.get("/v1/tokenops/models")
    assert models_resp.status_code == 200
    models_data = models_resp.json()
    assert "pricing_table_usd_per_1m_tokens" in models_data
    assert "model_tiers" in models_data


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint(async_client: httpx.AsyncClient):
    """Verify /metrics returns raw Prometheus text format."""
    metrics_resp = await async_client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert "tokenops" in metrics_resp.text


@pytest.mark.asyncio
async def test_dashboard_ui_endpoint(async_client: httpx.AsyncClient):
    """Verify GET / returns the HTML dashboard UI."""
    resp = await async_client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "TokenOps Gateway" in resp.text

