"""Intelligent model-tiering router evaluating prompt complexity and token length."""

import re
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import logger


class RoutingDecision(BaseModel):
    """Result of prompt routing evaluation."""
    model: str
    tier: int
    complexity_score: float
    token_count: int
    reasons: List[str]
    signals: Dict[str, float] = Field(default_factory=dict)


class ModelRouter:
    """
    Enterprise Model-Tiering Engine.
    
    Evaluates prompt complexity, structural features, and token volume to route
    inbound requests to the optimal model tier (Tier 1: Fast/Cheap, Tier 2: Standard, Tier 3: Reasoning).
    """

    # Regex patterns for code synthesis, debugging, and programming markers
    CODE_PATTERNS = [
        r"```[\s\S]*?```",                                     # Code fences
        r"\b(def|class|function|const|let|var|async|await)\b",  # Code keywords
        r"\b(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|JOIN)\b",   # SQL keywords
        r"[{};]\s*$",                                          # Trailing syntax punctuation
        r"\b(try|catch|except|raise|throw|traceback|import)\b", # Exception / module syntax
        r"(==|!=|<=|>=|=>|->|\+\+|--|&&|\|\|)",                # Syntax operators
    ]

    # Reasoning, analytical deduction, and mathematical indicators
    REASONING_PATTERNS = [
        r"\b(step[-\s]by[-\s]step|think step by step)\b",
        r"\b(prove that|proof|derive|mathematical proof)\b",
        r"\b(root cause|analyze the trade-offs|compare and contrast)\b",
        r"\b(algorithmic complexity|big o|o\(n\)|dynamic programming)\b",
        r"\b(deduce|infer|formal logic|premises|syllogism)\b",
        r"\b(architecture trade-offs|concurrency race condition|deadlock)\b",
    ]

    # Technical and domain-specific enterprise vocabulary
    DOMAIN_TERMS = [
        r"\b(kubernetes|docker|microservices|distributed systems|byzantine)\b",
        r"\b(consensus|raft|paxos|idempotency|cap theorem)\b",
        r"\b(cryptography|aes-256|sha-256|public key|rsa|elliptic curve)\b",
        r"\b(compliance|gdpr|hipaa|sox|pci-dss|liability|indemnification)\b",
        r"\b(vector search|embedding|transformer|attention mechanism|fine-tuning)\b",
    ]

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count based on whitespace and subword heuristics.
        Standard heuristic: ~3.8-4 characters per token for English text and code.
        """
        if not text or not text.strip():
            return 0
        words = len(text.split())
        chars = len(text)
        # Combine character length and word count for accurate hybrid estimate
        return max(1, int((chars / 3.8 + words * 1.3) / 2))

    def evaluate_complexity(self, text: str) -> Tuple[float, Dict[str, float], List[str]]:
        """
        Analyze prompt text and produce a composite complexity score between 0.0 and 1.0.
        
        Returns:
            Tuple of (overall_score, component_signals, explanatory_reasons)
        """
        if not text or not text.strip():
            return 0.0, {}, ["Empty or whitespace-only prompt"]

        reasons: List[str] = []
        clean_text = text.strip()

        # 1. Code Signal (Weight: 0.35)
        code_matches = sum(len(re.findall(p, clean_text, re.IGNORECASE | re.MULTILINE)) for p in self.CODE_PATTERNS)
        code_score = min(1.0, code_matches / 4.0)
        if code_score > 0.4:
            reasons.append(f"Significant code/syntax density detected ({code_matches} markers)")

        # 2. Reasoning & Deduction Signal (Weight: 0.30)
        reasoning_matches = sum(len(re.findall(p, clean_text, re.IGNORECASE)) for p in self.REASONING_PATTERNS)
        reasoning_score = min(1.0, reasoning_matches / 2.0)
        if reasoning_score > 0.3:
            reasons.append(f"Multi-step reasoning / analytical indicators present ({reasoning_matches} markers)")

        # 3. Domain Technical Vocabulary (Weight: 0.20)
        domain_matches = sum(len(re.findall(p, clean_text, re.IGNORECASE)) for p in self.DOMAIN_TERMS)
        domain_score = min(1.0, domain_matches / 3.0)
        if domain_score > 0.3:
            reasons.append(f"Enterprise domain terminology detected ({domain_matches} terms)")

        # 4. Lexical Diversity & Structural Depth (Weight: 0.15)
        words = clean_text.split()
        unique_words = set(w.lower() for w in words)
        lexical_diversity = len(unique_words) / max(1, len(words))
        avg_word_length = sum(len(w) for w in words) / max(1, len(words))
        structural_score = min(1.0, (lexical_diversity * 0.6 + min(1.0, avg_word_length / 8.0) * 0.4))

        # Composite weighted score with dominant signal boost
        composite_score = (
            (code_score * 0.35) +
            (reasoning_score * 0.30) +
            (domain_score * 0.20) +
            (structural_score * 0.15)
        )
        dominant_signal = max(code_score, reasoning_score)
        if dominant_signal >= 0.9:
            composite_score = max(composite_score, dominant_signal * 0.60 + domain_score * 0.25 + structural_score * 0.15)

        composite_score = round(min(1.0, max(0.0, composite_score)), 4)

        signals = {
            "code_score": round(code_score, 4),
            "reasoning_score": round(reasoning_score, 4),
            "domain_score": round(domain_score, 4),
            "structural_score": round(structural_score, 4),
        }

        return composite_score, signals, reasons

    def route_prompt(
        self,
        prompt: str,
        requested_model: Optional[str] = None,
        force_tier: Optional[int] = None,
    ) -> RoutingDecision:
        """
        Determine model tier and target model based on prompt complexity and token volume.
        """
        token_count = self.estimate_tokens(prompt)
        complexity_score, signals, reasons = self.evaluate_complexity(prompt)

        # 1. Check for manual tier override
        if force_tier in (1, 2, 3):
            tier_model_map = {
                1: settings.TIER_1_MODEL,
                2: settings.TIER_2_MODEL,
                3: settings.TIER_3_MODEL,
            }
            return RoutingDecision(
                model=tier_model_map[force_tier],
                tier=force_tier,
                complexity_score=complexity_score,
                token_count=token_count,
                reasons=[f"Caller enforced tier override: Tier {force_tier}"],
                signals=signals,
            )

        # 2. Check if dynamic routing is disabled or caller specified explicit model
        if not settings.ROUTING_ENABLED or (requested_model and requested_model != "auto"):
            target_model = requested_model or settings.DEFAULT_BASELINE_MODEL
            # Infer tier from model name
            tier = 2
            if any(k in target_model.lower() for k in ["mini", "haiku", "small", "nano"]):
                tier = 1
            elif any(k in target_model.lower() for k in ["o1", "opus", "large"]):
                tier = 3
            return RoutingDecision(
                model=target_model,
                tier=tier,
                complexity_score=complexity_score,
                token_count=token_count,
                reasons=[f"Explicit model requested: {target_model}"],
                signals=signals,
            )

        # 3. Dynamic Tiering Decision Matrix
        # Tier 3 Trigger: Massive context OR High Analytical/Code Complexity
        if token_count > settings.TIER_2_MAX_TOKENS or complexity_score >= settings.COMPLEXITY_THRESHOLD_TIER3:
            tier = 3
            model = settings.TIER_3_MODEL
            if token_count > settings.TIER_2_MAX_TOKENS:
                reasons.append(f"Prompt length ({token_count} tokens) exceeds Tier 2 capacity ({settings.TIER_2_MAX_TOKENS})")
            if complexity_score >= settings.COMPLEXITY_THRESHOLD_TIER3:
                reasons.append(f"High complexity score ({complexity_score:.2f} >= {settings.COMPLEXITY_THRESHOLD_TIER3})")

        # Tier 2 Trigger: Moderate length OR Moderate Complexity
        elif token_count > settings.TIER_1_MAX_TOKENS or complexity_score >= settings.COMPLEXITY_THRESHOLD_TIER2:
            tier = 2
            model = settings.TIER_2_MODEL
            if token_count > settings.TIER_1_MAX_TOKENS:
                reasons.append(f"Prompt length ({token_count} tokens) exceeds Tier 1 limit ({settings.TIER_1_MAX_TOKENS})")
            if complexity_score >= settings.COMPLEXITY_THRESHOLD_TIER2:
                reasons.append(f"Moderate complexity score ({complexity_score:.2f} >= {settings.COMPLEXITY_THRESHOLD_TIER2})")

        # Tier 1: Fast, Lightweight, Low-Cost
        else:
            tier = 1
            model = settings.TIER_1_MODEL
            reasons.append(f"Lightweight prompt ({token_count} tokens, complexity={complexity_score:.2f}) suitable for Tier 1")

        logger.debug(
            f"Model router decision: tier={tier} model={model} complexity={complexity_score} tokens={token_count}"
        )

        return RoutingDecision(
            model=model,
            tier=tier,
            complexity_score=complexity_score,
            token_count=token_count,
            reasons=reasons,
            signals=signals,
        )


# Global singleton instance
router_service = ModelRouter()
