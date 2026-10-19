"""Pydantic schemas for the LLM Semantic Caching & TokenOps Gateway."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Chat completion message."""
    role: str = Field(..., description="Message author role: system, user, or assistant")
    content: str = Field(..., description="Content text of the message")
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request schema."""
    model: Optional[str] = Field(default=None, description="Requested model (optional; router decides if omitted)")
    messages: List[ChatMessage] = Field(..., min_length=1, description="List of messages in conversation")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    stream: Optional[bool] = Field(default=False)
    user: Optional[str] = Field(default=None)
    # Gateway-specific controls
    similarity_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    bypass_cache: Optional[bool] = Field(default=False)
    force_tier: Optional[int] = Field(default=None, ge=1, le=3)


class GenerateRequest(BaseModel):
    """Direct prompt generation request schema."""
    prompt: str = Field(..., min_length=1, description="Raw input prompt")
    model: Optional[str] = Field(default=None)
    temperature: Optional[float] = Field(default=0.7)
    max_tokens: Optional[int] = Field(default=None)
    bypass_cache: Optional[bool] = Field(default=False)
    force_tier: Optional[int] = Field(default=None, ge=1, le=3)


class UsageInfo(BaseModel):
    """Token usage metrics."""
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)


class LatencyBreakdown(BaseModel):
    """Latency breakdown across pipeline stages in milliseconds."""
    embedding_ms: float = 0.0
    cache_lookup_ms: float = 0.0
    upstream_llm_ms: float = 0.0
    total_gateway_ms: float = 0.0


class TokenOpsMetadata(BaseModel):
    """TokenOps enterprise observability metadata."""
    trace_id: str
    cache_hit: bool
    similarity_score: Optional[float] = None
    model_requested: Optional[str] = None
    model_routed: str
    model_tier: int
    tokens_saved: int
    actual_cost_usd: float
    baseline_cost_usd: float
    cost_saved_usd: float
    latency: LatencyBreakdown
    routing_reason: Optional[str] = None
    complexity_score: Optional[float] = None


class ChatChoice(BaseModel):
    """Individual completion choice."""
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response with TokenOps metadata."""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: UsageInfo
    tokenops: TokenOpsMetadata


class CacheStatsResponse(BaseModel):
    """Semantic cache operational stats."""
    index_name: str
    total_documents: int
    cache_hits: int
    cache_misses: int
    hit_ratio: float
    similarity_threshold: float
    ttl_seconds: int
    redis_connected: bool


class CachePurgeResponse(BaseModel):
    """Semantic cache purge result."""
    purged_keys: int
    status: str = "success"
    message: str


class CacheInspectRequest(BaseModel):
    """Request to inspect nearest neighbors in semantic cache."""
    prompt: str = Field(..., min_length=1)
    top_k: int = Field(default=3, ge=1, le=10)


class CacheMatchItem(BaseModel):
    """Single matching entry from semantic cache."""
    prompt: str
    similarity_score: float
    distance: float
    model: str
    tier: int
    prompt_tokens: int
    completion_tokens: int
    created_at: float


class CacheInspectResponse(BaseModel):
    """Results of cache nearest neighbor inspection."""
    prompt: str
    matches: List[CacheMatchItem]


class TokenOpsSummaryResponse(BaseModel):
    """Executive financial & operational TokenOps dashboard summary."""
    total_requests: int
    cache_hits: int
    cache_misses: int
    cache_hit_ratio: float
    total_tokens_processed: int
    tokens_saved_by_cache: int
    total_spend_usd: float
    total_savings_usd: float
    savings_percentage: float
    tier_distribution: Dict[str, int]
