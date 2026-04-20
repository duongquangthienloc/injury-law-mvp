"""
Asset Impact Mapper
Maps escalation index and risk tier to predicted financial asset movements.

Short-term  (0-7d):  Forex volatility, VIX, Gold spikes
Mid-term    (1-3mo): Energy futures, Supply chain / Semiconductors
Long-term   (6mo+):  FX reserves / De-dollarization, Infrastructure bonds
"""
from __future__ import annotations

import logging
from typing import List

from ..models.asset import (
    AssetClass, AssetImpact, FinancialPrediction, PriceDirection, TimeHorizon
)
from ..models.escalation import EscalationResult

logger = logging.getLogger(__name__)


class AssetMapperEngine:

    def predict(self, escalation: EscalationResult) -> FinancialPrediction:
        idx = escalation.escalation_index        # 0-100
        tier = escalation.risk_tier              # STABLE/ELEVATED/CRITICAL/BREACH
        p = escalation.components.probability_of_harm

        short = self._short_term(idx, tier, p)
        mid   = self._mid_term(idx, tier, p)
        long  = self._long_term(idx, tier, p)

        de_dol = _de_dollarization_score(escalation)
        energy = _energy_disruption_score(escalation)

        return FinancialPrediction(
            escalation_index=idx,
            risk_tier=tier,
            short_term=short,
            mid_term=mid,
            long_term=long,
            de_dollarization_score=de_dol,
            energy_disruption_score=energy,
            summary=_prediction_summary(tier, short, mid, long),
        )

    # ─── Short-term (0-7 days) ────────────────────────────────────────────

    def _short_term(
        self, idx: float, tier: str, p: float
    ) -> List[AssetImpact]:
        impacts: List[AssetImpact] = []

        # FOREX Volatility: rises with any escalation
        forex_mag = _scale(idx, 0, 100, 0.5, 8.0)
        impacts.append(AssetImpact(
            asset_class=AssetClass.FOREX,
            horizon=TimeHorizon.SHORT,
            direction=_direction(forex_mag, neutral_band=1.0),
            magnitude_pct=round(forex_mag, 2),
            confidence=round(0.5 + p * 0.4, 2),
            driver=f"Geopolitical uncertainty ({tier}) → EM currency sell-off",
        ))

        # VIX: spikes on CRITICAL/BREACH
        vix_mag = _scale(idx, 30, 100, 2.0, 35.0) if idx > 30 else 0.0
        impacts.append(AssetImpact(
            asset_class=AssetClass.EQUITY_VOLATILITY,
            horizon=TimeHorizon.SHORT,
            direction=_direction(vix_mag, neutral_band=2.0),
            magnitude_pct=round(vix_mag, 2),
            confidence=round(0.45 + p * 0.45, 2),
            driver="Risk-off flight → VIX expansion",
        ))

        # Gold: safe-haven demand
        gold_mag = _scale(idx, 0, 100, 0.3, 6.0)
        impacts.append(AssetImpact(
            asset_class=AssetClass.GOLD,
            horizon=TimeHorizon.SHORT,
            direction=PriceDirection.SPIKE if idx > 70 else PriceDirection.RISE,
            magnitude_pct=round(gold_mag, 2),
            confidence=round(0.60 + p * 0.3, 2),
            driver="Safe-haven demand spike",
        ))

        return impacts

    # ─── Mid-term (1-3 months) ────────────────────────────────────────────

    def _mid_term(
        self, idx: float, tier: str, p: float
    ) -> List[AssetImpact]:
        impacts: List[AssetImpact] = []

        # Energy futures: supply disruption risk
        energy_mag = _scale(idx, 20, 100, 0.5, 40.0) if idx > 20 else 0.0
        impacts.append(AssetImpact(
            asset_class=AssetClass.ENERGY_FUTURES,
            horizon=TimeHorizon.MID,
            direction=_direction(energy_mag, neutral_band=2.0),
            magnitude_pct=round(energy_mag, 2),
            confidence=round(0.40 + p * 0.45, 2),
            driver="Shipping route disruption / supply shock",
        ))

        # Semiconductors: supply chain re-routing
        semi_mag = _scale(idx, 40, 100, 1.0, 20.0) if idx > 40 else 0.0
        # Semiconductors go DOWN on escalation (supply chain uncertainty)
        impacts.append(AssetImpact(
            asset_class=AssetClass.SEMICONDUCTORS,
            horizon=TimeHorizon.MID,
            direction=PriceDirection.FALL if semi_mag > 3 else PriceDirection.NEUTRAL,
            magnitude_pct=round(-semi_mag, 2),
            confidence=round(0.35 + p * 0.40, 2),
            driver="East-West supply chain fragmentation / export control risk",
        ))

        return impacts

    # ─── Long-term (6 months+) ────────────────────────────────────────────

    def _long_term(
        self, idx: float, tier: str, p: float
    ) -> List[AssetImpact]:
        impacts: List[AssetImpact] = []

        # FX Reserves / De-dollarization
        fx_mag = _scale(idx, 50, 100, 0.5, 15.0) if idx > 50 else 0.0
        impacts.append(AssetImpact(
            asset_class=AssetClass.FX_RESERVES,
            horizon=TimeHorizon.LONG,
            direction=PriceDirection.FALL if fx_mag > 2.0 else PriceDirection.NEUTRAL,
            magnitude_pct=round(-fx_mag, 2),
            confidence=round(0.30 + p * 0.35, 2),
            driver="BRICS alternative settlement growth / USD reserve diversification",
        ))

        # Infrastructure bonds: depends on region
        infra_mag = _scale(idx, 0, 100, 0.2, 5.0)
        impacts.append(AssetImpact(
            asset_class=AssetClass.INFRASTRUCTURE_BONDS,
            horizon=TimeHorizon.LONG,
            direction=_direction(-infra_mag, neutral_band=0.5),
            magnitude_pct=round(-infra_mag, 2),
            confidence=round(0.25 + p * 0.30, 2),
            driver="Sovereign risk premium expansion on conflict-adjacent issuers",
        ))

        return impacts


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _scale(val: float, v_min: float, v_max: float, out_min: float, out_max: float) -> float:
    """Linear scale val from [v_min, v_max] to [out_min, out_max]."""
    clamped = max(v_min, min(val, v_max))
    ratio = (clamped - v_min) / max(v_max - v_min, 1e-9)
    return out_min + ratio * (out_max - out_min)


