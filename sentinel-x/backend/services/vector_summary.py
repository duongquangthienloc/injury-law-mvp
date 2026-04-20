"""
Vector Summary Service
Pre-processes 3-6 months of signals into compact summaries before sending to Claude.
Reduces token usage by ~80% while preserving semantic content for LLM analysis.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from ..models.signal import ActorBloc, GeopoliticalSignal, SignalSeverity

logger = logging.getLogger(__name__)

# Max signals to include verbatim in the Claude prompt (most severe only)
_MAX_VERBATIM_SIGNALS = 15


class VectorSummaryService:
    """
    Compresses large signal batches into structured text summaries
    optimized for LLM context efficiency.
    """

    def build_historical_summary(
        self,
        signals: List[GeopoliticalSignal],
        window_days: int = 180,
    ) -> str:
        """
        Produces a token-efficient 180-day baseline summary.
        Cached in Claude's prompt cache to avoid reprocessing on each call.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        window = [s for s in signals if s.timestamp >= cutoff]

        if not window:
            return "No historical signals in the analysis window."

        # Aggregate by bloc and severity
        bloc_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for sig in window:
            bloc_stats[sig.actor_bloc.value][sig.severity.name] += 1

        # Top actors by signal count
        actor_counts: Dict[str, int] = defaultdict(int)
        for sig in window:
            actor_counts[sig.actor] += 1
        top_actors = sorted(actor_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Monthly cadence (signal density per 30-day bucket)
        monthly: Dict[str, int] = defaultdict(int)
        for sig in window:
            month_key = sig.timestamp.strftime("%Y-%m")
            monthly[month_key] += 1

        lines = [
            f"=== SENTINEL-X 180-DAY BASELINE SUMMARY ===",
            f"Window: {cutoff.strftime('%Y-%m-%d')} to {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            f"Total signals processed: {len(window)}",
            "",
            "SIGNAL DISTRIBUTION BY BLOC & SEVERITY:",
        ]

        for bloc, sev_map in sorted(bloc_stats.items()):
            total = sum(sev_map.values())
            sev_str = ", ".join(f"{k}:{v}" for k, v in sorted(sev_map.items()))
            lines.append(f"  {bloc}: {total} signals ({sev_str})")

        lines += [
            "",
            "TOP ACTORS (signal count):",
            ", ".join(f"{actor}({cnt})" for actor, cnt in top_actors),
            "",
            "MONTHLY SIGNAL CADENCE (baseline density):",
            ", ".join(f"{m}:{c}" for m, c in sorted(monthly.items())),
        ]

        return "\n".join(lines)

    def build_realtime_summary(
        self,
        signals: List[GeopoliticalSignal],
        window_hours: int = 168,  # 7 days
    ) -> str:
        """
        Produces a compact real-time window summary (last 7 days).
        Included verbatim in each Claude analysis call.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        recent = sorted(
            [s for s in signals if s.timestamp >= cutoff],
            key=lambda s: s.severity,
            reverse=True,
        )

        if not recent:
            return "No real-time signals in the 7-day window."

        # Verbatim top signals (most severe)
        verbatim = recent[:_MAX_VERBATIM_SIGNALS]

        lines = [
            f"=== REAL-TIME SIGNAL WINDOW (last {window_hours//24}d) ===",
            f"Total signals: {len(recent)} | Showing top {len(verbatim)} by severity",
            "",
        ]

        for i, sig in enumerate(verbatim, 1):
            lines.append(
                f"{i}. [{sig.severity.name}] [{sig.actor_bloc.value}] {sig.actor}: "
                f"{sig.headline[:200]} "
                f"(src: {sig.source}, {sig.timestamp.strftime('%Y-%m-%d %H:%M')} UTC)"
            )

        # Severity breakdown
        sev_dist: Dict[str, int] = defaultdict(int)
        for sig in recent:
            sev_dist[sig.severity.name] += 1
        lines += [
            "",
            "SEVERITY BREAKDOWN: " + ", ".join(f"{k}:{v}" for k, v in sev_dist.items()),
        ]

        return "\n".join(lines)

    def build_escalation_context(
        self,
        escalation_index: float,
        risk_tier: str,
        b: float,
        p: float,
        l: float,
        fault_allocation: Dict[str, float],
    ) -> str:
        return (
            f"=== LEARNED HAND ESCALATION ANALYSIS ===\n"
            f"Risk Tier: {risk_tier} | Index: {escalation_index:.1f}/100\n"
            f"B (restraint cost): ${b:.1f}bn | P (probability): {p:.1%} | L (loss magnitude): ${l:.1f}bn\n"
            f"B < P×L threshold: {'BREACHED' if b < p * l else 'within bounds'}\n"
            f"Comparative Fault: {json.dumps(fault_allocation, indent=2)}\n"
        )
