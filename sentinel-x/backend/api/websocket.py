"""
WebSocket Manager
Broadcasts real-time escalation updates to all connected War-Room dashboard clients.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

ws_router = APIRouter()


class WebSocketManager:
    """Manages active WebSocket connections and broadcasts payloads."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)
        logger.info("WS client connected. Total: %d", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)
        logger.info("WS client disconnected. Total: %d", len(self._connections))

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        if not self._connections:
            return
        message = json.dumps(payload)
        dead: List[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)

    async def broadcast_escalation(
        self,
        escalation_index: float,
        risk_tier: str,
        b: float,
        p: float,
        l: float,
        dominant_signals: List[str],
    ) -> None:
        await self.broadcast({
            "type": "ESCALATION_UPDATE",
            "data": {
                "escalation_index": escalation_index,
                "risk_tier": risk_tier,
                "b": b,
                "p": p,
                "l": l,
                "dominant_signals": dominant_signals,
            },
        })

    async def broadcast_signal(self, headline: str, severity: str, actor: str) -> None:
        await self.broadcast({
            "type": "NEW_SIGNAL",
            "data": {"headline": headline, "severity": severity, "actor": actor},
        })

    @property
    def connection_count(self) -> int:
        return len(self._connections)


ws_manager = WebSocketManager()


@ws_router.websocket("/ws/sentinel")
async def sentinel_websocket(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        # Heartbeat loop — keeps connection alive and sends status pings
        while True:
            try:
                # Wait for client ping (with 30s timeout)
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_text(json.dumps({"type": "HEARTBEAT"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as exc:
        logger.warning("WS error: %s", exc)
        ws_manager.disconnect(websocket)
