"""
Learned Hand Formula Engine — B < P * L
Applied to geopolitical escalation detection.

B = Economic/diplomatic cost of restraint over the 6-month window (USD bn)
P = Probability of conflict: ratio of real-time signal density to historical baseline
L = Magnitude of potential special damages (economic loss, energy spike, USD bn)

When B < P * L → escalation threshold breached → "Breach of Stability Duty"
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import List

from ..models.escalation import EscalationResult, LearnedHandComponents
from ..models.signal import GeopoliticalSignal, SignalSeverity

logger = logging.getLogger(__name__)

# ─── Economic constants (approximate USD billion benchmarks) ──────────────────

# Cost of restraint: average per-day diplomatic/economic cost of *not* escalating.
# Includes: trade facilitation value, diplomatic capital, joint infrastructure.
# Source basis: IMF world trade flow data; ~$180bn/day global goods trade.
_DAILY_RESTRAINT_COST_USD_BN = 0.5   # Conservative per-day de-escalation cost

# Special damages scale (L) per severity tier, per signal (USD bn equivalent)
_SEVERITY_DAMAGE_MAP = {
    SignalSeverity.LOW: 0.5,
    SignalSeverity.MEDIUM: 5.0,
    SignalSeverity.HIGH: 25.0,
    SignalSeverity.CRITICAL: 150.0,
}

# Probability weight per severity (how much each tier increases P)
_SEVERITY_PROB_WEIGHT = {
    SignalSeverity.LOW: 0.01,
    SignalSeverity.MEDIUM: 0.04,
    SignalSeverity.HIGH: 0.10,
    SignalSeverity.CRITICAL: 0.25,
}


class LearnedHandEngine:
    """
    Computes the B < P*L escalation test against a historical baseline.
    """

    def compute(
        self,
        realtime_signals: List[GeopoliticalSignal],
        historical_signals: List[GeopoliticalSignal],
        window_days: int = 7,
        historical_days: int = 180,
    ) -> EscalationResult:
        # ── B: Burden of restraint ─────────────────────────────────────────
        # Approximated as the compounded daily cost of de-escalation posture
        # over the observation window.  We adjust upward with active engagement
        # signals (accords, summits) that represent real diplomatic outlay.
        accord_signals = sum(
            1 for s in realtime_signals
            if any(kw in ("accord", "treaty", "summit", "ceasefire", "negotiation")
                   for kw in s.action_keywords)
        )
        B = (_DAILY_RESTRAINT_COST_USD_BN * window_days) + (accord_signals * 2.0)

        # ── P: Probability of harm ─────────────────────────────────────────
        # Signal density = severity-weighted signals per day
        realtime_density = _weighted_density(realtime_signals, window_days)
        historical_density = _weighted_density(historical_signals, historical_days)

        if historical_density < 1e-6:
            # No historical baseline yet — use raw realtime density
            P = min(realtime_density * 0.05, 0.95)
        else:
            # Density ratio: how much hotter is the current window vs baseline?
            ratio = realtime_density / historical_density
            # Sigmoid transform to map ratio → [0, 1]
            P = 1.0 / (1.0 + math.exp(-2.0 * (ratio - 1.0)))

        P = max(0.01, min(P, 0.99))

        # ── L: Loss magnitude ──────────────────────────────────────────────
        # Sum of severity-weighted damage estimates across realtime signals.
        L = sum(_SEVERITY_DAMAGE_MAP[s.severity] for s in realtime_signals)
        # Floor at 1 bn to avoid zero division
        L = max(L, 1.0)

        # ── Assemble components ────────────────────────────────────────────
        components = LearnedHandComponents(
            burden_of_restraint=round(B, 2),
            probability_of_harm=round(P, 4),
            loss_magnitude=round(L, 2),
            realtime_signal_density=round(realtime_density, 4),
            historical_signal_density=round(historical_density, 4),
        )

        # ── Dominant signals (top-3 by severity) ──────────────────────────
        sorted_signals = sorted(realtime_signals, key=lambda s: s.severity, reverse=True)
        dominant = [s.headline[:120] for s in sorted_signals[:3]]

        return EscalationResult.from_components(
            components=components,
            dominant_signals=dominant,
            summary=_build_summary(components),
        )


def _weighted_density(signals: List[GeopoliticalSignal], days: int) -> float:
    """Severity-weighted signals per day."""
    if not signals or days <= 0:
        return 0.0
    total_weight = sum(_SEVERITY_PROB_WEIGHT[s.severity] for s in signals)
    return total_weight / days


def _build_summary(c: LearnedHandComponents) -> str:
    status = "BREACHED" if c.threshold_breached else "WITHIN BOUNDS"
    return (
        f"Stability Duty {status}. "
        f"B={c.burden_of_restraint:.1f}bn vs P×L={c.expected_loss:.1f}bn. "
        f"Signal density ratio: {c.realtime_signal_density:.3f} (RT) / "
        f"{c.historical_signal_density:.3f} (180d). "
        f"P(conflict)={c.probability_of_harm:.1%}."
    )
