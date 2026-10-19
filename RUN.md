# Enterprise LLM Semantic Caching & TokenOps Gateway - Run & Deployment Guide

This guide provides step-by-step instructions for running, testing, and deploying the gateway locally and in enterprise production environments.

---

## 1. Quick Start: Docker Compose (Recommended)

The fastest and most reliable way to run the complete stack (FastAPI Gateway + Redis Stack with RediSearch vector indexing + RedisInsight Web GUI) is via Docker Compose.

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) (v24.0+)
- [Docker Compose](https://docs.docker.com/compose/) (v2.20+)

### Steps
1. Open a terminal and navigate to the project directory:
   ```bash
   cd "c:/Users/HP/Documents/Exquisapps/ID's/lekeOmotayo/kilo"
   ```

2. Build and start the containers:
   ```bash
   docker compose up --build
   ```

3. Wait until both containers report healthy:
   - `tokenops-redis`: Serving RediSearch on port `6379`, RedisInsight on port `8001`.
   - `tokenops-gateway`: Serving FastAPI and the Web Dashboard on port `8000`.

4. Access the services:
   | Service | URL | Description |
   | :--- | :--- | :--- |
   | **TokenOps Web Cockpit** | `http://localhost:8000` | Interactive prompt playground, live KPI cards, and cache inspector |
   | **Swagger UI** | `http://localhost:8000/docs` | Interactive OpenAPI documentation |
   | **ReDoc** | `http://localhost:8000/redoc` | Clean API reference docs |
   | **Prometheus Metrics** | `http://localhost:8000/metrics` | Prometheus telemetry scraping endpoint |
   | **Health Check** | `http://localhost:8000/health` | Container liveness probe |
   | **Readiness Check** | `http://localhost:8000/ready` | Redis connection and vector index readiness probe |
   | **RedisInsight GUI** | `http://localhost:8001` | Visual Redis key browser and vector index inspector |

5. To stop the containers:
   ```bash
   docker compose down
   ```

---

## 2. Local Manual Setup (Python Virtual Environment)

If you prefer to run the gateway natively on your machine without Docker:

### Prerequisites
- Python 3.11 or Python 3.12
- Running Redis Stack instance with RediSearch (or standard Redis with memory fallback)

### Step 1: Create and Activate Virtual Environment
```bash
cd "c:/Users/HP/Documents/Exquisapps/ID's/lekeOmotayo/kilo"

# Create virtual environment
python -m venv .venv

# Activate on Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Or Windows (Command Prompt):
.venv\Scripts\activate.bat
# Or macOS/Linux:
source .venv/bin/activate
```

### Step 2: Install Dependencies
```bash
# Install core and development requirements
pip install --upgrade pip
pip install -r requirements-dev.txt
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Adjust settings in `.env` as needed:
```ini
# For offline local development (zero external dependencies):
EMBEDDING_PROVIDER=deterministic
UPSTREAM_PROVIDER=mock
REDIS_URL=redis://localhost:6379

# For live OpenAI API execution:
# EMBEDDING_PROVIDER=openai
# UPSTREAM_PROVIDER=openai
# OPENAI_API_KEY=sk-proj-your-actual-api-key
```

### Step 4: Run the FastAPI Development Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 3. Running the Comprehensive Pytest Test Suites

The test suite includes unit tests for mathematical vector similarity, model complexity scoring, pricing calculations, structured JSON logging, and full HTTP integration tests.

```bash
# Run all tests
pytest

# Run tests with verbose output and coverage report
pytest -v --cov=app --cov-report=term-missing

# Run individual test domains:
pytest tests/test_router.py      # Intelligent model-tiering & complexity engine
pytest tests/test_cache.py       # Redis vector search cosine similarity & TTL
pytest tests/test_tokenops.py    # Per-model pricing math & telemetry aggregation
pytest tests/test_logging.py     # Structured JSON logging schema assertions
pytest tests/test_api_chat.py    # OpenAI-compatible /v1/chat/completions lifecycle
pytest tests/test_api_admin.py   # Admin, health, inspect, and dashboard UI tests
pytest tests/test_embeddings.py  # Vector dimensions, norms, and cosine math
```

---

## 4. Testing the Gateway via cURL

### Test 1: First Inbound Request (Cache MISS)
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: trace-enterprise-demo-001" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is the capital of France?"}
    ],
    "temperature": 0.7
  }'
```
**Expected Headers**:
- `X-Cache: MISS`
- `X-Routed-Model: gpt-4o-mini`
- `X-Tier: 1`
- `X-Trace-Id: trace-enterprise-demo-001`
- `X-Gateway-Time-Ms: <latency>`

### Test 2: Repeat Same Request (Cache HIT)
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is the capital of France?"}
    ]
  }'
