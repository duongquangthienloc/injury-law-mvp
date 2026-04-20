"""
Comparative Fault Engine
Analyzes signals from both blocs (G7 vs BRICS etc.) to determine
who is increasing the Probability of Conflict more aggressively.
Outputs a fault allocation (%) per bloc — analogous to comparative negligence.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from ..models.escalation import ComparativeFaultResult
from ..models.signal import ActorBloc, GeopoliticalSignal, SignalSeverity

logger = logging.getLogger(__name__)

# Severity weights for fault scoring
_FAULT_WEIGHTS: Dict[SignalSeverity, float] = {
    SignalSeverity.LOW: 1.0,
    SignalSeverity.MEDIUM: 3.0,
    SignalSeverity.HIGH: 8.0,
    SignalSeverity.CRITICAL: 20.0,
}

# De-escalation keywords reduce fault score (showing restraint)
_DEESCALATION_KWS = frozenset({
    "ceasefire", "accord", "treaty", "withdrawal", "summit",
    "negotiation", "dialogue", "cooperation", "agreement",
})


class ComparativeFaultEngine:
    """
    Determines which actor/bloc is the primary driver of escalation.
    Modeled on comparative negligence: each party's fault share is their
    weighted escalatory signal count / total escalatory signals.
    """

    def analyze(
        self,
        signals: List[GeopoliticalSignal],
        window_days: int = 30,
    ) -> ComparativeFaultResult:
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        window_signals = [s for s in signals if s.timestamp >= cutoff]

        bloc_scores: Dict[str, float] = defaultdict(float)
        bloc_counts: Dict[str, int] = defaultdict(int)

        for sig in window_signals:
            bloc = sig.actor_bloc.value
            weight = _FAULT_WEIGHTS[sig.severity]

            # Reduce weight for de-escalatory signals
            de_esc_count = sum(
                1 for kw in sig.action_keywords if kw in _DEESCALATION_KWS
            )
            if de_esc_count > 0:
                weight *= max(0.1, 1.0 - (de_esc_count * 0.3))

            bloc_scores[bloc] += weight
            bloc_counts[bloc] += 1

        total_score = sum(bloc_scores.values()) or 1.0

        fault_allocation: Dict[str, float] = {
            bloc: round((score / total_score) * 100.0, 1)
            for bloc, score in bloc_scores.items()
        }

        # Primary aggressor: highest fault share (excluding "OTHER" if others exist)
        primary = max(
            fault_allocation,
            key=lambda b: fault_allocation[b] if b != "OTHER" else -1,
            default="UNKNOWN",
        )

        return ComparativeFaultResult(
            bloc_fault_scores={k: round(v, 2) for k, v in bloc_scores.items()},
            bloc_signal_counts=dict(bloc_counts),
            fault_allocation=fault_allocation,
            primary_aggressor=primary,
            analysis_window_days=window_days,
        )

    def get_bloc_trend(
        self,
        signals: List[GeopoliticalSignal],
        bloc: ActorBloc,
        bucket_days: int = 7,
        total_days: int = 180,
    ) -> List[Dict]:
        """
        Returns a time-bucketed trend for a single bloc.
        Used for the 6-month Intent vs Action graph.
        """
        now = datetime.now(timezone.utc)
        buckets = []

        for i in range(total_days // bucket_days - 1, -1, -1):
            bucket_end = now - timedelta(days=i * bucket_days)
            bucket_start = bucket_end - timedelta(days=bucket_days)

            bloc_signals = [
                s for s in signals
                if s.actor_bloc == bloc
                and bucket_start <= s.timestamp < bucket_end
            ]

            # "Intent" = LOW/MEDIUM signals (diplomatic language)
            intent = sum(
                _FAULT_WEIGHTS[s.severity]
                for s in bloc_signals
                if s.severity in (SignalSeverity.LOW, SignalSeverity.MEDIUM)
            )
            # "Action" = HIGH/CRITICAL signals (actual military/economic moves)
            action = sum(
                _FAULT_WEIGHTS[s.severity]
                for s in bloc_signals
                if s.severity in (SignalSeverity.HIGH, SignalSeverity.CRITICAL)
            )

            buckets.append({
                "date": bucket_end.strftime("%Y-%m-%d"),
                "bloc": bloc.value,
                "intent": round(intent, 2),
                "action": round(action, 2),
                "total": round(intent + action, 2),
                "signal_count": len(bloc_signals),
            })

        return buckets
