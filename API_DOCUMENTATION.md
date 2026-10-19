# Enterprise LLM Semantic Caching & TokenOps Gateway - API Documentation

The TokenOps Gateway provides an **OpenAI-compatible drop-in replacement API** with enterprise semantic caching, dynamic model tiering, and comprehensive token/cost observability.

---

## Base URLs
- **Local Dev**: `http://localhost:8000`
- **Prefix**: `/v1` (Root aliases are also supported for zero-configuration compatibility)

---

## 1. LLM Chat Completions

### `POST /v1/chat/completions`
Standard OpenAI Chat Completion endpoint with semantic caching and dynamic model routing.

#### Request Headers
| Header | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `Content-Type` | string | Yes | `application/json` |
| `X-Trace-Id` | string | No | Custom distributed trace ID (auto-generated if omitted) |

#### Request Body (JSON)
```json
{
  "messages": [
    {"role": "system", "content": "You are a helpful enterprise assistant."},
    {"role": "user", "content": "What is the capital of France?"}
  ],
  "temperature": 0.7,
  "max_tokens": 500,
  "similarity_threshold": 0.88,
  "bypass_cache": false,
  "force_tier": null
}
```

#### Gateway-Specific Fields
- `similarity_threshold` *(float, optional)*: Overrides default cosine threshold (`0.88`). Values between `0.0` and `1.0`.
- `bypass_cache` *(boolean, optional, default: false)*: When `true`, forces cache bypass to query upstream LLM directly.
- `force_tier` *(integer, optional)*: Manually locks request to `1` (Fast/Cheap), `2` (Standard), or `3` (Reasoning).

#### Response Headers
| Header | Values | Description |
| :--- | :--- | :--- |
| `X-Cache` | `HIT` or `MISS` | Indicates if prompt was resolved from Redis Vector Cache |
| `X-Similarity-Score` | `0.0000` - `1.0000` | Present on cache `HIT` |
| `X-Routed-Model` | `gpt-4o-mini`, `gpt-4o`, `o1-mini` | Upstream model selected |
| `X-Tier` | `1`, `2`, `3` | Selected model tier |
| `X-Trace-Id` | UUID string | Distributed trace identifier |
| `X-Gateway-Time-Ms` | float | Total round-trip latency inside gateway |

#### Response Body (JSON)
```json
{
  "id": "chatcmpl-cache-7a8f9c12b4e5",
  "object": "chat.completion",
  "created": 1740000000,
  "model": "gpt-4o-mini",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The capital of France is Paris."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 15,
    "completion_tokens": 7,
    "total_tokens": 22
  },
  "tokenops": {
    "trace_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "cache_hit": true,
    "similarity_score": 0.9521,
    "model_requested": null,
    "model_routed": "gpt-4o-mini",
    "model_tier": 1,
    "tokens_saved": 22,
    "actual_cost_usd": 0.0,
    "baseline_cost_usd": 0.0001075,
    "cost_saved_usd": 0.0001075,
    "latency": {
      "embedding_ms": 2.15,
      "cache_lookup_ms": 1.42,
      "upstream_llm_ms": 0.0,
      "total_gateway_ms": 3.57
    },
    "routing_reason": "Semantic Cache Hit",
    "complexity_score": 0.12
  }
}
```

---

## 2. Direct Prompt Generation

### `POST /v1/generate`
Convenience endpoint accepting raw prompt strings.

#### Request Body
```json
{
  "prompt": "Explain semantic caching in two sentences.",
  "temperature": 0.7,
  "bypass_cache": false
}
```

---

## 3. Semantic Cache Administration

### `GET /v1/cache/stats`
Returns operational metrics from the Redis Vector Search index.

#### Response Body
```json
{
  "index_name": "idx:llm_semantic_cache",
  "total_documents": 412,
  "cache_hits": 890,
  "cache_misses": 530,
  "hit_ratio": 0.6268,
  "similarity_threshold": 0.88,
  "ttl_seconds": 86400,
  "redis_connected": true
}
```

