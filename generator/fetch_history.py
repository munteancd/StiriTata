import logging
from typing import Any, Dict, Optional

import httpx

from .models import HistoryCandidates, HistoryItem

log = logging.getLogger(__name__)

# Wikipedia REST API — "On This Day" feed. No API key required.
# MM and DD are zero-padded two-digit strings.
HISTORY_URL_RO = "https://ro.wikipedia.org/api/rest_v1/feed/onthisday/all/{mm}/{dd}"
HISTORY_URL_EN = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/all/{mm}/{dd}"

# Politeness header per Wikipedia's user-agent policy.
_USER_AGENT = (
    "StiriTata/1.0 (https://munteancd.github.io/StiriTata/; munteancd@gmail.com)"
)

# Max items per category we keep after sorting. The LLM doesn't need 200 candidates;
# 15 gives it ample choice per category without bloating the prompt.
_TOP_N_PER_CATEGORY = 15

# If RO returns fewer than this many TOTAL candidates (events + births + deaths),
# we also fetch EN and merge RO-first.
_MIN_RO_CANDIDATES = 3


def _parse_category(raw: list, source_lang: str) -> list[HistoryItem]:
    """Convert raw [{year, text, ...}, ...] list into sorted, capped HistoryItems."""
    items: list[HistoryItem] = []
    for entry in raw or []:
        try:
            year = int(entry["year"])
            text = str(entry["text"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if not text:
            continue
        items.append(HistoryItem(year=year, text=text, source_lang=source_lang))
    items.sort(key=lambda i: i.year, reverse=True)
    return items[:_TOP_N_PER_CATEGORY]


def parse_history_response(data: Dict[str, Any], *, source_lang: str) -> HistoryCandidates:
    return HistoryCandidates(
        events=_parse_category(data.get("events", []), source_lang),
        births=_parse_category(data.get("births", []), source_lang),
        deaths=_parse_category(data.get("deaths", []), source_lang),
    )


def _total(c: HistoryCandidates) -> int:
    return len(c.events) + len(c.births) + len(c.deaths)


def _merge(primary: HistoryCandidates, secondary: HistoryCandidates) -> HistoryCandidates:
    """RO items first, then EN items — per spec: 'Prioritizează evenimentele românești'."""
    def merge_list(a: list[HistoryItem], b: list[HistoryItem]) -> list[HistoryItem]:
        return (a + b)[:_TOP_N_PER_CATEGORY]

    return HistoryCandidates(
        events=merge_list(primary.events, secondary.events),
        births=merge_list(primary.births, secondary.births),
        deaths=merge_list(primary.deaths, secondary.deaths),
    )


async def _get(client: httpx.AsyncClient, url: str) -> Optional[Dict[str, Any]]:
    """One GET with one retry on transient failure. Returns None on permanent failure."""
    for attempt in range(2):
        try:
            resp = await client.get(url, timeout=15.0, headers={"User-Agent": _USER_AGENT})
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            log.warning("wiki history GET %s attempt %d failed: %s", url, attempt + 1, exc)
    return None


async def fetch_history(*, month: int, day: int) -> Optional[HistoryCandidates]:
    """Fetch 'on this day' candidates from Wikipedia.

    Always tries Romanian first. If RO returns fewer than 3 total candidates
    (or fails), we also fetch English and merge (RO first). Returns None only
    if both fail hard — the caller treats that like any other permanent
    section failure and uses the fallback line.
    """
    ro_url = HISTORY_URL_RO.format(mm=f"{month:02d}", dd=f"{day:02d}")
    en_url = HISTORY_URL_EN.format(mm=f"{month:02d}", dd=f"{day:02d}")

    async with httpx.AsyncClient() as client:
        ro_raw = await _get(client, ro_url)
        ro_cands = parse_history_response(ro_raw, source_lang="ro") if ro_raw else None

        if ro_cands is not None and _total(ro_cands) >= _MIN_RO_CANDIDATES:
            log.info("history: using RO only (%d total)", _total(ro_cands))
            return ro_cands

        en_raw = await _get(client, en_url)
        en_cands = parse_history_response(en_raw, source_lang="en") if en_raw else None

    if ro_cands is None and en_cands is None:
        log.warning("history: both RO and EN failed, returning None")
        return None
    if ro_cands is None:
        log.info("history: RO failed, using EN (%d total)", _total(en_cands))
        return en_cands
    if en_cands is None:
        log.info("history: EN failed, using RO thin (%d total)", _total(ro_cands))
        return ro_cands
    merged = _merge(ro_cands, en_cands)
    log.info(
        "history: merged RO (%d) + EN (%d) → %d total",
        _total(ro_cands), _total(en_cands), _total(merged),
    )
    return merged
