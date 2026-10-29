/* ==============================================================================
   TokenOps Gateway - Interactive Client Application Logic
   ============================================================================== */
const API_BASE = window.location.protocol === 'file:' ? 'http://localhost:8090' : '';

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const chatForm = document.getElementById("chat-form");
  const promptInput = document.getElementById("prompt-input");
  const tierSelect = document.getElementById("tier-select");
  const thresholdSlider = document.getElementById("threshold-slider");
  const thresholdVal = document.getElementById("threshold-val");
  const bypassToggle = document.getElementById("bypass-cache-toggle");
  const btnSubmit = document.getElementById("btn-submit");

  const telemetryBanner = document.getElementById("telemetry-banner");
  const badgeCacheStatus = document.getElementById("badge-cache-status");
  const badgeSimilarity = document.getElementById("badge-similarity");
  const badgeModel = document.getElementById("badge-model");
  const badgeTier = document.getElementById("badge-tier");
  const valLatency = document.getElementById("val-latency");
  const valSavedUsd = document.getElementById("val-saved-usd");
  const valTraceId = document.getElementById("val-trace-id");

  const latencyStages = document.getElementById("latency-stages");
  const timeEmbed = document.getElementById("time-embed");
  const timeCache = document.getElementById("time-cache");
  const timeLlm = document.getElementById("time-llm");
  const timeTotal = document.getElementById("time-total");

  const responseOutput = document.getElementById("response-output");
  const btnCopyResponse = document.getElementById("btn-copy-response");
  const btnRefreshStats = document.getElementById("btn-refresh-stats");

  // KPI elements
  const kpiHitRatio = document.getElementById("kpi-hit-ratio");
  const kpiHitsCount = document.getElementById("kpi-hits-count");
  const kpiTotalReqs = document.getElementById("kpi-total-reqs");
  const hitRatioBar = document.getElementById("hit-ratio-bar");

  const kpiCostSaved = document.getElementById("kpi-cost-saved");
  const kpiCostSpent = document.getElementById("kpi-cost-spent");
  const kpiSavingsPct = document.getElementById("kpi-savings-pct");
  const savingsBar = document.getElementById("savings-bar");

  const kpiTokensSaved = document.getElementById("kpi-tokens-saved");
  const kpiTokensTotal = document.getElementById("kpi-tokens-total");
  const tokensBar = document.getElementById("tokens-bar");

  const countTier1 = document.getElementById("count-tier-1");
  const countTier2 = document.getElementById("count-tier-2");
  const countTier3 = document.getElementById("count-tier-3");

  const cacheDocsCount = document.getElementById("cache-docs-count");
  const btnPurgeCache = document.getElementById("btn-purge-cache");
  const auditLogList = document.getElementById("audit-log-list");

  // Inspector Elements
  const inspectInput = document.getElementById("inspect-input");
  const btnRunInspect = document.getElementById("btn-run-inspect");
  const inspectResults = document.getElementById("inspect-results");

  const toast = document.getElementById("toast");

  // Presets definition
  const presets = {
    simple: "What is the capital of France and its primary currency?",
    code: "Write an async Python function using FastAPI and Redis vector search to evaluate cosine similarity.",
    reasoning: "Prove step by step why byzantine fault tolerance requires 3f + 1 nodes under formal consensus logic.",
  };

  // Preset Buttons
  document.querySelectorAll(".pill-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const type = btn.dataset.preset;
      if (presets[type]) {
        promptInput.value = presets[type];
        promptInput.focus();
      }
    });
  });

  // Slider change
  thresholdSlider.addEventListener("input", (e) => {
    thresholdVal.textContent = parseFloat(e.target.value).toFixed(2);
  });

  // Tab switching
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));

      btn.classList.add("active");
      const tabId = btn.dataset.tab;
      const target = document.getElementById(tabId);
      if (target) target.classList.add("active");
    });
  });

  // Show Toast Helper
  function showToast(message) {
    toast.textContent = message;
    toast.classList.remove("hidden");
    setTimeout(() => {
      toast.classList.add("hidden");
    }, 3200);
  }

  // Copy buttons
  btnCopyResponse.addEventListener("click", () => {
    if (responseOutput.textContent) {
      navigator.clipboard.writeText(responseOutput.textContent);
      showToast("Completion copied to clipboard!");
    }
  });

  valTraceId.addEventListener("click", () => {
    const rawTrace = valTraceId.dataset.trace;
    if (rawTrace) {
      navigator.clipboard.writeText(rawTrace);
      showToast(`Trace ID copied: ${rawTrace}`);
    }
  });

  // Fetch KPI Stats
  async function refreshStats() {
    try {
      const [sumRes, cacheRes] = await Promise.all([
        fetch(`${API_BASE}/v1/tokenops/summary`),
        fetch(`${API_BASE}/v1/cache/stats`),
      ]);

      if (sumRes.ok && cacheRes.ok) {
        const sum = await sumRes.json();
        const cache = await cacheRes.json();

        // Update Hit Ratio KPI
        const ratioPct = (sum.cache_hit_ratio * 100).toFixed(1);
        kpiHitRatio.textContent = `${ratioPct}%`;
        kpiHitsCount.textContent = sum.cache_hits.toLocaleString();
        kpiTotalReqs.textContent = sum.total_requests.toLocaleString();
        hitRatioBar.style.width = `${Math.min(100, sum.cache_hit_ratio * 100)}%`;

        // Update Cost KPI
        kpiCostSaved.textContent = `$${sum.total_savings_usd.toFixed(4)}`;
        kpiCostSpent.textContent = `$${sum.total_spend_usd.toFixed(4)}`;
        kpiSavingsPct.textContent = `${sum.savings_percentage.toFixed(1)}%`;
        savingsBar.style.width = `${Math.min(100, sum.savings_percentage)}%`;

        // Update Tokens KPI
        kpiTokensSaved.textContent = sum.tokens_saved_by_cache.toLocaleString();
        kpiTokensTotal.textContent = sum.total_tokens_processed.toLocaleString();
        const tokenSavingsRatio = sum.total_tokens_processed > 0
          ? (sum.tokens_saved_by_cache / sum.total_tokens_processed) * 100
          : 0;
        tokensBar.style.width = `${Math.min(100, tokenSavingsRatio)}%`;

        // Update Tier Distribution
        countTier1.textContent = sum.tier_distribution.tier_1 || 0;
        countTier2.textContent = sum.tier_distribution.tier_2 || 0;
        countTier3.textContent = sum.tier_distribution.tier_3 || 0;

        // Update Cache Docs
        cacheDocsCount.textContent = cache.total_documents.toLocaleString();
      }
    } catch (err) {
      console.warn("Could not fetch gateway stats:", err);
    }
  }

  btnRefreshStats.addEventListener("click", refreshStats);

  // Prepend transaction to Recent Audit Log
  function addAuditEntry(item) {
    const emptyNotice = auditLogList.querySelector(".audit-empty");
    if (emptyNotice) emptyNotice.remove();

    const div = document.createElement("div");
    div.className = "audit-item";

    const isHit = item.cache_hit;
    const hitBadgeClass = isHit ? "badge-hit" : "badge-miss";
    const hitText = isHit ? "HIT" : "MISS";

    div.innerHTML = `
      <div class="audit-top">
        <span class="audit-model">${item.model_routed}</span>
        <span class="badge ${hitBadgeClass}">${hitText}</span>
      </div>
      <div class="audit-prompt">${item.prompt}</div>
      <div class="audit-meta">
        <span>${item.latency_ms.toFixed(1)}ms</span>
        <span class="${isHit ? 'text-green' : ''}">+$${item.cost_saved_usd.toFixed(5)} saved</span>
        <span>${new Date().toLocaleTimeString()}</span>
      </div>
    `;

    auditLogList.prepend(div);

    // Limit list length to 15
    while (auditLogList.children.length > 15) {
      auditLogList.removeChild(auditLogList.lastChild);
    }
  }

  // Handle Chat Form Submit
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const prompt = promptInput.value.trim();
    if (!prompt) return;

    btnSubmit.disabled = true;
    btnSubmit.querySelector(".btn-text").textContent = "Processing...";
    responseOutput.classList.remove("empty-state");
    responseOutput.textContent = "Querying semantic cache vector store & routing models...";

    const forceTierVal = tierSelect.value === "auto" ? null : parseInt(tierSelect.value, 10);
    const threshold = parseFloat(thresholdSlider.value);
    const bypassCache = bypassToggle.checked;

    const payload = {
      messages: [{ role: "user", content: prompt }],
      similarity_threshold: threshold,
      bypass_cache: bypassCache,
      force_tier: forceTierVal,
    };

    try {
      const res = await fetch(`${API_BASE}/v1/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errorJson = await res.json().catch(() => ({}));
        throw new Error(errorJson.detail || `Server error: ${res.status}`);
      }

      const data = await res.json();
      const choice = data.choices && data.choices[0];
      const tokenops = data.tokenops;

      // Update response text
      responseOutput.textContent = choice ? choice.message.content : "No response content.";

      // Update Telemetry Banner
      telemetryBanner.classList.remove("hidden");
      latencyStages.classList.remove("hidden");

      if (tokenops.cache_hit) {
        badgeCacheStatus.className = "badge badge-hit";
        badgeCacheStatus.textContent = "CACHE HIT";

        badgeSimilarity.classList.remove("hidden");
        badgeSimilarity.textContent = `Cosine Sim: ${(tokenops.similarity_score * 100).toFixed(1)}%`;
      } else {
        badgeCacheStatus.className = "badge badge-miss";
        badgeCacheStatus.textContent = "CACHE MISS";
        badgeSimilarity.classList.add("hidden");
      }

      badgeModel.textContent = `Model: ${tokenops.model_routed}`;
      badgeTier.textContent = `Tier ${tokenops.model_tier}`;

      valLatency.textContent = `${tokenops.latency.total_gateway_ms.toFixed(1)} ms`;
      valSavedUsd.textContent = `+$${tokenops.cost_saved_usd.toFixed(5)}`;

      valTraceId.textContent = `Trace: ${tokenops.trace_id.substring(0, 8)}...`;
      valTraceId.dataset.trace = tokenops.trace_id;

      // Update Latency Breakdown Stages
      timeEmbed.textContent = tokenops.latency.embedding_ms.toFixed(1);
      timeCache.textContent = tokenops.latency.cache_lookup_ms.toFixed(1);
      timeLlm.textContent = tokenops.latency.upstream_llm_ms.toFixed(1);
      timeTotal.textContent = tokenops.latency.total_gateway_ms.toFixed(1);

      // Add to audit stream
      addAuditEntry({
        prompt: prompt,
        model_routed: tokenops.model_routed,
        cache_hit: tokenops.cache_hit,
        latency_ms: tokenops.latency.total_gateway_ms,
        cost_saved_usd: tokenops.cost_saved_usd,
      });

      // Refresh Stats KPIs
      await refreshStats();

    } catch (err) {
      responseOutput.textContent = `Error: ${err.message}`;
      showToast(`Request failed: ${err.message}`);
    } finally {
      btnSubmit.disabled = false;
      btnSubmit.querySelector(".btn-text").textContent = "Send Request";
    }
  });

  // Purge Cache Handler
  btnPurgeCache.addEventListener("click", async () => {
    if (!confirm("Are you sure you want to purge all semantic cache vectors from Redis?")) return;

    try {
      const res = await fetch(`${API_BASE}/v1/cache/purge`, { method: "POST" });
      const data = await res.json();
      showToast(`Cache purged: ${data.purged_keys} keys removed.`);
      await refreshStats();
    } catch (err) {
      showToast(`Purge failed: ${err.message}`);
    }
  });

  // Vector Nearest Neighbor Inspector
  btnRunInspect.addEventListener("click", async () => {
    const q = inspectInput.value.trim();
    if (!q) return;

    inspectResults.innerHTML = "<div class='audit-empty'>Searching nearest vector neighbors...</div>";

    try {
      const res = await fetch(`${API_BASE}/v1/cache/inspect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: q, top_k: 4 }),
      });

      if (!res.ok) throw new Error("Inspection query failed.");
      const data = await res.json();

      if (!data.matches || data.matches.length === 0) {
        inspectResults.innerHTML = "<div class='audit-empty'>No vector neighbors found in cache. Submit queries first.</div>";
        return;
      }

      inspectResults.innerHTML = "";
      data.matches.forEach((m, idx) => {
        const card = document.createElement("div");
        card.className = "inspect-card";
        card.innerHTML = `
          <div class="inspect-card-top">
            <span>Match #${idx + 1} (${m.model})</span>
            <span class="sim-val">${(m.similarity_score * 100).toFixed(2)}% Cosine Sim</span>
          </div>
          <div class="audit-prompt">"${m.prompt}"</div>
          <div class="audit-meta">
            <span>Distance: ${m.distance.toFixed(4)}</span>
            <span>Tokens: ${m.prompt_tokens + m.completion_tokens}</span>
          </div>
        `;
        inspectResults.appendChild(card);
      });
    } catch (err) {
      inspectResults.innerHTML = `<div class='audit-empty text-rose'>Error: ${err.message}</div>`;
    }
  });

  // Initial stats load
  refreshStats();
});
