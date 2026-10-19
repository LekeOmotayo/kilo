"""Unit tests for TokenOps pricing calculations and metrics aggregator."""

import pytest
from app.core.pricing import calculate_cost, calculate_tokenops_metrics, get_model_rates
from app.services.tokenops import TokenOpsService


def test_model_rates_retrieval():
    """Verify rate lookup returns correct per-million figures."""
    in_rate, out_rate = get_model_rates("gpt-4o-mini")
    assert in_rate == 0.15
    assert out_rate == 0.60

    in_rate_4o, out_rate_4o = get_model_rates("gpt-4o")
    assert in_rate_4o == 2.50
    assert out_rate_4o == 10.00


def test_calculate_cost_accuracy():
    """Verify dollar calculations for known token volumes."""
    # 1,000,000 prompt tokens and 1,000,000 completion tokens of gpt-4o-mini
    cost = calculate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
    assert pytest.approx(cost, rel=1e-4) == 0.75  # 0.15 + 0.60

    # 10,000 prompt tokens and 2,000 completion tokens of gpt-4o
    # in: 10,000 * 2.5 / 1,000,000 = 0.025
    # out: 2,000 * 10.0 / 1,000,000 = 0.020
    cost_4o = calculate_cost("gpt-4o", 10_000, 2_000)
    assert pytest.approx(cost_4o, rel=1e-4) == 0.045


def test_tokenops_metrics_on_cache_hit():
    """On cache hit, actual cost must be zero and savings equal to baseline."""
    metrics = calculate_tokenops_metrics(
        baseline_model="gpt-4o",
        routed_model="gpt-4o-mini",
        prompt_tokens=1000,
        completion_tokens=500,
        cache_hit=True,
    )

    assert metrics["actual_cost_usd"] == 0.0
    assert metrics["baseline_cost_usd"] > 0.0
    assert metrics["cost_saved_usd"] == metrics["baseline_cost_usd"]
    assert metrics["tokens_saved"] == 1500


def test_tokenops_metrics_on_cache_miss_routing_savings():
    """On cache miss routed to cheaper model, savings is difference between baseline and actual."""
    metrics = calculate_tokenops_metrics(
        baseline_model="gpt-4o",
        routed_model="gpt-4o-mini",
        prompt_tokens=100_000,
        completion_tokens=50_000,
        cache_hit=False,
    )

    assert metrics["actual_cost_usd"] > 0.0
    assert metrics["baseline_cost_usd"] > metrics["actual_cost_usd"]
    assert metrics["cost_saved_usd"] == pytest.approx(
        metrics["baseline_cost_usd"] - metrics["actual_cost_usd"], rel=1e-4
    )
    assert metrics["tokens_saved"] == 0


@pytest.mark.asyncio
async def test_tokenops_service_aggregation():
    """Verify aggregator maintains accurate totals, ratios, and percentages."""
    service = TokenOpsService()

    # Record 1 cache hit
    await service.record_request(
        endpoint="/v1/chat/completions",
        model_routed="gpt-4o-mini",
        model_tier=1,
        cache_hit=True,
        prompt_tokens=100,
        completion_tokens=50,
        tokens_saved=150,
        actual_cost_usd=0.0,
        cost_saved_usd=0.001,
        total_latency_seconds=0.015,
    )

    # Record 1 cache miss
    await service.record_request(
        endpoint="/v1/chat/completions",
        model_routed="gpt-4o",
        model_tier=2,
        cache_hit=False,
        prompt_tokens=200,
        completion_tokens=100,
        tokens_saved=0,
        actual_cost_usd=0.002,
        cost_saved_usd=0.0,
        total_latency_seconds=0.35,
    )

    summary = await service.get_summary()

    assert summary["total_requests"] == 2
    assert summary["cache_hits"] == 1
    assert summary["cache_misses"] == 1
    assert summary["cache_hit_ratio"] == 0.5
    assert summary["tokens_saved_by_cache"] == 150
    assert summary["total_spend_usd"] == 0.002
    assert summary["total_savings_usd"] == 0.001
    assert summary["tier_distribution"]["tier_1"] == 1
    assert summary["tier_distribution"]["tier_2"] == 1

    # Check Prometheus export
    prom_data = service.export_prometheus_metrics().decode("utf-8")
    assert "tokenops_requests_total" in prom_data
