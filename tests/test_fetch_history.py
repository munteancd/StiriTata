import json
from pathlib import Path

import httpx
import respx

from generator.fetch_history import (
    HISTORY_URL_EN,
    HISTORY_URL_RO,
    fetch_history,
    parse_history_response,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _ro_url(mm: int, dd: int) -> str:
    return HISTORY_URL_RO.format(mm=f"{mm:02d}", dd=f"{dd:02d}")


def _en_url(mm: int, dd: int) -> str:
    return HISTORY_URL_EN.format(mm=f"{mm:02d}", dd=f"{dd:02d}")


def test_parse_history_response_keeps_year_and_text():
    data = json.loads((FIXTURES / "history_response_ro.json").read_text(encoding="utf-8"))
    cands = parse_history_response(data, source_lang="ro")
    assert len(cands.events) == 3
    assert cands.events[0].year == 1999
    assert "Columbine" in cands.events[0].text
    assert cands.events[0].source_lang == "ro"
    assert len(cands.births) == 2
    assert len(cands.deaths) == 1


def test_parse_history_response_sorts_by_year_desc_and_caps_at_15():
    # Build a payload with 20 events spanning years 1900..1919
    data = {
        "events": [{"year": 1900 + i, "text": f"ev {i}", "pages": []} for i in range(20)],
        "births": [],
        "deaths": [],
    }
    cands = parse_history_response(data, source_lang="en")
    assert len(cands.events) == 15
    # Newest first
    assert cands.events[0].year == 1919
    assert cands.events[-1].year == 1905


@respx.mock
async def test_fetch_history_uses_ro_when_sufficient():
    respx.get(_ro_url(4, 20)).mock(
        return_value=httpx.Response(
            200, content=(FIXTURES / "history_response_ro.json").read_bytes()
        )
    )
    cands = await fetch_history(month=4, day=20)
    assert cands is not None
    # 3 events + 2 births + 1 death = 6 > 3, no fallback
    assert len(cands.events) == 3
    assert all(e.source_lang == "ro" for e in cands.events)


@respx.mock
async def test_fetch_history_falls_back_to_en_when_ro_thin():
    respx.get(_ro_url(4, 20)).mock(
        return_value=httpx.Response(
            200, content=(FIXTURES / "history_response_ro_thin.json").read_bytes()
        )
    )
    respx.get(_en_url(4, 20)).mock(
        return_value=httpx.Response(
            200, content=(FIXTURES / "history_response_en.json").read_bytes()
        )
    )
    cands = await fetch_history(month=4, day=20)
    assert cands is not None
    # RO had 1 event + 0 + 0 = 1 < 3 → fallback fetched
    # RO items come first (priority), then EN items merged
    ro_events = [e for e in cands.events if e.source_lang == "ro"]
    en_events = [e for e in cands.events if e.source_lang == "en"]
    assert len(ro_events) == 1
    assert len(en_events) == 2
    # Order: RO first, then EN
    assert cands.events[0].source_lang == "ro"
    assert cands.events[-1].source_lang == "en"


@respx.mock
async def test_fetch_history_returns_none_when_both_fail():
    respx.get(_ro_url(4, 20)).mock(return_value=httpx.Response(500))
    respx.get(_en_url(4, 20)).mock(return_value=httpx.Response(500))
    cands = await fetch_history(month=4, day=20)
    assert cands is None


@respx.mock
async def test_fetch_history_returns_ro_when_ro_thin_and_en_fails():
    # RO returns thin result (< 3 total) → EN fallback is triggered; EN fails (500).
    # We still return the thin RO candidates rather than None, because SOMETHING is
    # better than nothing for the LLM prompt. We only return None if RO itself failed
    # hard AND EN also failed.
    ro_thin = json.loads((FIXTURES / "history_response_ro_thin.json").read_text(encoding="utf-8"))
    respx.get(_ro_url(4, 20)).mock(return_value=httpx.Response(200, json=ro_thin))
    respx.get(_en_url(4, 20)).mock(return_value=httpx.Response(500))
    cands = await fetch_history(month=4, day=20)
    assert cands is not None
    total = len(cands.events) + len(cands.births) + len(cands.deaths)
    assert total < 3  # the whole point: thin result preserved
    assert all(it.source_lang == "ro" for it in cands.events)
