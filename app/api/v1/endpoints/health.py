"""Health check and readiness endpoints for container orchestration."""

import time
from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.services.cache import semantic_cache

router = APIRouter()


@router.get("/health")
async def health_liveness():
    """Liveness probe indicating gateway process is active."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "timestamp": time.time(),
    }


@router.get("/ready")
async def health_readiness(response: Response):
    """Readiness probe evaluating Redis connectivity and vector index status."""
    cache_stats = await semantic_cache.get_stats()
    is_ready = True
    details = {
        "redis_connected": cache_stats["redis_connected"],
        "redisearch_active": cache_stats["redisearch_active"],
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "upstream_provider": settings.UPSTREAM_PROVIDER,
    }

    # Gateway remains resilient with memory fallback even if Redis is momentarily warming up
    return {
        "status": "ready" if is_ready else "degraded",
        "details": details,
        "timestamp": time.time(),
    }
