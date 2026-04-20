"""
SENTINEL-X V2 — FastAPI Route Definitions
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import (
    fetch_escalation_history,
    fetch_signals_in_window,
    get_session,
)
from ..engines.asset_mapper import AssetMapperEngine
from ..engines.comparative_fault import ComparativeFaultEngine
from ..engines.learned_hand import LearnedHandEngine
from ..models.signal import ActorBloc, GeopoliticalSignal, SignalSeverity
from ..services.claude_service import ClaudeService

logger = logging.getLogger(__name__)
router = APIRouter()

# Shared engine singletons (injected via app state in main.py)
_lh_engine = LearnedHandEngine()
_fault_engine = ComparativeFaultEngine()
_asset_engine = AssetMapperEngine()
_claude_svc = ClaudeService()


# ─── Status ──────────────────────────────────────────────────────────────────

@router.get("/status")
async def get_status() -> Dict[str, Any]:
    return {
        "status": "online",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "modes": {"realtime": "active", "historical": "available"},
    }


# ─── Signals ─────────────────────────────────────────────────────────────────

@router.get("/signals")
async def get_signals(
    days: int = Query(default=7, ge=1, le=180),
    severity_min: int = Query(default=1, ge=1, le=4),
    bloc: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    rows = await fetch_signals_in_window(session, start, end)

    signals = [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "source": r.source,
            "headline": r.headline,
            "actor": r.actor,
            "actor_bloc": r.actor_bloc,
            "severity": r.severity,
            "action_keywords": r.action_keywords,
            "url": r.url,
        }
        for r in rows
        if r.severity >= severity_min
        and (not bloc or r.actor_bloc == bloc.upper())
    ][:limit]

    return {
        "signals": signals,
        "count": len(signals),
        "window_days": days,
        "filters": {"severity_min": severity_min, "bloc": bloc},
    }


# ─── Escalation ──────────────────────────────────────────────────────────────

@router.get("/escalation")
async def get_escalation(
    realtime_days: int = Query(default=7, ge=1, le=30),
    historical_days: int = Query(default=180, ge=30, le=365),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)

    rt_rows = await fetch_signals_in_window(
        session, now - timedelta(days=realtime_days), now
    )
    hist_rows = await fetch_signals_in_window(
        session, now - timedelta(days=historical_days), now
    )

    rt_signals = _rows_to_signals(rt_rows)
    hist_signals = _rows_to_signals(hist_rows)

    result = _lh_engine.compute(
        realtime_signals=rt_signals,
        historical_signals=hist_signals,
        window_days=realtime_days,
        historical_days=historical_days,
    )

    fault = _fault_engine.analyze(rt_signals + hist_signals, window_days=realtime_days)

    return {
        "escalation_index": result.escalation_index,
        "risk_tier": result.risk_tier,
        "threshold_breached": result.components.threshold_breached,
        "components": {
            "B": result.components.burden_of_restraint,
            "P": result.components.probability_of_harm,
            "L": result.components.loss_magnitude,
            "PL": result.components.expected_loss,
        },
        "dominant_signals": result.dominant_signals,
        "summary": result.summary,
        "comparative_fault": {
            "allocation": fault.fault_allocation,
            "primary_aggressor": fault.primary_aggressor,
            "signal_counts": fault.bloc_signal_counts,
        },
        "timestamp": result.timestamp.isoformat(),
    }


# ─── Trend data for 6-month graph ────────────────────────────────────────────

@router.get("/trend")
async def get_trend(
    bloc: str = Query(default="G7"),
    bucket_days: int = Query(default=7, ge=1, le=30),
    total_days: int = Query(default=180, ge=30, le=365),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    try:
        bloc_enum = ActorBloc(bloc.upper())
    except ValueError:
        raise HTTPException(400, f"Unknown bloc: {bloc}")

    now = datetime.now(timezone.utc)
    rows = await fetch_signals_in_window(
        session, now - timedelta(days=total_days), now
    )
    signals = _rows_to_signals(rows)
    trend = _fault_engine.get_bloc_trend(signals, bloc_enum, bucket_days, total_days)
    return {"bloc": bloc_enum.value, "trend": trend}


# ─── Assets ──────────────────────────────────────────────────────────────────

@router.get("/assets")
async def get_asset_predictions(
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)

    rt_rows = await fetch_signals_in_window(session, now - timedelta(days=7), now)
    hist_rows = await fetch_signals_in_window(session, now - timedelta(days=180), now)

    rt_signals = _rows_to_signals(rt_rows)
    hist_signals = _rows_to_signals(hist_rows)

    escalation = _lh_engine.compute(rt_signals, hist_signals)
    prediction = _asset_engine.predict(escalation)

    return {
        "escalation_index": prediction.escalation_index,
        "risk_tier": prediction.risk_tier,
        "de_dollarization_score": prediction.de_dollarization_score,
        "energy_disruption_score": prediction.energy_disruption_score,
        "short_term": [i.model_dump() for i in prediction.short_term],
        "mid_term": [i.model_dump() for i in prediction.mid_term],
        "long_term": [i.model_dump() for i in prediction.long_term],
        "summary": prediction.summary,
        "timestamp": prediction.timestamp.isoformat(),
    }


# ─── Claude Analysis ─────────────────────────────────────────────────────────

@router.post("/analysis")
async def run_analysis(
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    rt_rows = await fetch_signals_in_window(session, now - timedelta(days=7), now)
    hist_rows = await fetch_signals_in_window(session, now - timedelta(days=180), now)

    rt_signals = _rows_to_signals(rt_rows)
    hist_signals = _rows_to_signals(hist_rows)

    escalation = _lh_engine.compute(rt_signals, hist_signals)
    fault = _fault_engine.analyze(rt_signals + hist_signals)
    prediction = _asset_engine.predict(escalation)

    analysis = await _claude_svc.analyze_escalation(
        realtime_signals=rt_signals,
        historical_signals=hist_signals,
        escalation=escalation,
        fault_allocation=fault.fault_allocation,
    )

    strategy = await _claude_svc.generate_strategy_report(escalation, prediction, analysis)

    return {
        "escalation": {
            "index": escalation.escalation_index,
            "tier": escalation.risk_tier,
            "summary": escalation.summary,
        },
        "claude_analysis": analysis,
        "strategy_brief": strategy,
        "asset_prediction": {
            "short_term": [i.model_dump() for i in prediction.short_term],
            "de_dollarization_score": prediction.de_dollarization_score,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─── Historical crawl trigger ─────────────────────────────────────────────────

@router.post("/crawl/start")
async def start_historical_crawl(
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    from ..scrapers.historical import HistoricalScraper
    scraper = HistoricalScraper()

    async def _run() -> None:
        await scraper.run_full_crawl()

    background_tasks.add_task(_run)
    return {"status": "crawl_started", "message": "180-day historical crawl initiated in background"}


# ─── Escalation history ──────────────────────────────────────────────────────

@router.get("/history")
async def get_escalation_history(
    limit: int = Query(default=90, ge=1, le=180),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    rows = await fetch_escalation_history(session, limit=limit)
    history = [
        {
            "timestamp": r.timestamp.isoformat(),
            "escalation_index": r.escalation_index,
            "risk_tier": r.risk_tier,
            "threshold_breached": r.threshold_breached,
            "probability": r.probability_of_harm,
        }
        for r in rows
    ]
    return {"history": history, "count": len(history)}


# ─── Helper ──────────────────────────────────────────────────────────────────

def _rows_to_signals(rows: list) -> List[GeopoliticalSignal]:
    import json as _json
    signals = []
    for r in rows:
        try:
            kws = _json.loads(r.action_keywords) if r.action_keywords else []
        except Exception:
            kws = []
        signals.append(
            GeopoliticalSignal(
                id=r.id,
                timestamp=r.timestamp.replace(tzinfo=timezone.utc) if r.timestamp.tzinfo is None else r.timestamp,
                source=r.source,
                headline=r.headline,
                content_summary=r.content_summary or "",
                actor=r.actor or "",
                actor_bloc=ActorBloc(r.actor_bloc) if r.actor_bloc else ActorBloc.OTHER,
                severity=SignalSeverity(r.severity) if r.severity else SignalSeverity.LOW,
                action_keywords=kws,
                url=r.url or "",
                is_realtime=r.is_realtime,
            )
        )
    return signals
