# Kilo — Enterprise LLM Semantic Caching & TokenOps Demo Script

## 1. The 30-Second Elevator Pitch
> *"Over 60% of LLM queries in enterprise applications are redundant or could be served by cheaper models. **Kilo** is a high-throughput TokenOps semantic caching gateway. It intercepts OpenAI-compatible `/v1/chat/completions` requests, runs Redis HNSW vector similarity search against cached prompt embeddings, and returns cache hits in under 5ms with zero token cost. On cache misses, its dynamic router analyzes code density, formal reasoning markers, and token lengths to route queries to the cheapest tier (Tier 1 `gpt-4o-mini`, Tier 2 `gpt-4o`, Tier 3 `o1-mini`), slashing API spend by up to 70%."*

---

## 2. Senior Architecture Deep Dive

```
Client Request -> [FastAPI Gateway]
                         |
                         v
              [Feature Hashing / Embedding]
          (Deterministic offline vector or text-embedding-3-small)
                         |
                         v
              [Redis Vector Store (HNSW / Flat)]
             Threshold check (Cosine Similarity >= 0.88)
                   /                    \
              HIT /                      \ MISS
                 v                        v
      [Instant Response (<5ms)]     [Intelligent Model Router]
      • $0 token consumption       • Tier 1: Low complexity ($0.15/M)
      • Exact savings logged        • Tier 2: Code/Analysis ($2.50/M)
                                    • Tier 3: Reasoning proof ($3.00/M)
                                          |
                                          v
                                    [Upstream LLM Provider]
                                          |
                                          v
                                    [Cache Write-Through]
```

---

## 3. How to Run & Demo

```powershell
Set-Location "C:\Users\HP\Documents\Exquisapps\ID's\lekeOmotayo\kilo"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Open **`http://localhost:8000`** (or `/docs` for Swagger UI).

### Demo Flow:
1. **Show Live KPIs**: Point to the top dashboard ribbon showing **Cache Hit Ratio**, **Cost Savings ($)**, and **Tokens Saved**.
2. **First Query (Cache Miss)**: Send `"Explain how Raft consensus works"`. Show it routing to Tier 2 based on domain terminology.
3. **Second Similar Query (Cache Hit)**: Send `"How does Raft distributed consensus operate?"`. Show the instant sub-5ms cache hit with similarity score `0.92+`, $0 cost, and savings incrementing.
4. **Reasoning Proof Routing**: Send a formal logic proof. Watch the router escalate to Tier 3 (`o1-mini`).

---

## 4. Senior Defense Questions & Answers

### Q: "Why cosine similarity over Euclidean distance for prompt embeddings?"
> **Answer:** *"Cosine similarity measures the angular orientation between prompt vectors rather than magnitude. Long vs short prompts with identical semantic intent produce vectors with identical orientation, preventing prompt verbosity from breaking cache hits."*

### Q: "How does Kilo work in air-gapped or local environments without Redis?"
> **Answer:** *"Kilo includes an in-memory cosine vector store fallback (`InMemoryVectorCache`) and deterministic character-trigram hashing embeddings (`EMBEDDING_PROVIDER=deterministic`). It runs completely offline without external Docker, Redis, or OpenAI keys."*
