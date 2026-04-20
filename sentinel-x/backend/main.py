"""
SENTINEL-X V2 — FastAPI Application Entry Point
Time-Series Geopolitical Alpha Engine
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .api.websocket import ws_manager, ws_router
from .config import settings
from .db.database import init_db
from .engines.asset_mapper import AssetMapperEngine
from .engines.comparative_fault import ComparativeFaultEngine
from .engines.learned_hand import LearnedHandEngine
from .scrapers.realtime import RealtimeScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("sentinel_x")

# ─── Singletons ───────────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler(timezone="UTC")
realtime_scraper = RealtimeScraper()
lh_engine = LearnedHandEngine()
fault_engine = ComparativeFaultEngine()
asset_engine = AssetMapperEngine()


# ─── Scheduled tasks ──────────────────────────────────────────────────────────

async def _realtime_poll_and_broadcast() -> None:
    """Every 60s: scrape → compute escalation → broadcast to WS clients."""
    new_signals = await realtime_scraper.poll_cycle()

    if not new_signals:
        return

    recent = realtime_scraper.get_recent_signals(200)
    escalation = lh_engine.compute(
        realtime_signals=recent,
        historical_signals=[],  # DB-backed historical loaded separately
        window_days=7,
    )

    await ws_manager.broadcast_escalation(
        escalation_index=escalation.escalation_index,
        risk_tier=escalation.risk_tier,
        b=escalation.components.burden_of_restraint,
        p=escalation.components.probability_of_harm,
        l=escalation.components.loss_magnitude,
        dominant_signals=escalation.dominant_signals,
    )

    # Broadcast each new high-severity signal individually
    for sig in new_signals:
        if sig.severity.value >= 3:
            await ws_manager.broadcast_signal(
                headline=sig.headline,
                severity=sig.severity.name,
                actor=sig.actor,
            )

    logger.info(
        "Poll complete: %d new signals | EscIdx=%.1f | Tier=%s",
        len(new_signals),
        escalation.escalation_index,
        escalation.risk_tier,
    )


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SENTINEL-X V2 starting up...")
    await init_db()

    scheduler.add_job(
        _realtime_poll_and_broadcast,
        trigger="interval",
        seconds=settings.realtime_poll_interval_seconds,
        id="realtime_poll",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(
        "Real-time polling active (every %ds). SENTINEL-X online.",
        settings.realtime_poll_interval_seconds,
    )

    yield

    logger.info("SENTINEL-X shutting down...")
    scheduler.shutdown(wait=False)
    await realtime_scraper.close()


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SENTINEL-X V2",
    description="Time-Series Geopolitical Alpha Engine — Breach of Stability Duty Analysis",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/sentinel", tags=["SENTINEL-X"])
app.include_router(ws_router, tags=["WebSocket"])


@app.get("/", tags=["Health"])
async def root():
    return {
        "system": "SENTINEL-X V2",
        "status": "online",
        "endpoints": {
            "status":   "/api/sentinel/status",
            "signals":  "/api/sentinel/signals",
            "escalation": "/api/sentinel/escalation",
            "trend":    "/api/sentinel/trend",
            "assets":   "/api/sentinel/assets",
            "analysis": "/api/sentinel/analysis (POST)",
            "history":  "/api/sentinel/history",
            "crawl":    "/api/sentinel/crawl/start (POST)",
            "websocket": "/ws/sentinel",
        },
    }
