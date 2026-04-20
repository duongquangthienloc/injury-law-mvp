"""
MODE A — Real-time scraper.
Polls RSS feeds every 60 seconds and stores geopolitical signals.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import feedparser
import httpx

from ..config import settings
from ..db.database import SessionLocal, save_signal
from ..models.signal import ActorBloc, GeopoliticalSignal, SignalSeverity, classify_bloc
from .semantic_filter import classify_headline, extract_actor_hint

logger = logging.getLogger(__name__)

# Official & high-quality geopolitical RSS feeds
RSS_FEEDS = [
    # Wire services
    ("Reuters World", "https://feeds.reuters.com/reuters/worldNews"),
    ("AP Top News", "https://feeds.apnews.com/rss/apf-topnews"),
    ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    # Official government / intergovernmental
    ("UN News", "https://news.un.org/feed/subscribe/en/news/all/rss.xml"),
    ("US State Dept", "https://www.state.gov/rss-feeds/press-releases/"),
    ("NATO News", "https://www.nato.int/cps/en/natolive/news.rss"),
    # Financial / geopolitical specialty
    ("Reuters Politics", "https://feeds.reuters.com/reuters/politicsNews"),
    ("FT World", "https://www.ft.com/world?format=rss"),
]

# Deduplicate by content hash to avoid reprocessing
_seen_hashes: set[str] = set()


def _content_hash(headline: str, source: str) -> str:
    return hashlib.md5(f"{source}:{headline}".encode()).hexdigest()


async def _fetch_feed(
    client: httpx.AsyncClient,
    name: str,
    url: str,
) -> List[GeopoliticalSignal]:
    signals: List[GeopoliticalSignal] = []
    try:
        resp = await client.get(url, timeout=15.0)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.text)

        for entry in parsed.entries[:20]:  # Limit per feed to control volume
            headline: str = getattr(entry, "title", "")
            if not headline:
                continue

            h = _content_hash(headline, name)
            if h in _seen_hashes:
                continue

            result = classify_headline(headline)
            if result is None:
                continue  # semantic filter: skip noise

            severity, keywords = result
            actor_hint = extract_actor_hint(headline)
            bloc = classify_bloc(actor_hint)

            pub_date = getattr(entry, "published_parsed", None)
            if pub_date:
                ts = datetime(*pub_date[:6], tzinfo=timezone.utc)
            else:
                ts = datetime.now(timezone.utc)

            signals.append(
                GeopoliticalSignal(
                    id=str(uuid.uuid4()),
                    timestamp=ts,
                    source=name,
                    headline=headline,
                    content_summary=getattr(entry, "summary", headline)[:500],
                    actor=actor_hint,
                    actor_bloc=bloc,
                    severity=severity,
                    action_keywords=keywords,
                    url=getattr(entry, "link", ""),
                    is_realtime=True,
                )
            )
            _seen_hashes.add(h)

    except Exception as exc:
        logger.warning("Feed %s fetch error: %s", name, exc)

    return signals


class RealtimeScraper:
    """MODE A: polls all RSS feeds every settings.realtime_poll_interval_seconds."""

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self.signal_buffer: List[GeopoliticalSignal] = []

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": "SENTINEL-X/2.0 geopolitical-research-bot"},
                follow_redirects=True,
            )
        return self._client

    async def poll_cycle(self) -> List[GeopoliticalSignal]:
        """Single poll cycle — called by APScheduler every 60s."""
        client = await self._get_client()
        tasks = [_fetch_feed(client, name, url) for name, url in RSS_FEEDS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        new_signals: List[GeopoliticalSignal] = []
        for r in results:
            if isinstance(r, list):
                new_signals.extend(r)

        if new_signals:
            async with SessionLocal() as session:
                for sig in new_signals:
                    await save_signal(session, {
                        "id": sig.id,
                        "timestamp": sig.timestamp,
                        "source": sig.source,
                        "headline": sig.headline,
                        "content_summary": sig.content_summary,
                        "actor": sig.actor,
                        "actor_bloc": sig.actor_bloc.value,
                        "severity": sig.severity.value,
                        "action_keywords": json.dumps(sig.action_keywords),
                        "url": sig.url or "",
                        "is_realtime": True,
                    })

            self.signal_buffer = (self.signal_buffer + new_signals)[-500:]
            logger.info("Real-time poll: %d new signals", len(new_signals))

        return new_signals

    def get_recent_signals(self, limit: int = 50) -> List[GeopoliticalSignal]:
        return self.signal_buffer[-limit:]

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
