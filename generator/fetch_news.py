import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List

import feedparser
import httpx

from .models import NewsItem
from .text_utils import normalize_title_for_dedup

log = logging.getLogger(__name__)


def _entry_published(entry: Any) -> datetime | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed is None:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc)


def parse_feed_bytes(
    raw: bytes,
    *,
    source_name: str,
    category: str,
    now: datetime,
    window_hours: int = 24,
) -> List[NewsItem]:
    feed = feedparser.parse(raw)
    cutoff = now - timedelta(hours=window_hours)
    items: List[NewsItem] = []
    for entry in feed.entries:
        published = _entry_published(entry)
        if published is None or published < cutoff:
            continue
        items.append(
            NewsItem(
                title=(entry.get("title") or "").strip(),
                summary=(entry.get("summary") or entry.get("description") or "").strip(),
                url=(entry.get("link") or "").strip(),
                source=source_name,
                category=category,
                published=published,
            )
        )
    return items


async def _fetch_one(
    client: httpx.AsyncClient,
    *,
    name: str,
    url: str,
    category: str,
    now: datetime,
    window_hours: int,
) -> List[NewsItem]:
    try:
        resp = await client.get(url, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:
        log.warning("feed %s (%s) failed: %s", name, url, exc)
        return []
    return parse_feed_bytes(
        resp.content,
        source_name=name,
        category=category,
        now=now,
        window_hours=window_hours,
    )


def _dedup(items: Iterable[NewsItem]) -> List[NewsItem]:
    seen: set[str] = set()
    out: List[NewsItem] = []
    for item in items:
        key = normalize_title_for_dedup(item.title)
        if key in seen or not key:
            continue
        seen.add(key)
        out.append(item)
    return out


async def fetch_all_sources(
    sources_cfg: Dict[str, List[Dict[str, str]]],
    *,
    now: datetime | None = None,
    window_hours: int = 24,
) -> List[NewsItem]:
    now = now or datetime.now(tz=timezone.utc)
    tasks = []
    async with httpx.AsyncClient(headers={"User-Agent": "StiriTata/1.0"}) as client:
        for category, sources in sources_cfg.items():
            for src in sources:
                tasks.append(
                    _fetch_one(
                        client,
                        name=src["name"],
                        url=src["url"],
                        category=category,
                        now=now,
                        window_hours=window_hours,
                    )
                )
        results = await asyncio.gather(*tasks)
    flat = [item for sub in results for item in sub]
    return _dedup(flat)
