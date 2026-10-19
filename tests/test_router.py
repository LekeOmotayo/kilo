"""Unit tests for the intelligent model-tiering router."""

import pytest
from app.core.config import settings
from app.services.router import ModelRouter, RoutingDecision


@pytest.fixture
def router():
    return ModelRouter()


def test_simple_prompt_routes_to_tier_1(router):
    """Simple, short factual queries should be routed to Tier 1 (fast/cheap)."""
    prompt = "What is the capital of Nigeria?"
    decision: RoutingDecision = router.route_prompt(prompt)

    assert decision.tier == 1
    assert decision.model == settings.TIER_1_MODEL
    assert decision.complexity_score < settings.COMPLEXITY_THRESHOLD_TIER2
    assert decision.token_count < settings.TIER_1_MAX_TOKENS


def test_code_dense_prompt_routes_to_tier_2(router):
    """Prompts containing code, SQL syntax, or error traces should trigger Tier 2 or higher."""
    prompt = """
    Please review this Python code:
    ```python
    async def fetch_user(db, user_id):
        try:
            query = "SELECT id, name FROM users WHERE id = :id"
            result = await db.execute(query, {"id": user_id})
            return result.fetchone()
        except Exception as e:
            logger.error(f"Failed: {e}")
            raise
    ```
    """
    decision: RoutingDecision = router.route_prompt(prompt)

    assert decision.tier in (2, 3)
    assert decision.signals["code_score"] > 0.3
    assert any("code" in r.lower() for r in decision.reasons)


def test_multi_step_reasoning_routes_to_tier_3(router):
    """Prompts requesting formal proofs, step-by-step logic, and deep analysis route to Tier 3."""
    prompt = (
        "Prove that the Halting Problem is undecidable using formal logic and syllogism. "
        "Explain step by step the mathematical proof and derive the algorithmic complexity "
        "and architecture trade-offs for distributed consensus under byzantine fault tolerance."
    )
    decision: RoutingDecision = router.route_prompt(prompt)

    assert decision.tier == 3
    assert decision.model == settings.TIER_3_MODEL
    assert decision.complexity_score >= settings.COMPLEXITY_THRESHOLD_TIER3
    assert any("reasoning" in r.lower() or "complexity" in r.lower() for r in decision.reasons)


def test_high_token_volume_escalates_to_tier_3(router):
    """Large prompts exceeding TIER_2_MAX_TOKENS escalate to Tier 3 even if simple text."""
    # Generate long text that exceeds TIER_2_MAX_TOKENS (2500 tokens ~ 10,000 chars)
    prompt = "This is an enterprise log line and context item. " * 300
    decision: RoutingDecision = router.route_prompt(prompt)

    assert decision.token_count > settings.TIER_2_MAX_TOKENS
    assert decision.tier == 3
    assert decision.model == settings.TIER_3_MODEL
    assert any("exceeds" in r for r in decision.reasons)


def test_explicit_model_override(router):
    """When a caller requests a specific model name, the router respects it."""
    prompt = "Hi there"
    decision: RoutingDecision = router.route_prompt(prompt, requested_model="gpt-4o")

    assert decision.model == "gpt-4o"
    assert decision.tier == 2
    assert "Explicit model requested" in decision.reasons[0]


def test_forced_tier_override(router):
    """When force_tier is supplied, it overrides complexity evaluation."""
    complex_prompt = "Prove step by step using mathematical proof and code ```def f(): pass```"
    # Force down to tier 1
    decision: RoutingDecision = router.route_prompt(complex_prompt, force_tier=1)

    assert decision.tier == 1
    assert decision.model == settings.TIER_1_MODEL
    assert "Caller enforced tier override" in decision.reasons[0]


def test_router_edge_cases(router):
    """Verify router handles empty, single character, and whitespace gracefully."""
    empty_decision = router.route_prompt("")
    assert empty_decision.tier == 1
    assert empty_decision.token_count == 0
    assert empty_decision.complexity_score == 0.0

    whitespace_decision = router.route_prompt("   \n\t  ")
    assert whitespace_decision.tier == 1
    assert whitespace_decision.token_count == 0

    single_char_decision = router.route_prompt("?")
    assert single_char_decision.tier == 1
    assert single_char_decision.token_count >= 1