```
**Expected Headers**:
- `X-Cache: HIT`
- `X-Similarity-Score: 1.0000` (or >= 0.88)
- Response body contains `tokenops.tokens_saved > 0` and `tokenops.cost_saved_usd > 0`.

### Test 3: Bypass Cache
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is the capital of France?"}],
    "bypass_cache": true
  }'
```
**Expected Header**: `X-Cache: MISS`

### Test 4: Check TokenOps Executive Financial Summary
```bash
curl -X GET http://localhost:8000/v1/tokenops/summary
```

### Test 5: Purge Semantic Cache
```bash
curl -X POST http://localhost:8000/v1/cache/purge
```

---

## 5. Production Deployment Architecture

### Environment Variables Reference
| Variable | Default | Description |
| :--- | :--- | :--- |
| `REDIS_URL` | `redis://localhost:6379` | Connection URI for Redis Stack / Enterprise |
| `REDIS_INDEX_NAME` | `idx:llm_semantic_cache` | RediSearch vector index name |
| `REDIS_PREFIX` | `cache:llm:` | Redis key prefix for cached vectors |
| `VECTOR_DIMENSION` | `1536` | Embedding vector dimensionality |
| `SIMILARITY_THRESHOLD`| `0.88` | Cosine similarity threshold for cache hit |
| `CACHE_TTL_SECONDS` | `86400` | Expiration TTL for cached queries (24 hours) |
| `CACHE_ENABLED` | `true` | Master switch for semantic caching |
| `EMBEDDING_PROVIDER` | `deterministic` | `openai` or `deterministic` (offline simulation) |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model name |
| `OPENAI_API_KEY` | `null` | Bearer API token for upstream provider |
| `ROUTING_ENABLED` | `true` | Enables multi-signal model-tiering router |
| `DEFAULT_BASELINE_MODEL` | `gpt-4o` | Baseline model used to calculate cost savings |
| `TIER_1_MODEL` | `gpt-4o-mini` | Low-cost, fast model for lightweight queries |
| `TIER_2_MODEL` | `gpt-4o` | Balanced flagship model for standard queries |
| `TIER_3_MODEL` | `o1-mini` | Heavy reasoning model for complex queries |
| `UPSTREAM_PROVIDER` | `mock` | `openai` or `mock` (resilient test provider) |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

### Deployment Option A: Cloud Containers (Google Cloud Run / AWS ECS / Azure Container Apps)

1. Build and tag the Docker image:
   ```bash
   docker build -t your-org/tokenops-gateway:v1.0.0 .
   ```

2. Push to your container registry (ECR, GCR, Docker Hub):
   ```bash
   docker push your-org/tokenops-gateway:v1.0.0
   ```

3. Deploy container with environment variables pointing to managed Redis (e.g., Redis Cloud, AWS ElastiCache, or GCP Memorystore with vector search enabled):
   - Set `REDIS_URL=rediss://user:password@redis-host:6379`
   - Set `OPENAI_API_KEY=sk-...`
   - Set `EMBEDDING_PROVIDER=openai`
   - Set `UPSTREAM_PROVIDER=openai`

---

### Deployment Option B: Kubernetes

Example Kubernetes manifest:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tokenops-gateway
  labels:
    app: tokenops-gateway
spec:
  replicas: 3
  selector:
    matchLabels:
      app: tokenops-gateway
  template:
    metadata:
      labels:
        app: tokenops-gateway
    spec:
      containers:
      - name: gateway
        image: your-org/tokenops-gateway:v1.0.0
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: tokenops-secrets
        - configMapRef:
            name: tokenops-config
        resources:
          requests:
            cpu: "250m"
            memory: "512Mi"
          limits:
            cpu: "1000m"
            memory: "1Gi"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 20
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: tokenops-gateway-service
spec:
  type: ClusterIP
  selector:
    app: tokenops-gateway
  ports:
  - port: 80
    targetPort: 8000
```

---

### Production Best Practices & Security
1. **Container Security**: The provided `Dockerfile` creates and runs under non-root user `appuser` (UID 10001).
2. **Graceful Fail-Open**: In the unlikely event of Redis connectivity issues, the gateway automatically falls open, allowing LLM traffic to proceed uninterrupted via in-memory vector cache or direct routing.
3. **Structured Log Ingestion**: All logs are emitted to `stdout` in valid JSON with `trace_id` fields, directly indexable by Datadog, Elasticsearch, Logstash, FluentBit, and CloudWatch.
4. **Prometheus Scraping**: Configure your Prometheus server to scrape `http://tokenops-gateway:8000/metrics` every 15s to capture request latencies, cache hit ratios, and real-time financial savings.
