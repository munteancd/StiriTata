from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
import respx

from generator.fetch_news import fetch_all_sources, parse_feed_bytes

FIXTURE = Path(__file__).parent / "fixtures" / "sample_feed.xml"


def test_parse_feed_bytes_returns_items_in_window():
    raw = FIXTURE.read_bytes()
    now = datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)

    items = parse_feed_bytes(
        raw,
        source_name="Example",
        category="national_politics",
        now=now,
        window_hours=24,
    )

    # Only the two fresh items (one will be deduped later at the aggregation stage).
    assert len(items) == 2
    assert all(it.source == "Example" for it in items)
    assert all(it.category == "national_politics" for it in items)
    assert all((now - it.published).total_seconds() <= 24 * 3600 for it in items)


@respx.mock
async def test_fetch_all_sources_aggregates_and_dedups():
    respx.get("https://a.example/feed").mock(
        return_value=httpx.Response(200, content=FIXTURE.read_bytes())
    )
    respx.get("https://b.example/feed").mock(
        return_value=httpx.Response(200, content=FIXTURE.read_bytes())
    )

    sources_cfg = {
        "national_politics": [
            {"name": "A", "url": "https://a.example/feed"},
            {"name": "B", "url": "https://b.example/feed"},
        ]
    }
    now = datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)

    items = await fetch_all_sources(sources_cfg, now=now, window_hours=24)

    # Dedup removes titles normalizing to the same form across sources.
    titles = {it.title for it in items}
    assert len(items) == len(titles)  # no exact-title dups in final list
    # There must be at most one "guvernul adopta masuri noi" after normalization.
    from generator.text_utils import normalize_title_for_dedup
    normalized = {normalize_title_for_dedup(t) for t in titles}
    assert len(normalized) == len(titles)


@respx.mock
async def test_fetch_all_sources_ignores_failing_feed():
    respx.get("https://ok.example/feed").mock(
        return_value=httpx.Response(200, content=FIXTURE.read_bytes())
    )
    respx.get("https://broken.example/feed").mock(
        return_value=httpx.Response(500, text="fail")
    )

    sources_cfg = {
        "national_politics": [
            {"name": "OK", "url": "https://ok.example/feed"},
            {"name": "Broken", "url": "https://broken.example/feed"},
        ]
    }
    now = datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)

    items = await fetch_all_sources(sources_cfg, now=now, window_hours=24)

    # Still returns items from the working source.
    assert len(items) >= 1
    assert all(it.source == "OK" for it in items)
