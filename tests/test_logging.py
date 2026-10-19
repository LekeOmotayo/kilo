"""Unit tests verifying structured JSON logging and TokenOps audit schemas."""

import io
import json
import logging
import pytest

from app.core.logging import JSONFormatter, log_tokenops_request, trace_id_ctx


def test_json_formatter_produces_valid_json():
    """Verify JSONFormatter outputs valid, parseable single-line JSON."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Test message with trace",
        args=(),
        exc_info=None,
    )
    trace_id_ctx.set("trace-abc-123")
    formatted = formatter.format(record)

    parsed = json.loads(formatted)
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "Test message with trace"
    assert parsed["trace_id"] == "trace-abc-123"
    assert "timestamp" in parsed


def test_log_tokenops_request_schema():
    """Verify log_tokenops_request emits all mandatory enterprise TokenOps audit fields."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())

    test_logger = logging.getLogger("tokenops_gateway")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.INFO)

    trace_id = "trace-corp-999"
    log_tokenops_request(
        trace_id=trace_id,
        endpoint="/v1/chat/completions",
        model_requested="gpt-4o",
        model_routed="gpt-4o-mini",
        model_tier=1,
        cache_hit=True,
        similarity_score=0.9452,
        prompt_tokens=150,
        completion_tokens=80,
        total_tokens=230,
        tokens_saved=230,
        actual_cost_usd=0.0,
        baseline_cost_usd=0.001175,
        cost_saved_usd=0.001175,
        latency_breakdown_ms={
            "embedding_ms": 2.1,
            "cache_lookup_ms": 1.4,
            "upstream_llm_ms": 0.0,
            "total_gateway_ms": 3.5,
        },
        routing_reason="Semantic Cache Hit",
        complexity_score=0.15,
    )

    test_logger.removeHandler(handler)
    output = stream.getvalue().strip()
    assert output, "Log output should not be empty"

    data = json.loads(output)
    assert data["trace_id"] == trace_id
    assert "tokenops" in data

    tokenops = data["tokenops"]
    assert tokenops["cache_hit"] is True
    assert tokenops["similarity_score"] == 0.9452
    assert tokenops["model_routed"] == "gpt-4o-mini"
    assert tokenops["model_tier"] == 1

    # Check token counts
    assert tokenops["tokens"]["prompt"] == 150
    assert tokenops["tokens"]["completion"] == 80
    assert tokenops["tokens"]["saved"] == 230

    # Check financials
    assert tokenops["financials"]["actual_cost_usd"] == 0.0
    assert tokenops["financials"]["cost_saved_usd"] == 0.001175

    # Check latency breakdown
    assert tokenops["latency_ms"]["cache_lookup_ms"] == 1.4
    assert tokenops["latency_ms"]["total_gateway_ms"] == 3.5
