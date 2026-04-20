"""
Claude Service — SENTINEL-X V2
Uses claude-sonnet-4-6 with prompt caching for cost-efficient geopolitical analysis.

Caching strategy:
  - CACHE BLOCK 1 (ephemeral): 180-day historical baseline summary
    → static for each crawl session; cached across multiple analysis calls
  - CACHE BLOCK 2 (ephemeral): Escalation context + methodology
    → cached within the same analysis session
  - DYNAMIC BLOCK: Real-time signal window (not cached; changes each call)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import anthropic

from ..config import settings
from ..models.asset import FinancialPrediction
from ..models.escalation import EscalationResult
from ..models.signal import GeopoliticalSignal
from .vector_summary import VectorSummaryService

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are SENTINEL-X, an expert geopolitical risk analyst and LegalTech intelligence engine.
You apply Learned Hand negligence principles (B < P×L) to geopolitical escalation analysis.
Your role is to:
1. Assess current escalation levels against the 180-day historical baseline
2. Identify which actors are breaching their "Stability Duty" (most aggressively increasing conflict probability)
3. Predict financial asset impacts across short (0-7d), mid (1-3mo), and long-term (6mo+) horizons
4. Provide actionable intelligence for institutional investors and legal risk teams

Always structure your response as JSON with keys: analysis, breach_assessment, asset_outlook, recommended_hedges, confidence_score.
Be precise, data-driven, and cite specific signals from the provided context."""


class ClaudeService:

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._summary_svc = VectorSummaryService()
        self._cached_historical_summary: Optional[str] = None

    def set_historical_summary(self, summary: str) -> None:
        """Called after historical crawl completes; cached for reuse."""
        self._cached_historical_summary = summary

    def build_historical_summary(self, signals: List[GeopoliticalSignal]) -> str:
        summary = self._summary_svc.build_historical_summary(signals)
        self._cached_historical_summary = summary
        return summary

    async def analyze_escalation(
        self,
        realtime_signals: List[GeopoliticalSignal],
        historical_signals: List[GeopoliticalSignal],
        escalation: EscalationResult,
        fault_allocation: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Full geopolitical analysis with prompt caching.
        Returns structured JSON analysis from Claude.
        """
        historical_summary = (
            self._cached_historical_summary
            or self._summary_svc.build_historical_summary(historical_signals)
        )
        realtime_summary = self._summary_svc.build_realtime_summary(realtime_signals)
        escalation_ctx = self._summary_svc.build_escalation_context(
            escalation_index=escalation.escalation_index,
            risk_tier=escalation.risk_tier,
            b=escalation.components.burden_of_restraint,
            p=escalation.components.probability_of_harm,
            l=escalation.components.loss_magnitude,
            fault_allocation=fault_allocation,
        )

        messages = [
            {
                "role": "user",
                "content": [
                    # CACHE BLOCK 1: 180-day historical baseline (static, large, cached)
                    {
                        "type": "text",
                        "text": historical_summary,
                        "cache_control": {"type": "ephemeral"},
                    },
                    # CACHE BLOCK 2: Escalation methodology + current context (semi-static)
                    {
                        "type": "text",
                        "text": escalation_ctx,
                        "cache_control": {"type": "ephemeral"},
                    },
                    # DYNAMIC BLOCK: Real-time signals (changes each call; not cached)
                    {
                        "type": "text",
                        "text": (
                            realtime_summary
                            + "\n\nBased on all context above, provide your full SENTINEL-X analysis as JSON."
                        ),
                    },
                ],
            }
        ]

        try:
            response = await self._client.messages.create(
                model=settings.claude_model,
                max_tokens=2048,
                system=[
                    {
                        "type": "text",
                        "text": _SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=messages,
            )

            raw_text = response.content[0].text
            cache_stats = {
                "cache_creation_tokens": getattr(response.usage, "cache_creation_input_tokens", 0),
                "cache_read_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
            logger.info("Claude analysis — %s", cache_stats)

            return _parse_analysis(raw_text, cache_stats)

        except Exception as exc:
            logger.error("Claude analysis failed: %s", exc)
            return {
                "analysis": f"Analysis unavailable: {exc}",
                "breach_assessment": escalation.summary,
                "asset_outlook": {},
                "recommended_hedges": [],
                "confidence_score": 0.0,
                "error": str(exc),
            }

    async def generate_strategy_report(
        self,
        escalation: EscalationResult,
        prediction: FinancialPrediction,
        analysis: Dict[str, Any],
    ) -> str:
        """
        Generates a concise executive strategy brief (≤400 words).
        Uses cached system prompt for efficiency.
        """
        prompt = (
            f"Generate an executive strategy brief based on:\n"
            f"Risk Tier: {escalation.risk_tier} | Index: {escalation.escalation_index}\n"
            f"Key findings: {analysis.get('analysis', '')[:600]}\n"
            f"Asset outlook: {prediction.summary}\n"
            f"De-dollarization score: {prediction.de_dollarization_score}\n"
            f"Energy disruption score: {prediction.energy_disruption_score}\n\n"
            f"Format: 3 sections — Situation, Risk Assessment, Recommended Actions. Max 400 words."
        )

        try:
            response = await self._client.messages.create(
                model=settings.claude_model,
                max_tokens=600,
                system=[{"type": "text", "text": _SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as exc:
            logger.error("Strategy report failed: %s", exc)
            return f"Strategy report unavailable: {exc}"


def _parse_analysis(raw: str, cache_stats: dict) -> Dict[str, Any]:
    import json, re
    # Extract JSON block if wrapped in markdown code fences
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        raw = match.group(1)
    try:
        data = json.loads(raw)
        data["_cache_stats"] = cache_stats
        return data
    except json.JSONDecodeError:
        return {
            "analysis": raw,
            "breach_assessment": "",
            "asset_outlook": {},
            "recommended_hedges": [],
            "confidence_score": 0.5,
            "_cache_stats": cache_stats,
        }