---

### `POST /v1/cache/purge`
Purges all semantic cache vector records.

#### Response Body
```json
{
  "purged_keys": 412,
  "status": "success",
  "message": "Purged 412 semantic cache keys from Redis and memory fallback."
}
```

---

### `POST /v1/cache/inspect`
Evaluates vector cosine proximity between input text and vectors currently stored in Redis.

#### Request Body
```json
{
  "prompt": "What is France's capital city?",
  "top_k": 3
}
```

#### Response Body
```json
{
  "prompt": "What is France's capital city?",
  "matches": [
    {
      "prompt": "What is the capital of France?",
      "similarity_score": 0.9412,
      "distance": 0.0588,
      "model": "gpt-4o-mini",
      "tier": 1,
      "prompt_tokens": 14,
      "completion_tokens": 7,
      "created_at": 1740000000.0
    }
  ]
}
```

---

## 4. TokenOps Observability & Pricing

### `GET /v1/tokenops/summary`
Executive report aggregating token counts, financial savings, and tier allocations.

#### Response Body
```json
{
  "total_requests": 1420,
  "cache_hits": 890,
  "cache_misses": 530,
  "cache_hit_ratio": 0.6268,
  "total_tokens_processed": 1450200,
  "tokens_saved_by_cache": 912400,
  "total_spend_usd": 1.3412,
  "total_savings_usd": 7.4520,
  "savings_percentage": 84.75,
  "tier_distribution": {
    "tier_1": 420,
    "tier_2": 85,
    "tier_3": 25
  }
}
```

---

### `GET /v1/tokenops/models`
Returns the active per-million pricing table and routing threshold boundaries.

---

### `GET /metrics`
Standard Prometheus scraping endpoint.

#### Sample Prometheus Output:
```
# HELP tokenops_requests_total Total incoming LLM requests processed by the gateway
# TYPE tokenops_requests_total counter
tokenops_requests_total{cache_hit="true",endpoint="/v1/chat/completions",model_routed="gpt-4o-mini"} 890.0
tokenops_requests_total{cache_hit="false",endpoint="/v1/chat/completions",model_routed="gpt-4o"} 530.0

# HELP tokenops_tokens_saved_total Total tokens saved due to semantic cache hits
# TYPE tokenops_tokens_saved_total counter
tokenops_tokens_saved_total 912400.0

# HELP tokenops_cost_saved_usd_total Total dollar cost saved through semantic caching and dynamic model tiering
# TYPE tokenops_cost_saved_usd_total counter
tokenops_cost_saved_usd_total 7.4520
```

---

## 5. Health & Orchestration Probes

### `GET /health`
Liveness probe for container orchestrators (Kubernetes, ECS).
- Status code: `200 OK`
- Output: `{"status": "healthy", "service": "...", "version": "1.0.0"}`

### `GET /ready`
Readiness probe verifying Redis connection and vector index availability.
- Status code: `200 OK`
- Output: `{"status": "ready", "details": {"redis_connected": true, ...}}`

---

## 6. Client Integration Examples

### Python (OpenAI SDK)
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed-for-gateway",
)

response = client.chat.completions.create(
    model="auto",  # Gateway router determines optimal tier
    messages=[{"role": "user", "content": "Explain vector indexing"}],
)

print(response.choices[0].message.content)
```

### JavaScript / TypeScript
```javascript
const response = await fetch("http://localhost:8000/v1/chat/completions", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-Trace-Id": "client-trace-101",
  },
  body: JSON.stringify({
    messages: [{ role: "user", content: "What is quantum computing?" }],
    temperature: 0.7,
  }),
});

const data = await response.json();
console.log("Cached:", response.headers.get("X-Cache"));
console.log("Model Routed:", response.headers.get("X-Routed-Model"));
console.log("Content:", data.choices[0].message.content);
```
