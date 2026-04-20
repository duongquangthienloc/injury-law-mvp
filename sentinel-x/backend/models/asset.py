from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AssetClass(str, Enum):
    FOREX = "FOREX"
    EQUITY_VOLATILITY = "EQUITY_VOLATILITY"   # VIX
    GOLD = "GOLD"
    ENERGY_FUTURES = "ENERGY_FUTURES"
    SEMICONDUCTORS = "SEMICONDUCTORS"
    FX_RESERVES = "FX_RESERVES"
    INFRASTRUCTURE_BONDS = "INFRASTRUCTURE_BONDS"


class TimeHorizon(str, Enum):
    SHORT = "SHORT"   # 0-7 days
    MID = "MID"       # 1-3 months
    LONG = "LONG"     # 6+ months


class PriceDirection(str, Enum):
    SPIKE = "SPIKE"       # >+5% expected move
    RISE = "RISE"         # +1-5%
    NEUTRAL = "NEUTRAL"   # within ±1%
    FALL = "FALL"         # -1-5%
    CRASH = "CRASH"       # >-5%


class AssetImpact(BaseModel):
    asset_class: AssetClass
    horizon: TimeHorizon
    direction: PriceDirection
    magnitude_pct: float = Field(..., description="Expected % price move")
    confidence: float = Field(..., ge=0.0, le=1.0)
    driver: str = ""  # Human-readable driver string


class FinancialPrediction(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    escalation_index: float
    risk_tier: str

    short_term: List[AssetImpact] = Field(default_factory=list)   # 0-7d
    mid_term: List[AssetImpact] = Field(default_factory=list)     # 1-3mo
    long_term: List[AssetImpact] = Field(default_factory=list)    # 6mo+

    de_dollarization_score: float = Field(
        default=0.0, ge=0.0, le=100.0,
        description="0-100 score for de-dollarization trend intensity"
    )
    energy_disruption_score: float = Field(
        default=0.0, ge=0.0, le=100.0,
        description="0-100 score for supply disruption risk"
    )
    summary: str = ""
