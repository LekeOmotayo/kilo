"""Structured JSON logging with trace context and TokenOps metrics."""

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Context variable for distributed trace ID
trace_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class JSONFormatter(logging.Formatter):
    """Custom formatter producing structured JSON log records for enterprise log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": trace_id_ctx.get() or getattr(record, "trace_id", ""),
            "request_id": request_id_ctx.get() or getattr(record, "request_id", ""),
        }

        # Include structured extra payload if present
        if hasattr(record, "tokenops") and isinstance(record.tokenops, dict):
            log_data["tokenops"] = record.tokenops

        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_data.update(record.extra_data)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure the root and application loggers to output structured JSON to stdout."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    # Disable noisy third-party loggers
    logging.getLogger("uvicorn.access").handlers = [handler]
    logging.getLogger("uvicorn.error").handlers = [handler]
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return logging.getLogger("tokenops_gateway")


logger = logging.getLogger("tokenops_gateway")


def log_tokenops_request(
    trace_id: str,
    endpoint: str,
    model_requested: Optional[str],
    model_routed: str,
    model_tier: int,
    cache_hit: bool,
    similarity_score: Optional[float],
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    tokens_saved: int,
    actual_cost_usd: float,
    baseline_cost_usd: float,
    cost_saved_usd: float,
    latency_breakdown_ms: Dict[str, float],
    routing_reason: Optional[str] = None,
    complexity_score: Optional[float] = None,
    status_code: int = 200,
) -> None:
    """Emit a canonical structured TokenOps audit log line for enterprise observability."""
    tokenops_payload = {
        "event_type": "llm_request_audit",
        "endpoint": endpoint,
        "status_code": status_code,
        "model_requested": model_requested,
        "model_routed": model_routed,
        "model_tier": model_tier,
        "cache_hit": cache_hit,
        "similarity_score": round(similarity_score, 4) if similarity_score is not None else None,
        "tokens": {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": total_tokens,
            "saved": tokens_saved,
        },
        "financials": {
            "actual_cost_usd": actual_cost_usd,
            "baseline_cost_usd": baseline_cost_usd,
            "cost_saved_usd": cost_saved_usd,
        },
        "latency_ms": latency_breakdown_ms,
        "routing": {
            "complexity_score": round(complexity_score, 4) if complexity_score is not None else None,
            "reason": routing_reason,
        },
    }

    logger.info(
        f"TokenOps request completed: cache_hit={cache_hit} routed={model_routed} saved_usd=${cost_saved_usd:.6f}",
        extra={"tokenops": tokenops_payload, "trace_id": trace_id},
    )