def _direction(magnitude: float, neutral_band: float = 1.0) -> PriceDirection:
    if magnitude > 10:
        return PriceDirection.SPIKE
    if magnitude > neutral_band:
        return PriceDirection.RISE
    if magnitude < -10:
        return PriceDirection.CRASH
    if magnitude < -neutral_band:
        return PriceDirection.FALL
    return PriceDirection.NEUTRAL


def _de_dollarization_score(e: EscalationResult) -> float:
    """Score increases when BRICS signals dominate and index is high."""
    from ..models.signal import ActorBloc
    brics_dominant = any("BRICS" in s for s in e.dominant_signals)
    base = _scale(e.escalation_index, 40, 100, 10.0, 85.0) if e.escalation_index > 40 else 5.0
    return round(min(base * (1.3 if brics_dominant else 1.0), 100.0), 1)


def _energy_disruption_score(e: EscalationResult) -> float:
    energy_kws = {"energy", "oil", "gas", "pipeline", "shipping", "strait", "blockade"}
    signal_text = " ".join(e.dominant_signals).lower()
    has_energy = any(kw in signal_text for kw in energy_kws)
    base = _scale(e.escalation_index, 20, 100, 5.0, 90.0) if e.escalation_index > 20 else 2.0
    return round(min(base * (1.4 if has_energy else 1.0), 100.0), 1)


def _prediction_summary(tier: str, short: list, mid: list, long: list) -> str:
    lines = [f"Risk tier: {tier}."]
    for impact in short[:2]:
        lines.append(f"[0-7d] {impact.asset_class.value}: {impact.direction.value} ~{abs(impact.magnitude_pct):.1f}%")
    for impact in mid[:2]:
        lines.append(f"[1-3mo] {impact.asset_class.value}: {impact.direction.value} ~{abs(impact.magnitude_pct):.1f}%")
    for impact in long[:2]:
        lines.append(f"[6mo+] {impact.asset_class.value}: {impact.direction.value} ~{abs(impact.magnitude_pct):.1f}%")
    return " | ".join(lines)
