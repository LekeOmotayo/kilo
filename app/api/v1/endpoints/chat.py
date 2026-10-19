"""Chat completion and text generation endpoints with semantic caching and dynamic routing."""

import time
import uuid
from typing import List, Optional
from fastapi import APIRouter, Header, HTTPException, Request, Response

from app.core.config import settings
from app.core.logging import log_tokenops_request, trace_id_ctx
from app.core.pricing import calculate_tokenops_metrics
from app.models.schemas import (
    ChatChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    GenerateRequest,
    LatencyBreakdown,
    TokenOpsMetadata,
    UsageInfo,
)
from app.services.cache import semantic_cache
from app.services.embeddings import get_embedding_service
from app.services.llm_client import llm_client
from app.services.router import router_service
from app.services.tokenops import tokenops_service

router = APIRouter()


def extract_canonical_prompt(messages: List[ChatMessage]) -> str:
    """Concatenate messages into normalized prompt string for embedding and similarity lookup."""
    lines = []
    for msg in messages:
        lines.append(f"{msg.role.upper()}: {msg.content.strip()}")
    return "\n".join(lines).strip()


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def create_chat_completion(
    request: ChatCompletionRequest,
    fastapi_req: Request,
    response: Response,
    x_trace_id: Optional[str] = Header(None),
) -> ChatCompletionResponse:
    """
    OpenAI-compatible Chat Completion endpoint with semantic caching and model tiering.
    
    1. Intercepts incoming conversation and computes prompt vector embedding.
    2. Performs Redis Vector Search evaluating cosine similarity against cached queries.
    3. If similarity >= threshold: returns cached response immediately (0 upstream cost, ultra-low latency).
    4. If cache miss: evaluates prompt complexity & token volume, routes to optimal model tier, calls upstream,
       and asynchronously persists embedding into Redis vector cache.
    """
    start_total = time.perf_counter()
    trace_id = x_trace_id or str(uuid.uuid4())
    trace_id_ctx.set(trace_id)

    prompt_text = extract_canonical_prompt(request.messages)
    if not prompt_text:
        raise HTTPException(status_code=400, detail="Empty conversation messages provided.")

    embedding_service = get_embedding_service()
    cached_match = None
    prompt_vector = None

    t0_embed = time.perf_counter()
    embedding_ms = 0.0
    cache_lookup_ms = 0.0
    upstream_llm_ms = 0.0

    # Step 1: Semantic Caching Pipeline
    if settings.CACHE_ENABLED and not request.bypass_cache:
        try:
            # Generate embedding vector
            prompt_vector = await embedding_service.embed_query(prompt_text)
            embedding_ms = (time.perf_counter() - t0_embed) * 1000.0

            # Redis Vector Search
            t0_lookup = time.perf_counter()
            threshold = request.similarity_threshold or settings.SIMILARITY_THRESHOLD
            matches = await semantic_cache.find_similar(
                vector=prompt_vector,
                threshold=threshold,
                top_k=1,
            )
            cache_lookup_ms = (time.perf_counter() - t0_lookup) * 1000.0

            if matches:
                cached_match = matches[0]
        except Exception as exc:
            # Fail-open: cache errors should never break the critical user path
            cache_lookup_ms = (time.perf_counter() - t0_embed) * 1000.0

    # Step 2: Handle Semantic Cache HIT
    if cached_match:
        total_gateway_ms = (time.perf_counter() - start_total) * 1000.0
        routed_model = cached_match["model"]
        routed_tier = cached_match["tier"]
        sim_score = cached_match["similarity_score"]
        p_tokens = cached_match["prompt_tokens"]
        c_tokens = cached_match["completion_tokens"]

        tokenops_data = calculate_tokenops_metrics(
            baseline_model=settings.DEFAULT_BASELINE_MODEL,
            routed_model=routed_model,
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            cache_hit=True,
        )

        latency_breakdown = LatencyBreakdown(
            embedding_ms=round(embedding_ms, 2),
            cache_lookup_ms=round(cache_lookup_ms, 2),
            upstream_llm_ms=0.0,
            total_gateway_ms=round(total_gateway_ms, 2),
        )

        # Record telemetry & structured audit log
        await tokenops_service.record_request(
            endpoint="/v1/chat/completions",
            model_routed=routed_model,
            model_tier=routed_tier,
            cache_hit=True,
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            tokens_saved=tokenops_data["tokens_saved"],
            actual_cost_usd=tokenops_data["actual_cost_usd"],
            cost_saved_usd=tokenops_data["cost_saved_usd"],
            total_latency_seconds=total_gateway_ms / 1000.0,
        )

        log_tokenops_request(
            trace_id=trace_id,
            endpoint="/v1/chat/completions",
            model_requested=request.model,
            model_routed=routed_model,
            model_tier=routed_tier,
            cache_hit=True,
            similarity_score=sim_score,
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            total_tokens=tokenops_data["total_tokens"],
            tokens_saved=tokenops_data["tokens_saved"],
            actual_cost_usd=tokenops_data["actual_cost_usd"],
            baseline_cost_usd=tokenops_data["baseline_cost_usd"],
            cost_saved_usd=tokenops_data["cost_saved_usd"],
            latency_breakdown_ms=latency_breakdown.model_dump(),
            routing_reason="Semantic Cache Hit (Redis Vector Similarity)",
        )

        response.headers["X-Cache"] = "HIT"
        response.headers["X-Similarity-Score"] = f"{sim_score:.4f}"
        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Latency-Ms"] = f"{total_gateway_ms:.2f}"
        response.headers["X-Routed-Model"] = routed_model
        response.headers["X-Tier"] = str(routed_tier)

        return ChatCompletionResponse(
            id=f"chatcmpl-cache-{uuid.uuid4().hex[:12]}",
            created=int(time.time()),
            model=routed_model,
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=cached_match["response"]),
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                total_tokens=p_tokens + c_tokens,
            ),
            tokenops=TokenOpsMetadata(
                trace_id=trace_id,
                cache_hit=True,
                similarity_score=round(sim_score, 4),
                model_requested=request.model,
                model_routed=routed_model,
                model_tier=routed_tier,
                tokens_saved=tokenops_data["tokens_saved"],
                actual_cost_usd=tokenops_data["actual_cost_usd"],
                baseline_cost_usd=tokenops_data["baseline_cost_usd"],
                cost_saved_usd=tokenops_data["cost_saved_usd"],
                latency=latency_breakdown,
                routing_reason="Semantic Cache Hit",
            ),
        )

    # Step 3: Cache MISS -> Intelligent Model-Tiering & Upstream Dispatch
    routing_decision = router_service.route_prompt(
        prompt=prompt_text,
        requested_model=request.model,
        force_tier=request.force_tier,
    )

    t0_llm = time.perf_counter()
    llm_resp = await llm_client.generate_chat_completion(
        messages=request.messages,
        model=routing_decision.model,
        temperature=request.temperature or 0.7,
        max_tokens=request.max_tokens,
    )
    upstream_llm_ms = (time.perf_counter() - t0_llm) * 1000.0

    # Step 4: Asynchronously populate Semantic Cache for future queries
    if settings.CACHE_ENABLED and not request.bypass_cache:
        try:
            if prompt_vector is None:
                prompt_vector = await embedding_service.embed_query(prompt_text)
            await semantic_cache.store(
                prompt=prompt_text,
                vector=prompt_vector,
                response=llm_resp.content,
                model=routing_decision.model,
                tier=routing_decision.tier,
                prompt_tokens=llm_resp.prompt_tokens,
                completion_tokens=llm_resp.completion_tokens,
            )
        except Exception as exc:
            # Non-blocking cache store failure
            pass

    total_gateway_ms = (time.perf_counter() - start_total) * 1000.0
    tokenops_data = calculate_tokenops_metrics(
        baseline_model=settings.DEFAULT_BASELINE_MODEL,
        routed_model=routing_decision.model,
        prompt_tokens=llm_resp.prompt_tokens,
        completion_tokens=llm_resp.completion_tokens,
        cache_hit=False,
    )

    latency_breakdown = LatencyBreakdown(
        embedding_ms=round(embedding_ms, 2),
        cache_lookup_ms=round(cache_lookup_ms, 2),
        upstream_llm_ms=round(upstream_llm_ms, 2),
        total_gateway_ms=round(total_gateway_ms, 2),
    )

    # Record telemetry & structured audit log
    await tokenops_service.record_request(
        endpoint="/v1/chat/completions",
        model_routed=routing_decision.model,
        model_tier=routing_decision.tier,
        cache_hit=False,
        prompt_tokens=llm_resp.prompt_tokens,
        completion_tokens=llm_resp.completion_tokens,
        tokens_saved=0,
        actual_cost_usd=tokenops_data["actual_cost_usd"],
        cost_saved_usd=tokenops_data["cost_saved_usd"],
        total_latency_seconds=total_gateway_ms / 1000.0,
    )

    routing_reason_str = "; ".join(routing_decision.reasons)
    log_tokenops_request(
        trace_id=trace_id,
        endpoint="/v1/chat/completions",
        model_requested=request.model,
        model_routed=routing_decision.model,
        model_tier=routing_decision.tier,
        cache_hit=False,
        similarity_score=None,
        prompt_tokens=llm_resp.prompt_tokens,
        completion_tokens=llm_resp.completion_tokens,
        total_tokens=tokenops_data["total_tokens"],
        tokens_saved=0,
        actual_cost_usd=tokenops_data["actual_cost_usd"],
        baseline_cost_usd=tokenops_data["baseline_cost_usd"],
        cost_saved_usd=tokenops_data["cost_saved_usd"],
        latency_breakdown_ms=latency_breakdown.model_dump(),
        routing_reason=routing_reason_str,
        complexity_score=routing_decision.complexity_score,
    )

    response.headers["X-Cache"] = "MISS"
    response.headers["X-Trace-Id"] = trace_id
    response.headers["X-Latency-Ms"] = f"{total_gateway_ms:.2f}"
    response.headers["X-Routed-Model"] = routing_decision.model
    response.headers["X-Tier"] = str(routing_decision.tier)

    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
        created=int(time.time()),
        model=routing_decision.model,
        choices=[
            ChatChoice(
                index=0,
                message=ChatMessage(role="assistant", content=llm_resp.content),
                finish_reason=llm_resp.finish_reason,
            )
        ],
        usage=UsageInfo(
            prompt_tokens=llm_resp.prompt_tokens,
            completion_tokens=llm_resp.completion_tokens,
            total_tokens=llm_resp.total_tokens,
        ),
        tokenops=TokenOpsMetadata(
            trace_id=trace_id,
            cache_hit=False,
            similarity_score=None,
            model_requested=request.model,
            model_routed=routing_decision.model,
            model_tier=routing_decision.tier,
            tokens_saved=0,
            actual_cost_usd=tokenops_data["actual_cost_usd"],
            baseline_cost_usd=tokenops_data["baseline_cost_usd"],
            cost_saved_usd=tokenops_data["cost_saved_usd"],
            latency=latency_breakdown,
            routing_reason=routing_reason_str,
            complexity_score=routing_decision.complexity_score,
        ),
    )


@router.post("/generate", response_model=ChatCompletionResponse)
async def create_raw_generation(
    request: GenerateRequest,
    fastapi_req: Request,
    response: Response,
    x_trace_id: Optional[str] = Header(None),
) -> ChatCompletionResponse:
    """Convenience endpoint accepting single prompt string and returning completion."""
    chat_req = ChatCompletionRequest(
        model=request.model,
        messages=[ChatMessage(role="user", content=request.prompt)],
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        bypass_cache=request.bypass_cache,
        force_tier=request.force_tier,
    )
    return await create_chat_completion(chat_req, fastapi_req, response, x_trace_id)
