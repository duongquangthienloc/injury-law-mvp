from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ActorBloc(str, Enum):
    G7 = "G7"
    BRICS = "BRICS"
    NATO = "NATO"
    SCO = "SCO"
    ASEAN = "ASEAN"
    OTHER = "OTHER"


class SignalSeverity(int, Enum):
    LOW = 1       # Diplomatic statement / position paper
    MEDIUM = 2    # Economic action / sanction announcement
    HIGH = 3      # Military posturing / troop movement
    CRITICAL = 4  # Active conflict indicator / ultimatum


# Maps known nation names to blocs for fast lookup
NATION_BLOC_MAP: dict[str, ActorBloc] = {
    # G7
    "united states": ActorBloc.G7, "usa": ActorBloc.G7, "us": ActorBloc.G7,
    "united kingdom": ActorBloc.G7, "uk": ActorBloc.G7,
    "germany": ActorBloc.G7, "france": ActorBloc.G7,
    "italy": ActorBloc.G7, "japan": ActorBloc.G7, "canada": ActorBloc.G7,
    # BRICS
    "brazil": ActorBloc.BRICS, "russia": ActorBloc.BRICS,
    "india": ActorBloc.BRICS, "china": ActorBloc.BRICS,
    "south africa": ActorBloc.BRICS, "iran": ActorBloc.BRICS,
    "saudi arabia": ActorBloc.BRICS, "uae": ActorBloc.BRICS,
    "ethiopia": ActorBloc.BRICS, "egypt": ActorBloc.BRICS,
    # NATO (non-G7)
    "nato": ActorBloc.NATO, "poland": ActorBloc.NATO,
    "turkey": ActorBloc.NATO, "spain": ActorBloc.NATO,
    # SCO
    "pakistan": ActorBloc.SCO, "kazakhstan": ActorBloc.SCO,
    "uzbekistan": ActorBloc.SCO,
}


def classify_bloc(actor: str) -> ActorBloc:
    key = actor.lower().strip()
    for name, bloc in NATION_BLOC_MAP.items():
        if name in key:
            return bloc
    return ActorBloc.OTHER


class GeopoliticalSignal(BaseModel):
    id: Optional[str] = None
    timestamp: datetime
    source: str
    headline: str
    content_summary: str
    actor: str
    actor_bloc: ActorBloc = ActorBloc.OTHER
    severity: SignalSeverity = SignalSeverity.LOW
    action_keywords: List[str] = Field(default_factory=list)
    url: Optional[str] = None
    is_realtime: bool = True

    def model_post_init(self, __context: object) -> None:
        if self.actor_bloc == ActorBloc.OTHER:
            self.actor_bloc = classify_bloc(self.actor)


class SignalBatch(BaseModel):
    signals: List[GeopoliticalSignal]
    window_start: datetime
    window_end: datetime
    total_count: int
    severity_distribution: dict = Field(default_factory=dict)

    @classmethod
    def from_signals(
        cls,
        signals: List[GeopoliticalSignal],
        window_start: datetime,
        window_end: datetime,
    ) -> "SignalBatch":
        dist: dict[str, int] = {}
        for s in signals:
            key = s.severity.name
            dist[key] = dist.get(key, 0) + 1
        return cls(
            signals=signals,
            window_start=window_start,
            window_end=window_end,
            total_count=len(signals),
            severity_distribution=dist,
        )
