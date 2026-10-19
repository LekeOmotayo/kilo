"""Semantic cache administration and inspection endpoints."""

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    CacheInspectItem,
    CacheInspectRequest,
    CacheInspectResponse,
    CachePurgeResponse,
    CacheStatsResponse,
)
from app.services.cache import semantic_cache
from app.services.embeddings import get_embedding_service
from app.services.tokenops import tokenops_service

router = APIRouter()


@router.get("/stats", response_model=CacheStatsResponse)
async def get_cache_stats() -> CacheStatsResponse:
    """Retrieve operational statistics from Redis Vector Search index and memory fallback."""
    raw_stats = await semantic_cache.get_stats()
    tokenops_summary = await tokenops_service.get_summary()

    return CacheStatsResponse(
        index_name=raw_stats["index_name"],
        total_documents=raw_stats["total_documents"],
        cache_hits=tokenops_summary["cache_hits"],
        cache_misses=tokenops_summary["cache_misses"],
        hit_ratio=tokenops_summary["cache_hit_ratio"],
        similarity_threshold=raw_stats["similarity_threshold"],
        ttl_seconds=raw_stats["ttl_seconds"],
        redis_connected=raw_stats["redis_connected"],
    )


@router.post("/purge", response_model=CachePurgeResponse)
async def purge_cache() -> CachePurgeResponse:
    """Clear all vector documents and cached prompts."""
    purged_count = await semantic_cache.purge()
    return CachePurgeResponse(
        purged_keys=purged_count,
        status="success",
        message=f"Purged {purged_count} semantic cache keys from Redis and memory fallback.",
    )


@router.post("/inspect", response_model=CacheInspectResponse)
async def inspect_cache(request: CacheInspectRequest) -> CacheInspectResponse:
    """
    Compute vector embedding for prompt and inspect nearest neighbors in the vector index.
    Useful for testing similarity thresholds and auditing cache behavior.
    """
    embedding_service = get_embedding_service()
    try:
        vector = await embedding_service.embed_query(request.prompt)
        matches = await semantic_cache.find_similar(
            vector=vector,
            threshold=0.0,  # Return nearest neighbors regardless of threshold
            top_k=request.top_k,
        )

        match_items = [
            CacheInspectItem(
                prompt=m["prompt"],
                similarity_score=m["similarity_score"],
                distance=m["distance"],
                model=m["model"],
                tier=m["tier"],
                prompt_tokens=m["prompt_tokens"],
                completion_tokens=m["completion_tokens"],
                created_at=m["created_at"],
            )
            for m in matches
        ]

        return CacheInspectResponse(prompt=request.prompt, matches=match_items)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cache inspection failed: {exc}")
