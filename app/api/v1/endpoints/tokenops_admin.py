"""TokenOps observability, pricing catalog, and Prometheus metrics exposition."""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST

from app.core.config import settings
from app.core.pricing import MODEL_PRICING
from app.models.schemas import TokenOpsSummaryResponse
from app.services.tokenops import tokenops_service

router = APIRouter()


@router.get("/summary", response_model=TokenOpsSummaryResponse)
async def get_tokenops_summary() -> TokenOpsSummaryResponse:
    """Retrieve executive TokenOps financial and token savings report."""
    summary = await tokenops_service.get_summary()
    return TokenOpsSummaryResponse(**summary)


@router.get("/models")
async def get_models_catalog():
    """Retrieve model pricing table and tier mapping rules."""
    return {
        "pricing_table_usd_per_1m_tokens": MODEL_PRICING,
        "model_tiers": {
            "tier_1": {
                "name": "Fast / Lightweight / Cost-Saver",
                "model": settings.TIER_1_MODEL,
                "max_tokens": settings.TIER_1_MAX_TOKENS,
                "complexity_threshold": f"< {settings.COMPLEXITY_THRESHOLD_TIER2}",
            },
            "tier_2": {
                "name": "Standard / Flagship Reasoning",
                "model": settings.TIER_2_MODEL,
                "max_tokens": settings.TIER_2_MAX_TOKENS,
                "complexity_threshold": f">= {settings.COMPLEXITY_THRESHOLD_TIER2} and < {settings.COMPLEXITY_THRESHOLD_TIER3}",
            },
            "tier_3": {
                "name": "Advanced Analytical / Reasoning",
                "model": settings.TIER_3_MODEL,
                "max_tokens": f"> {settings.TIER_2_MAX_TOKENS}",
                "complexity_threshold": f">= {settings.COMPLEXITY_THRESHOLD_TIER3}",
            },
        },
        "baseline_model": settings.DEFAULT_BASELINE_MODEL,
    }


@router.get("/metrics")
async def get_prometheus_metrics():
    """Prometheus metrics endpoint for enterprise monitoring."""
    data = tokenops_service.export_prometheus_metrics()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
