"""
MODE B — Deep history back-crawl.
Scrapes 3-6 months of diplomatic signals to establish the Baseline
"Standard of Conduct" for Learned Hand comparison.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx
from playwright.async_api import async_playwright, Browser, Page

from ..config import settings
from ..db.database import SessionLocal, save_signal
from ..models.signal import GeopoliticalSignal, classify_bloc
from .semantic_filter import classify_headline, extract_actor_hint

logger = logging.getLogger(__name__)

# Sources with pagination support for historical back-crawl
HISTORICAL_SOURCES: List[Dict[str, Any]] = [
    {
        "name": "UN Press Releases",
        "base_url": "https://press.un.org/en",
        "type": "playwright",
        "selector": "article.views-row",
        "headline_sel": "h3.field-content a",
        "date_sel": "span.date-display-single",
        "page_param": "?page={page}",
        "max_pages": 30,
    },
    {
        "name": "US State Dept Briefings",
        "base_url": "https://www.state.gov/press-releases/",
        "type": "playwright",
        "selector": "li.views-row",
        "headline_sel": "span.views-field-title a",
        "date_sel": "span.date-display-single",
        "page_param": "?page={page}",
        "max_pages": 20,
    },
    {
        "name": "Reuters World Archive",
        "base_url": "https://feeds.reuters.com/reuters/worldNews",
        "type": "rss_batch",
        "max_pages": 1,
    },
]

# Rate limit: 1 request per 2 seconds for polite crawling
_RATE_LIMIT_DELAY = 2.0


class HistoricalScraper:
    """
    MODE B: Back-crawls up to settings.historical_window_days of data.
    Establishes the 180-day Baseline for Breach of Stability Duty analysis.
    """

    def __init__(self) -> None:
        self.cutoff_date = datetime.now(timezone.utc) - timedelta(
            days=settings.historical_window_days
        )
        self._progress_callbacks: List[Callable[[str, int], None]] = []
        self._browser: Optional[Browser] = None

    def on_progress(self, cb: Callable[[str, int], None]) -> None:
        self._progress_callbacks.append(cb)

    def _emit(self, message: str, pct: int) -> None:
        for cb in self._progress_callbacks:
            try:
                cb(message, pct)
            except Exception:
                pass

    async def _start_browser(self) -> Browser:
        if self._browser is None:
            pw = await async_playwright().start()
            self._browser = await pw.chromium.launch(headless=True)
        return self._browser

    async def _scrape_playwright_source(
        self,
        source: Dict[str, Any],
        signals: List[GeopoliticalSignal],
    ) -> None:
        browser = await self._start_browser()
        page: Page = await browser.new_page()
        await page.set_extra_http_headers(
            {"User-Agent": "SENTINEL-X/2.0 geopolitical-research-bot"}
        )

        for page_num in range(source["max_pages"]):
            url = source["base_url"] + source["page_param"].format(page=page_num)
            try:
                await page.goto(url, timeout=30000)
                await asyncio.sleep(_RATE_LIMIT_DELAY)

                items = await page.query_selector_all(source["selector"])
                if not items:
                    break

                page_had_recent = False
                for item in items:
                    headline_el = await item.query_selector(source["headline_sel"])
                    if not headline_el:
                        continue
                    headline = (await headline_el.inner_text()).strip()

                    date_el = await item.query_selector(source.get("date_sel", ""))
                    date_str = ""
                    if date_el:
                        date_str = (await date_el.inner_text()).strip()

                    ts = _parse_date(date_str)
                    if ts < self.cutoff_date:
                        continue  # older than our window
                    page_had_recent = True

                    result = classify_headline(headline)
                    if result is None:
                        continue

                    severity, keywords = result
                    actor = extract_actor_hint(headline)
                    href = await headline_el.get_attribute("href") or ""

                    signals.append(GeopoliticalSignal(
                        id=str(uuid.uuid4()),
                        timestamp=ts,
                        source=source["name"],
                        headline=headline,
                        content_summary=headline,
                        actor=actor,
                        actor_bloc=classify_bloc(actor),
                        severity=severity,
                        action_keywords=keywords,
                        url=href,
                        is_realtime=False,
                    ))

                if not page_had_recent:
                    break  # All remaining pages are older than our window

            except Exception as exc:
                logger.warning("Playwright scrape error [%s p%d]: %s", source["name"], page_num, exc)
                break

        await page.close()

    async def run_full_crawl(self) -> List[GeopoliticalSignal]:
        """
        Execute full 180-day back-crawl. Stores results to DB and returns signal list.
        Designed to run once on startup or on explicit API trigger.
        """
        all_signals: List[GeopoliticalSignal] = []
        total = len(HISTORICAL_SOURCES)

        for i, source in enumerate(HISTORICAL_SOURCES):
            self._emit(f"Crawling {source['name']}...", int((i / total) * 100))
            try:
                if source["type"] == "playwright":
                    await self._scrape_playwright_source(source, all_signals)
                elif source["type"] == "rss_batch":
                    # RSS sources are handled by realtime scraper; skip here
                    pass
            except Exception as exc:
                logger.error("Historical crawl error [%s]: %s", source["name"], exc)

        # Persist to DB in batches
        async with SessionLocal() as session:
            for sig in all_signals:
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
                    "is_realtime": False,
                })

        self._emit("Historical crawl complete.", 100)
        logger.info("Historical crawl: %d signals stored", len(all_signals))
        return all_signals

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()


def _parse_date(date_str: str) -> datetime:
    from dateutil import parser as dp
    try:
        dt = dp.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.now(timezone.utc)
