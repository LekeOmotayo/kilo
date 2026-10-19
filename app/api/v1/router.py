"""Aggregated API v1 Router."""

from fastapi import APIRouter

from app.api.v1.endpoints import cache_admin, chat, health, tokenops_admin

api_v1_router = APIRouter()

# Core LLM gateway endpoints (chat completions and generation)
api_v1_router.include_router(chat.router, tags=["LLM Gateway"])

# Semantic cache administrative and inspection endpoints
api_v1_router.include_router(cache_admin.router, prefix="/cache", tags=["Semantic Cache Admin"])

# TokenOps financial analytics and metrics endpoints
api_v1_router.include_router(tokenops_admin.router, prefix="/tokenops", tags=["TokenOps Analytics"])

# System health probes
api_v1_router.include_router(health.router, tags=["Health"])
