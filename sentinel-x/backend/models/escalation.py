from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel, Field


class LearnedHandComponents(BaseModel):
    """
    Learned Hand negligence formula: liability when B < P * L
    Applied to geopolitical escalation analysis.
    """
    # B — Economic/diplomatic cost of restraint over the 6-month window (USD billions)
    burden_of_restraint: float = Field(..., description="B: cost of de-escalation (USD bn)")

    # P — Probability of conflict based on signal density ratio (realtime vs historical)
    probability_of_harm: float = Field(..., ge=0.0, le=1.0, description="P: [0,1]")

    # L — Magnitude of potential special damages (USD billions)
    loss_magnitude: float = Field(..., description="L: estimated economic damage (USD bn)")

    # Derived: P * L
    expected_loss: float = 0.0

    # Derived: B < P*L → escalation threshold breached
    threshold_breached: bool = False

    # Raw signal counts used for P calculation
    realtime_signal_density: float = 0.0
    historical_signal_density: float = 0.0

    def model_post_init(self, __context: object) -> None:
        self.expected_loss = self.probability_of_harm * self.loss_magnitude
        self.threshold_breached = self.burden_of_restraint < self.expected_loss


class EscalationResult(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    components: LearnedHandComponents
    escalation_index: float = Field(..., ge=0.0, le=100.0, description="0-100 gauge score")
    risk_tier: str  # STABLE / ELEVATED / CRITICAL / BREACH
    dominant_signals: List[str] = Field(default_factory=list)
    summary: str = ""

    @classmethod
    def from_components(
        cls,
        components: LearnedHandComponents,
        dominant_signals: List[str],
        summary: str = "",
    ) -> "EscalationResult":
        # Normalize escalation index 0-100
        if components.burden_of_restraint <= 0:
            index = 100.0
        else:
            ratio = components.expected_loss / max(components.burden_of_restraint, 0.001)
            index = min(ratio * 50.0, 100.0)

        if index < 25:
            tier = "STABLE"
        elif index < 50:
            tier = "ELEVATED"
        elif index < 75:
            tier = "CRITICAL"
        else:
            tier = "BREACH"

        return cls(
            components=components,
            escalation_index=round(index, 2),
            risk_tier=tier,
            dominant_signals=dominant_signals,
            summary=summary,
        )


class ComparativeFaultResult(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    bloc_fault_scores: Dict[str, float] = Field(default_factory=dict)
    bloc_signal_counts: Dict[str, int] = Field(default_factory=dict)
    # Percentage of escalation attributed to each bloc (sums to ~100)
    fault_allocation: Dict[str, float] = Field(default_factory=dict)
    primary_aggressor: str = "UNKNOWN"
    analysis_window_days: int = 30
