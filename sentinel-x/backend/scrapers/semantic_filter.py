"""
Token-saving semantic filter.
Only passes headlines that contain geopolitically relevant Action Keywords.
Prevents generic noise from reaching the LLM pipeline.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from ..models.signal import SignalSeverity


# Tier 1 — CRITICAL: immediate conflict indicators
_CRITICAL_KEYWORDS: set[str] = {
    "invasion", "war", "nuclear", "strike", "bombing", "airstrike",
    "ultimatum", "missile", "warship", "troops deployed", "martial law",
    "coup", "blockade", "occupation",
}

# Tier 2 — HIGH: military posturing
_HIGH_KEYWORDS: set[str] = {
    "military", "deployment", "naval", "forces", "troops", "weapon",
    "arms", "defense", "offensive", "drills", "exercises", "intercept",
    "provocation", "aggression", "retaliation", "escalat",
}

# Tier 3 — MEDIUM: economic actions
_MEDIUM_KEYWORDS: set[str] = {
    "sanction", "embargo", "tariff", "trade war", "export ban",
    "import restriction", "asset freeze", "seizure", "expulsion",
    "accord", "treaty", "pact", "alliance", "coalition", "deal",
    "ceasefire", "negotiation", "summit", "bilateral",
}

# Tier 4 — LOW: diplomatic signals
_LOW_KEYWORDS: set[str] = {
    "diplomat", "ambassador", "envoy", "recall", "protest", "condemn",
    "demand", "warning", "tension", "dispute", "conflict", "crisis",
    "geopolit", "sovereignty", "territorial",
}

# Combined ordered list for fast scanning
_ALL_TIERS: List[Tuple[set[str], SignalSeverity]] = [
    (_CRITICAL_KEYWORDS, SignalSeverity.CRITICAL),
    (_HIGH_KEYWORDS, SignalSeverity.HIGH),
    (_MEDIUM_KEYWORDS, SignalSeverity.MEDIUM),
    (_LOW_KEYWORDS, SignalSeverity.LOW),
]


def _normalize(text: str) -> str:
    return text.lower()


def classify_headline(headline: str) -> Optional[Tuple[SignalSeverity, List[str]]]:
    """
    Returns (severity, matched_keywords) if the headline is relevant.
    Returns None if the headline should be skipped.
    """
    normalized = _normalize(headline)
    matched: List[str] = []
    highest_severity: Optional[SignalSeverity] = None

    for keyword_set, severity in _ALL_TIERS:
        for kw in keyword_set:
            if kw in normalized:
                matched.append(kw)
                if highest_severity is None:
                    highest_severity = severity

    if not matched:
        return None

    return highest_severity, list(set(matched))


def is_relevant(headline: str) -> bool:
    return classify_headline(headline) is not None


def extract_actor_hint(headline: str) -> str:
    """
    Quick heuristic actor extraction before the LLM pass.
    Extracts the first capitalized multi-word entity.
    """
    # Match sequences like "United States", "North Korea", "EU", "NATO"
    pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*|[A-Z]{2,5})\b'
    matches = re.findall(pattern, headline)
    # Skip very generic words
    generic = {"The", "A", "An", "In", "On", "At", "To", "Of", "For"}
    candidates = [m for m in matches if m not in generic]
    return candidates[0] if candidates else "UNKNOWN"
