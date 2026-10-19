"""TokenOps observability, metric aggregation, and Prometheus metrics registry."""

import asyncio
import time
from typing import Any, Dict, List
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# Prometheus Metric Definitions
PROMETHEUS_REQUESTS_TOTAL = Counter(
    "tokenops_requests_total",
    "Total incoming LLM requests processed by the gateway",
    ["endpoint", "model_routed", "cache_hit"],
)

PROMETHEUS_TOKENS_TOTAL = Counter(
    "tokenops_tokens_total",
    "Total tokens processed across all requests",
    ["model_routed", "token_type"],  # prompt, completion
)

PROMETHEUS_TOKENS_SAVED_TOTAL = Counter(
    "tokenops_tokens_saved_total",
    "Total tokens saved due to semantic cache hits",
)

PROMETHEUS_COST_INCURRED_USD = Counter(
    "tokenops_cost_incurred_usd_total",
    "Total dollar cost incurred from upstream LLM invocations",
    ["model_routed"],
)

PROMETHEUS_COST_SAVED_USD = Counter(
    "tokenops_cost_saved_usd_total",
    "Total dollar cost saved through semantic caching and dynamic model tiering",
)

PROMETHEUS_LATENCY_HISTOGRAM = Histogram(
    "tokenops_gateway_latency_seconds",
    "Gateway processing latency in seconds",
    ["stage", "cache_hit"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

PROMETHEUS_CACHE_HIT_RATIO_GAUGE = Gauge(
    "tokenops_cache_hit_ratio",
    "Current semantic cache hit ratio",
)


class TokenOpsService:
    """Thread-safe TokenOps aggregator tracking enterprise financial and operational metrics."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self.total_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_tokens_processed = 0
        self.tokens_saved_by_cache = 0
        self.total_spend_usd = 0.0
        self.total_savings_usd = 0.0
        self.tier_distribution = {
            "tier_1": 0,
            "tier_2": 0,
            "tier_3": 0,
        }

    async def record_request(
        self,
        endpoint: str,
        model_routed: str,
        model_tier: int,
        cache_hit: bool,
        prompt_tokens: int,
        completion_tokens: int,
        tokens_saved: int,
        actual_cost_usd: float,
        cost_saved_usd: float,
        total_latency_seconds: float,
    ) -> None:
        """Record telemetry data into both internal counters and Prometheus collectors."""
        async with self._lock:
            self.total_requests += 1
            if cache_hit:
                self.cache_hits += 1
            else:
                self.cache_misses += 1

            self.total_tokens_processed += (prompt_tokens + completion_tokens)
            self.tokens_saved_by_cache += tokens_saved
            self.total_spend_usd = round(self.total_spend_usd + actual_cost_usd, 6)
            self.total_savings_usd = round(self.total_savings_usd + cost_saved_usd, 6)

            tier_key = f"tier_{model_tier}"
            if tier_key in self.tier_distribution:
                self.tier_distribution[tier_key] += 1

            hit_ratio = self.cache_hits / max(1, self.total_requests)
            PROMETHEUS_CACHE_HIT_RATIO_GAUGE.set(hit_ratio)

        # Update Prometheus Metrics
        cache_str = "true" if cache_hit else "false"
        PROMETHEUS_REQUESTS_TOTAL.labels(
            endpoint=endpoint,
            model_routed=model_routed,
            cache_hit=cache_str,
        ).inc()

        PROMETHEUS_TOKENS_TOTAL.labels(
            model_routed=model_routed,
            token_type="prompt",
        ).inc(prompt_tokens)

        PROMETHEUS_TOKENS_TOTAL.labels(
            model_routed=model_routed,
            token_type="completion",
        ).inc(completion_tokens)

        if tokens_saved > 0:
            PROMETHEUS_TOKENS_SAVED_TOTAL.inc(tokens_saved)

        if actual_cost_usd > 0:
            PROMETHEUS_COST_INCURRED_USD.labels(model_routed=model_routed).inc(actual_cost_usd)

        if cost_saved_usd > 0:
            PROMETHEUS_COST_SAVED_USD.inc(cost_saved_usd)

        PROMETHEUS_LATENCY_HISTOGRAM.labels(
            stage="total_gateway",
            cache_hit=cache_str,
        ).observe(total_latency_seconds)

    async def get_summary(self) -> Dict[str, Any]:
        """Generate high-level financial and efficiency report."""
        async with self._lock:
            total_req = self.total_requests
            hits = self.cache_hits
            misses = self.cache_misses
            hit_ratio = round((hits / total_req), 4) if total_req > 0 else 0.0

            total_hypothetical_spend = self.total_spend_usd + self.total_savings_usd
            savings_pct = (
                round((self.total_savings_usd / total_hypothetical_spend) * 100.0, 2)
                if total_hypothetical_spend > 0
                else 0.0
            )

            return {
                "total_requests": total_req,
                "cache_hits": hits,
                "cache_misses": misses,
                "cache_hit_ratio": hit_ratio,
                "total_tokens_processed": self.total_tokens_processed,
                "tokens_saved_by_cache": self.tokens_saved_by_cache,
                "total_spend_usd": round(self.total_spend_usd, 4),
                "total_savings_usd": round(self.total_savings_usd, 4),
                "savings_percentage": savings_pct,
                "tier_distribution": dict(self.tier_distribution),
            }

    def export_prometheus_metrics(self) -> bytes:
        """Export raw Prometheus metrics formatted for scraping."""
        return generate_latest()


# Global singleton instance
tokenops_service = TokenOpsService()
