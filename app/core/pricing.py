"""Model pricing table and TokenOps cost calculation utilities."""

from typing import Dict, Tuple

# Pricing in USD per 1,000,000 tokens (Standard enterprise rates as of 2024-2025)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # Tier 1 - Fast / Lightweight
    "gpt-4o-mini": {
        "input_per_m": 0.15,
        "output_per_m": 0.60,
    },
    "claude-3-haiku": {
        "input_per_m": 0.25,
        "output_per_m": 1.25,
    },
    # Tier 2 - Standard / Flagship
    "gpt-4o": {
        "input_per_m": 2.50,
        "output_per_m": 10.00,
    },
    "claude-3-5-sonnet": {
        "input_per_m": 3.00,
        "output_per_m": 15.00,
    },
    # Tier 3 - Heavy Reasoning
    "o1-mini": {
        "input_per_m": 3.00,
        "output_per_m": 12.00,
    },
    "o1": {
        "input_per_m": 15.00,
        "output_per_m": 60.00,
    },
    "claude-3-opus": {
        "input_per_m": 15.00,
        "output_per_m": 75.00,
    },
    # Default fallback rate
    "default": {
        "input_per_m": 2.50,
        "output_per_m": 10.00,
    },
}

# Embedding pricing per 1M tokens
EMBEDDING_PRICING: Dict[str, float] = {
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
    "text-embedding-ada-002": 0.10,
    "deterministic": 0.0,
    "default": 0.02,
}


def get_model_rates(model_name: str) -> Tuple[float, float]:
    """Retrieve (input_rate_per_m, output_rate_per_m) for a model name."""
    clean_name = model_name.lower().strip()
    for key, rate in MODEL_PRICING.items():
        if key in clean_name:
            return rate["input_per_m"], rate["output_per_m"]
    default_rate = MODEL_PRICING["default"]
    return default_rate["input_per_m"], default_rate["output_per_m"]


def calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate the dollar cost of prompt and completion tokens."""
    in_rate, out_rate = get_model_rates(model_name)
    input_cost = (prompt_tokens / 1_000_000.0) * in_rate
    output_cost = (completion_tokens / 1_000_000.0) * out_rate
    return round(input_cost + output_cost, 8)


def calculate_tokenops_metrics(
    baseline_model: str,
    routed_model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cache_hit: bool,
) -> Dict[str, float]:
    """
    Calculate full TokenOps financial metrics.
    
    If cache_hit is True:
        Actual cost = $0 (upstream call avoided)
        Estimated baseline cost = what it would have cost using baseline_model
        Cost saved = Estimated baseline cost
        Tokens saved = prompt_tokens + completion_tokens
    If cache_hit is False:
        Actual cost = what it cost on routed_model
        Estimated baseline cost = what it would have cost using baseline_model
        Cost saved = max(0.0, baseline cost - actual cost)
        Tokens saved = 0
    """
    total_tokens = prompt_tokens + completion_tokens
    baseline_cost = calculate_cost(baseline_model, prompt_tokens, completion_tokens)

    if cache_hit:
        actual_cost = 0.0
        cost_saved = baseline_cost
        tokens_saved = total_tokens
    else:
        actual_cost = calculate_cost(routed_model, prompt_tokens, completion_tokens)
        cost_saved = max(0.0, round(baseline_cost - actual_cost, 8))
        tokens_saved = 0

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "tokens_saved": tokens_saved,
        "baseline_cost_usd": baseline_cost,
        "actual_cost_usd": actual_cost,
        "cost_saved_usd": cost_saved,
    }
