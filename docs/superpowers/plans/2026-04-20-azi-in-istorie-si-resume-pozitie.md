# „Azi în istorie" & Memorează poziția — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 1-minute „Azi în istorie" closing section to the daily bulletin (backend, Wikipedia-sourced), and add client-side pause-position resume to the PWA.

**Architecture:** Feature 1 is a new async Wikipedia fetcher (`generator/fetch_history.py`) wired into the existing parallel `asyncio.gather` in `main.py`, plus a 7th entry in `SECTIONS` consumed by the already-existing per-section OpenAI call loop. Feature 2 is pure frontend: `localStorage` keyed by bulletin date, save on pause/timeupdate/visibilitychange, restore on load after `loadedmetadata`, with a fading hint "Continuă de la M:SS". The two features are independent and can ship in separate commits.

**Tech Stack:** Python 3.11, httpx (async), pytest + respx (HTTP mocking), OpenAI SDK (existing), vanilla JS + localStorage (PWA), CSS transitions.

**Spec:** `docs/superpowers/specs/2026-04-20-azi-in-istorie-si-resume-pozitie-design.md`

---

## File Structure

**New files:**
- `generator/fetch_history.py` — async Wikipedia REST API client (RO primary, EN fallback)
- `tests/test_fetch_history.py` — unit tests with respx
- `tests/fixtures/history_response_ro.json` — sample Wikipedia response (many items)
- `tests/fixtures/history_response_ro_thin.json` — sample Wikipedia response (< 3 items, triggers EN fallback)
- `tests/fixtures/history_response_en.json` — sample English fallback response

**Modified files:**
- `generator/models.py` — add `HistoryItem`, `HistoryCandidates` dataclasses
- `generator/prompt.py` — add `history` section to `SECTIONS`, extend `build_section_user_prompt` signature
- `generator/summarize.py` — thread `history` through `summarize()` and `_call_section`; short-circuit when `history is None` for the history section
- `generator/main.py` — call `fetch_history` in the parallel `asyncio.gather`, pass result to `summarize`
- `tests/test_summarize.py` — update tests broken by the new section (count expectations, sample fixtures)
- `tests/test_main.py` — patch `fetch_history` in existing pipeline tests
- `pwa/app.js` — add save/restore/cleanup logic and hint rendering
- `pwa/index.html` — add hidden hint element
- `pwa/style.css` — style the hint with fade-out transition

---

## Feature 1: „Azi în istorie" (backend)

### Task 1: Add history data models

**Files:**
- Modify: `generator/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write failing test**

Open `tests/test_models.py`. Add at the end:

```python
def test_history_item_fields():
    from generator.models import HistoryItem
    h = HistoryItem(year=1905, text="Jules Verne publică ultimul său roman.", source_lang="ro")
    assert h.year == 1905
    assert h.text.startswith("Jules Verne")
    assert h.source_lang == "ro"


def test_history_candidates_defaults_empty():
    from generator.models import HistoryCandidates, HistoryItem
    c = HistoryCandidates(
        events=[HistoryItem(year=1905, text="t", source_lang="ro")],
        births=[],
        deaths=[],
    )
    assert len(c.events) == 1
    assert c.births == []
    assert c.deaths == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py::test_history_item_fields tests/test_models.py::test_history_candidates_defaults_empty -v`
Expected: FAIL with `ImportError: cannot import name 'HistoryItem'`.

- [ ] **Step 3: Add the dataclasses**

Append to `generator/models.py`:

```python
@dataclass
class HistoryItem:
    year: int
    text: str
    source_lang: str  # "ro" or "en"


@dataclass
class HistoryCandidates:
    events: List["HistoryItem"]
    births: List["HistoryItem"]
    deaths: List["HistoryItem"]
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_models.py -v`
Expected: PASS (all tests green, including the two new ones).

- [ ] **Step 5: Commit**

```bash
git add generator/models.py tests/test_models.py
git commit -m "feat(models): add HistoryItem and HistoryCandidates dataclasses"
```

---

### Task 2: Create Wikipedia history fetcher

**Files:**
- Create: `generator/fetch_history.py`
- Create: `tests/test_fetch_history.py`
- Create: `tests/fixtures/history_response_ro.json`
- Create: `tests/fixtures/history_response_ro_thin.json`
- Create: `tests/fixtures/history_response_en.json`

- [ ] **Step 1: Create fixture `history_response_ro.json`**

Create `tests/fixtures/history_response_ro.json` with a realistic Wikipedia "on this day" payload containing multiple events, births, and deaths. Exact content:

```json
{
  "events": [
    {"year": 1945, "text": "Armata Roșie încercuiește Berlinul la sfârșitul celui de-al Doilea Război Mondial.", "pages": []},
    {"year": 1972, "text": "Apollo 16 aselenizează pe Lună în regiunea Descartes.", "pages": []},
    {"year": 1999, "text": "Masacrul de la liceul Columbine din statul Colorado, Statele Unite.", "pages": []}
  ],
  "births": [
    {"year": 1889, "text": "Adolf Hitler, politician austriac, lider nazist.", "pages": []},
    {"year": 1951, "text": "Luca Turilli, compozitor și chitarist italian.", "pages": []}
  ],
  "deaths": [
    {"year": 1912, "text": "Bram Stoker, scriitor irlandez, autorul romanului Dracula.", "pages": []}
  ],
  "holidays": [],
  "selected": []
}
```

- [ ] **Step 2: Create fixture `history_response_ro_thin.json`**

Create `tests/fixtures/history_response_ro_thin.json` — fewer than 3 items total to trigger EN fallback:

```json
{
  "events": [
    {"year": 1877, "text": "Războiul de Independență — un eveniment din spațiul românesc.", "pages": []}
  ],
  "births": [],
  "deaths": [],
  "holidays": [],
  "selected": []
}
```

- [ ] **Step 3: Create fixture `history_response_en.json`**

Create `tests/fixtures/history_response_en.json`:

```json
{
  "events": [
    {"year": 1902, "text": "Pierre and Marie Curie refine radium chloride.", "pages": []},
    {"year": 1972, "text": "Apollo 16 lands on the Moon in the Descartes Highlands.", "pages": []}
  ],
  "births": [
    {"year": 1893, "text": "Harold Lloyd, American actor and comedian.", "pages": []}
  ],
  "deaths": [
    {"year": 1912, "text": "Bram Stoker, Irish novelist, author of Dracula.", "pages": []}
  ],
  "holidays": [],
  "selected": []
}
```

- [ ] **Step 4: Write failing tests**

Create `tests/test_fetch_history.py`:

```python
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
    assert cands.events[0].year == 1945
    assert "Berlin" in cands.events[0].text
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
async def test_fetch_history_returns_none_when_ro_fails_and_en_fails():
    # RO returns thin result → fallback triggered; EN fails → overall return is what RO had
    # but caller doesn't need EN to succeed if RO had anything — we return RO even when thin
    # (LLM gets fewer candidates but still some). We only return None if RO itself failed
    # hard AND EN also failed.
    respx.get(_ro_url(4, 20)).mock(return_value=httpx.Response(500))
    respx.get(_en_url(4, 20)).mock(return_value=httpx.Response(500))
    cands = await fetch_history(month=4, day=20)
    assert cands is None
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `pytest tests/test_fetch_history.py -v`
Expected: FAIL with `ImportError: cannot import name 'fetch_history' from 'generator.fetch_history'` (module doesn't exist yet).

- [ ] **Step 6: Implement `generator/fetch_history.py`**

Create `generator/fetch_history.py`:

```python
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
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_fetch_history.py -v`
Expected: PASS (all 6 tests green).

- [ ] **Step 8: Commit**

```bash
git add generator/fetch_history.py tests/test_fetch_history.py tests/fixtures/history_response_ro.json tests/fixtures/history_response_ro_thin.json tests/fixtures/history_response_en.json
git commit -m "feat(fetch_history): async Wikipedia 'on this day' client with RO primary + EN fallback"
```

---

### Task 3: Add `history` section to prompt builder

**Files:**
- Modify: `generator/prompt.py`
- Modify: `tests/test_summarize.py` (add test for history prompt shape)

- [ ] **Step 1: Write failing test for prompt shape**

Add to `tests/test_summarize.py` (at top, next to other imports — add import for new types):

```python
from generator.models import HistoryCandidates, HistoryItem, NewsItem, WeatherReport
from generator.prompt import (
    OUTRO,
    SECTIONS,
    SYSTEM_PROMPT,
    build_intro,
    build_section_user_prompt,
    build_user_prompt,
)
```

Then add these helper and test near the existing `_sample_items` / `_sample_weather` helpers:

```python
def _sample_history() -> HistoryCandidates:
    return HistoryCandidates(
        events=[
            HistoryItem(year=1945, text="Armata Roșie încercuiește Berlinul.", source_lang="ro"),
            HistoryItem(year=1999, text="Masacrul de la Columbine.", source_lang="ro"),
        ],
        births=[
            HistoryItem(year=1951, text="Luca Turilli, compozitor italian.", source_lang="ro"),
        ],
        deaths=[
            HistoryItem(year=1912, text="Bram Stoker, autorul lui Dracula.", source_lang="ro"),
        ],
    )


def test_history_section_is_last_before_outro():
    """The history section sits between football_eu and the outro."""
    keys = [s.key for s in SECTIONS]
    assert keys[-1] == "history"
    assert "football_eu" in keys
    assert keys.index("football_eu") == keys.index("history") - 1


def test_build_section_user_prompt_for_history_includes_candidates():
    history_section = next(s for s in SECTIONS if s.key == "history")
    prompt = build_section_user_prompt(
        section=history_section,
        items=[],
        weather=None,
        bulletin_date=datetime(2026, 4, 20, 6, 0, tzinfo=timezone.utc),
        history=_sample_history(),
    )
    # Contains events, births, deaths with years and text
    assert "1945" in prompt
    assert "Berlinul" in prompt
    assert "1951" in prompt
    assert "Turilli" in prompt
    assert "1912" in prompt
    assert "Stoker" in prompt


def test_build_section_user_prompt_for_non_history_ignores_history_kwarg():
    """Passing history= to a non-history section is harmless."""
    football_section = next(s for s in SECTIONS if s.key == "football_eu")
    prompt = build_section_user_prompt(
        section=football_section,
        items=_sample_items(),
        weather=None,
        bulletin_date=datetime(2026, 4, 20, 6, 0, tzinfo=timezone.utc),
        history=_sample_history(),
    )
    # History content should not leak into a non-history section
    assert "Stoker" not in prompt
    assert "Turilli" not in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_summarize.py::test_history_section_is_last_before_outro tests/test_summarize.py::test_build_section_user_prompt_for_history_includes_candidates -v`
Expected: FAIL — `history` section does not exist; `build_section_user_prompt` does not accept `history` kwarg.

- [ ] **Step 3: Extend `build_section_user_prompt` signature and add history formatter**

Edit `generator/prompt.py`. Add these imports at the top (after existing imports):

```python
from .models import HistoryCandidates, HistoryItem, NewsItem, WeatherReport
```

(Replace the existing `from .models import NewsItem, WeatherReport` line.)

Add a formatter helper next to `_format_weather_block`:

```python
def _format_history_block(history: Optional["HistoryCandidates"]) -> str:
    if history is None or (
        not history.events and not history.births and not history.deaths
    ):
        return "(candidați istorici indisponibili astăzi)"
    lines: list[str] = []

    def _append_section(label: str, entries: List["HistoryItem"]) -> None:
        if not entries:
            return
        lines.append(label)
        for it in entries:
            tag = "[RO]" if it.source_lang == "ro" else "[EN]"
            lines.append(f"- {it.year} {tag} {it.text}")
        lines.append("")

    _append_section("EVENIMENTE:", history.events)
    _append_section("NAȘTERI:", history.births)
    _append_section("DECESE:", history.deaths)
    return "\n".join(lines).rstrip()
```

Change the `build_section_user_prompt` signature to accept `history`:

```python
def build_section_user_prompt(
    *,
    section: Section,
    items: List[NewsItem],
    weather: Optional[WeatherReport],
    bulletin_date: datetime,
    history: Optional[HistoryCandidates] = None,
) -> str:
```

Inside the function, replace the `if section.key == "meteo": ... else: ...` block with a three-way dispatch:

```python
    if section.key == "meteo":
        parts.append("DATE DE INPUT:")
        parts.append(_format_weather_block(weather))
    elif section.key == "history":
        parts.append("DATE DE INPUT (AZI ÎN ISTORIE — candidați Wikipedia):")
        parts.append(_format_history_block(history))
    else:
        # News section — include the matching category
        cat_items = [it for it in items if it.category == section.key]
        parts.append(f"DATE DE INPUT ({CATEGORY_HEADERS.get(section.key, section.key)}):")
        parts.append(_format_items_block(cat_items))
```

- [ ] **Step 4: Add `history` entry to `SECTIONS`**

Still in `generator/prompt.py`, append a new `Section` to the end of the `SECTIONS` list (after `football_eu`):

```python
    Section(
        key="history",
        intro_phrase="Înainte de a încheia, câteva momente din istoria zilei de astăzi.",
        target_words=150,
        min_words=120,
        guidance=(
            "Alege 2 până la 3 momente istorice relevante din candidații furnizați. "
            "Prioritizează evenimentele românești [RO] dacă există; completează cu "
            "[EN] doar dacă e nevoie. Stil conversațional, „știați că" — nu listă "
            "seacă. Pentru fiecare moment, scrie anul în CUVINTE (de exemplu „o mie "
            "nouă sute patruzeci și cinci"). Tranziții naturale între momente "
            "(„Tot pe această zi", „Iar în"). Nu inventa evenimente care nu apar "
            "în listă."
        ),
    ),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_summarize.py::test_history_section_is_last_before_outro tests/test_summarize.py::test_build_section_user_prompt_for_history_includes_candidates tests/test_summarize.py::test_build_section_user_prompt_for_non_history_ignores_history_kwarg -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add generator/prompt.py tests/test_summarize.py
git commit -m "feat(prompt): add 'history' section to SECTIONS and plumb HistoryCandidates through build_section_user_prompt"
```

---

### Task 4: Thread `history` through `summarize()`

**Files:**
- Modify: `generator/summarize.py`
- Modify: `tests/test_summarize.py` (update existing tests broken by new section count; add history-specific tests)

- [ ] **Step 1: Write failing test — history=None short-circuits without API call**

Add to `tests/test_summarize.py`:

```python
def test_summarize_history_none_short_circuits_to_fallback_without_api_call():
    """When history is None, the history section uses fallback text and does NOT call OpenAI."""
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="OK"))]
    )

    text = summarize(
        items=_sample_items(),
        weather=_sample_weather(),
        bulletin_date=datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc),
        client=fake_client,
        model="gpt-4o-mini",
        history=None,
    )

    # One fewer call than sections — history was short-circuited
    assert fake_client.chat.completions.create.call_count == len(SECTIONS) - 1
    # Fallback line present for the history slot
    assert "nu avem informații" in text.lower()


def test_summarize_history_passed_reaches_api_call():
    """When history is provided, the history section does call OpenAI and its content ends up in the prompt."""
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="OK"))]
    )

    summarize(
        items=_sample_items(),
        weather=_sample_weather(),
        bulletin_date=datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc),
        client=fake_client,
        model="gpt-4o-mini",
        history=_sample_history(),
    )

    assert fake_client.chat.completions.create.call_count == len(SECTIONS)
    # At least one call's user prompt mentions our sample history item
    user_prompts = [
        call.kwargs["messages"][1]["content"]
        for call in fake_client.chat.completions.create.call_args_list
    ]
    assert any("Berlinul" in p for p in user_prompts)
```

- [ ] **Step 2: Update existing tests broken by new section count**

The existing test `test_summarize_tolerates_a_couple_section_failures` hardcodes `assert text.count("OK_SECTION") == 4` (assumed 6 sections - 2 failures = 4). With 7 sections, this becomes 5. And it must now pass `history=_sample_history()` to keep all sections reaching the API.

Replace the body of `test_summarize_tolerates_a_couple_section_failures` with:

```python
def test_summarize_tolerates_a_couple_section_failures():
    """Up to max_section_failures (default 2) bad sections → bulletin still returned."""
    fake_client = MagicMock()

    # Craft: first 2 sections fail permanently (each hit 3 times = 6 calls),
    # remaining sections succeed on first try.
    call_log = {"n": 0}

    def flaky(**kwargs):
        call_log["n"] += 1
        if call_log["n"] <= 6:  # First 2 sections × 3 attempts each
            raise RuntimeError("transient")
        return MagicMock(choices=[MagicMock(message=MagicMock(content="OK_SECTION"))])

    fake_client.chat.completions.create.side_effect = flaky

    text = summarize(
        items=_sample_items(),
        weather=_sample_weather(),
        bulletin_date=datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc),
        client=fake_client,
        model="gpt-4o-mini",
        max_retries=2,
        retry_sleep=0.0,
        max_section_failures=2,
        history=_sample_history(),
    )

    intro = build_intro(datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc))
    assert text.startswith(intro)
    assert text.endswith(OUTRO)
    # (len(SECTIONS) - 2) real sections present
    assert text.count("OK_SECTION") == len(SECTIONS) - 2
    # 2 fallback lines present
    assert "nu avem informații" in text.lower() or "trecem mai departe" in text.lower()
```

Also update `test_summarize_calls_openai_per_section_and_concatenates` and `test_summarize_raises_when_too_many_sections_fail` and `test_summarize_retries_transient_failure_then_succeeds` to pass `history=_sample_history()`. For each, add a single line `history=_sample_history(),` inside the `summarize(...)` call.

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_summarize.py -v`
Expected: FAIL on new history tests AND on the existing tests that now expect `history=` kwarg, because `summarize()` doesn't accept `history` yet.

- [ ] **Step 4: Update `summarize.py` to thread `history`**

Edit `generator/summarize.py`. Add import:

```python
from .models import HistoryCandidates, NewsItem, WeatherReport
```

(Replace the existing `from .models import NewsItem, WeatherReport`.)

Update `_call_section` signature to accept `history` and pass it to the user-prompt builder:

```python
def _call_section(
    *,
    section: Section,
    items: List[NewsItem],
    weather: Optional[WeatherReport],
    history: Optional[HistoryCandidates],
    bulletin_date: datetime,
    client: Any,
    model: str,
    max_retries: int,
    retry_sleep: float,
) -> str:
    """Generate the text for a single bulletin section via one OpenAI call."""
    # Short-circuit: if this is the history section but we have no candidates,
    # skip the API call entirely and use the fallback. Saves ~$0.01 and avoids
    # sending the model an empty candidate list that would yield "no info available".
    if section.key == "history" and history is None:
        log.info("section history: no candidates, using fallback without API call")
        return _SECTION_FALLBACK

    system_prompt = build_section_system_prompt(section)
    user_prompt = build_section_user_prompt(
        section=section,
        items=items,
        weather=weather,
        bulletin_date=bulletin_date,
        history=history,
    )
    # ... (rest of function unchanged)
```

Update `summarize` signature to accept `history` and pass it to `_call_section`:

```python
def summarize(
    *,
    items: List[NewsItem],
    weather: Optional[WeatherReport],
    bulletin_date: datetime,
    client: Any,
    model: str = "gpt-4o",
    max_retries: int = 2,
    retry_sleep: float = 2.0,
    max_section_failures: int = 2,
    history: Optional[HistoryCandidates] = None,
) -> str:
```

Inside `summarize`, in the `for section in SECTIONS:` loop, pass `history=history` to `_call_section`:

```python
    for section in SECTIONS:
        text = _call_section(
            section=section,
            items=items,
            weather=weather,
            history=history,
            bulletin_date=bulletin_date,
            client=client,
            model=model,
            max_retries=max_retries,
            retry_sleep=retry_sleep,
        )
```

- [ ] **Step 5: Run tests to verify all pass**

Run: `pytest tests/test_summarize.py -v`
Expected: PASS (all tests green, including new history tests and updated existing ones).

- [ ] **Step 6: Commit**

```bash
git add generator/summarize.py tests/test_summarize.py
git commit -m "feat(summarize): thread HistoryCandidates through summarize(); short-circuit history section when candidates are None"
```

---

### Task 5: Wire `fetch_history` into the pipeline

**Files:**
- Modify: `generator/main.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Update existing main tests to patch `fetch_history`**

Existing tests in `tests/test_main.py` patch `fetch_all_sources` and `fetch_weather`. They must now also patch `fetch_history`, or the real Wikipedia call will be attempted during tests (or fail to resolve, causing hangs/errors).

In each of the three existing `with patch(...)` blocks, add a `fetch_history` patch:

```python
    with patch("generator.main.fetch_all_sources", AsyncMock(return_value=_one_item())), \
         patch("generator.main.fetch_weather", AsyncMock(return_value=_wr())), \
         patch("generator.main.fetch_history", AsyncMock(return_value=None)), \
         patch("generator.main.synthesize", return_value=600.0) as tts_mock:
```

Do this for all three test functions (`test_pipeline_writes_mp3_and_manifest`, `test_pipeline_preserves_previous_mp3_on_summarize_failure`, `test_pipeline_trims_archive_to_last_7_days`). For the second test (the one without `synthesize`), the pattern is:

```python
    with patch("generator.main.fetch_all_sources", AsyncMock(return_value=_one_item())), \
         patch("generator.main.fetch_weather", AsyncMock(return_value=_wr())), \
         patch("generator.main.fetch_history", AsyncMock(return_value=None)):
```

- [ ] **Step 2: Add new test — `fetch_history` is called in parallel and result is passed to `summarize`**

Add to `tests/test_main.py`:

```python
async def test_pipeline_passes_history_to_summarize(tmp_path: Path):
    from generator.models import HistoryCandidates, HistoryItem

    public = tmp_path / "public"
    archive = public / "archive"

    sources_cfg = {
        "national_politics": [{"name": "X", "url": "https://x.example/feed"}],
        "weather": {"city": "Reșița", "country": "RO", "lat": 45.3, "lon": 21.88},
    }

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Text."))]
    )

    sample_history = HistoryCandidates(
        events=[HistoryItem(year=1945, text="Berlinul.", source_lang="ro")],
        births=[],
        deaths=[],
    )

    def _mk_mp3(*, text, out_mp3, config):
        out_mp3.parent.mkdir(parents=True, exist_ok=True)
        out_mp3.write_bytes(b"ID3")
        return 600.0

    with patch("generator.main.fetch_all_sources", AsyncMock(return_value=_one_item())), \
         patch("generator.main.fetch_weather", AsyncMock(return_value=_wr())), \
         patch("generator.main.fetch_history", AsyncMock(return_value=sample_history)) as hist_mock, \
         patch("generator.main.synthesize", side_effect=_mk_mp3), \
         patch("generator.main.summarize", return_value="Buletin.") as sum_mock:
        await run_pipeline(
            sources_cfg=sources_cfg,
            public_dir=public,
            archive_dir=archive,
            openai_client=fake_openai,
            openweather_api_key="k",
            now=datetime(2026, 4, 20, 6, 0, tzinfo=timezone.utc),
        )

    # fetch_history was awaited with (month=4, day=20)
    hist_mock.assert_awaited_once_with(month=4, day=20)
    # summarize received our sample history
    _, kwargs = sum_mock.call_args
    assert kwargs["history"] is sample_history
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_main.py -v`
Expected: FAIL — `generator.main` doesn't import or use `fetch_history` yet.

- [ ] **Step 4: Update `generator/main.py`**

Edit `generator/main.py`. Add the import:

```python
from .fetch_history import fetch_history
```

(Place it near the existing `from .fetch_weather import fetch_weather`.)

In `run_pipeline`, change the fetch block. Currently:

```python
    # 1. Fetch news + weather concurrently
    news_task = fetch_all_sources(rss_cfg, now=now)
    weather_task = fetch_weather(
        api_key=openweather_api_key,
        lat=float(weather_cfg.get("lat", 45.3)),
        lon=float(weather_cfg.get("lon", 21.8833)),
        city=weather_cfg.get("city", "Reșița"),
    )
    items, weather = await asyncio.gather(news_task, weather_task)
    log.info("fetched %d news items, weather=%s", len(items), bool(weather))
```

Replace with:

```python
    # 1. Fetch news + weather + history concurrently
    news_task = fetch_all_sources(rss_cfg, now=now)
    weather_task = fetch_weather(
        api_key=openweather_api_key,
        lat=float(weather_cfg.get("lat", 45.3)),
        lon=float(weather_cfg.get("lon", 21.8833)),
        city=weather_cfg.get("city", "Reșița"),
    )
    history_task = fetch_history(month=now.month, day=now.day)
    items, weather, history = await asyncio.gather(news_task, weather_task, history_task)
    log.info(
        "fetched %d news items, weather=%s, history=%s",
        len(items), bool(weather), bool(history),
    )
```

In the same function, update the `summarize(...)` call to pass `history`:

```python
        text = summarize(
            items=items,
            weather=weather,
            bulletin_date=now,
            client=openai_client,
            history=history,
        )
```

- [ ] **Step 5: Run full test suite to verify**

Run: `pytest -v`
Expected: PASS — all tests green across all files (models, fetch_history, summarize, main, and all pre-existing tests).

- [ ] **Step 6: Commit**

```bash
git add generator/main.py tests/test_main.py
git commit -m "feat(main): fetch 'on this day' in parallel with news+weather and pass to summarize"
```

---

### Task 6: End-to-end smoke test (local run)

**Files:** none modified — this is a manual verification step.

- [ ] **Step 1: Confirm env vars are set**

Run:
```bash
python -c "import os; print('OPENAI:', bool(os.environ.get('OPENAI_API_KEY')), 'OWM:', bool(os.environ.get('OPENWEATHER_API_KEY')))"
```
Expected: `OPENAI: True OWM: True`. If not, load `.env` or export manually.

- [ ] **Step 2: Run the generator against a scratch output dir**

Run:
```bash
python -m generator.main --sources sources.yaml --public-dir scratch_output
```
Expected: Process finishes without error; creates `scratch_output/latest.mp3`, `scratch_output/latest.json`, `scratch_output/latest.txt`.

- [ ] **Step 3: Inspect the bulletin text for the history section**

Open `scratch_output/latest.txt` and verify:
- Contains the intro phrase `Înainte de a încheia, câteva momente din istoria zilei de astăzi.`
- Contains at least one year written in words (e.g. "o mie nouă sute...")
- Does NOT end with a wrap-up phrase (no "Acestea au fost", no "În concluzie")
- Total length looks roughly ~14 min worth of content

- [ ] **Step 4: Listen to the MP3 (optional, sanity check)**

Play `scratch_output/latest.mp3` and confirm the history section sounds natural and the bulletin closes with "O zi bună, Ilie!" after it.

- [ ] **Step 5: Clean up scratch output**

Run:
```bash
rm -rf scratch_output
```

No commit for this task — it's verification only.

---

## Feature 2: Memorează poziția (frontend)

Per the spec: no automated tests for this feature — comportament verificabil vizual. One task, split into clean steps.

### Task 7: Add position save/restore with hint UI

**Files:**
- Modify: `pwa/index.html` — add hint element
- Modify: `pwa/style.css` — hint styling with fade-out transition
- Modify: `pwa/app.js` — save/restore/cleanup logic

- [ ] **Step 1: Add the hint element to `index.html`**

Edit `pwa/index.html`. Add the hint element immediately AFTER the `<p class="app__date" id="bulletin-date">...</p>` line and BEFORE the `<button id="play-btn" ...>` line:

```html
    <p class="resume-hint" id="resume-hint" aria-live="polite" hidden></p>
```

- [ ] **Step 2: Add hint styles to `style.css`**

Append to `pwa/style.css`:

```css
.resume-hint {
  margin: 0;
  font-size: 14px;
  color: var(--muted);
  opacity: 1;
  transition: opacity 600ms ease-out;
  min-height: 1.2em;
}

.resume-hint--fading {
  opacity: 0;
}
```

- [ ] **Step 3: Add the position logic to `app.js`**

Edit `pwa/app.js`. Inside the existing IIFE, after the `wakeLock` declaration and BEFORE the `formatDateRo` function, add the position-persistence helpers:

```javascript
  // --- position persistence (Feature 2) ---

  const POSITION_KEY_PREFIX = "stiritata:position:";
  const POSITION_SAVE_THROTTLE_MS = 10_000;
  const POSITION_MIN_SECONDS = 10; // below this, don't bother restoring
  const HINT_FADE_DELAY_MS = 5_000;

  let currentBulletinDate = null; // ISO YYYY-MM-DD from manifest
  let lastSavedAt = 0;

  function positionKey(date) {
    return POSITION_KEY_PREFIX + date;
  }

  function safeGet(key) {
    try { return localStorage.getItem(key); } catch (_) { return null; }
  }
  function safeSet(key, value) {
    try { localStorage.setItem(key, value); } catch (_) { /* quota/private mode */ }
  }
  function safeRemove(key) {
    try { localStorage.removeItem(key); } catch (_) { /* ignore */ }
  }

  function savePosition() {
    if (!currentBulletinDate) return;
    const pos = audio.currentTime;
    if (!Number.isFinite(pos) || pos < POSITION_MIN_SECONDS) return;
    safeSet(positionKey(currentBulletinDate), String(pos));
  }

  function clearPosition() {
    if (!currentBulletinDate) return;
    safeRemove(positionKey(currentBulletinDate));
  }

  function pruneOldPositionKeys(keepDate) {
    try {
      const currentKey = positionKey(keepDate);
      const toDelete = [];
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.startsWith(POSITION_KEY_PREFIX) && k !== currentKey) {
          toDelete.push(k);
        }
      }
      toDelete.forEach(safeRemove);
    } catch (_) { /* ignore */ }
  }

  function showResumeHint(seconds) {
    const hintEl = document.getElementById("resume-hint");
    if (!hintEl) return;
    hintEl.textContent = `Continuă de la ${formatTime(seconds)}`;
    hintEl.hidden = false;
    hintEl.classList.remove("resume-hint--fading");
    // Double rAF to let the browser paint the initial opacity:1 state before transitioning.
    requestAnimationFrame(() => requestAnimationFrame(() => {
      setTimeout(() => hintEl.classList.add("resume-hint--fading"), HINT_FADE_DELAY_MS);
    }));
  }

  function restorePositionOnce() {
    if (!currentBulletinDate) return;
    const raw = safeGet(positionKey(currentBulletinDate));
    if (raw === null) return;
    const pos = parseFloat(raw);
    if (!Number.isFinite(pos) || pos <= POSITION_MIN_SECONDS) return;

    const applyWhenReady = () => {
      const dur = audio.duration;
      if (!Number.isFinite(dur) || dur <= 0) return; // metadata still not ready
      if (pos >= dur) return; // corrupted / desynced
      audio.currentTime = pos;
      showResumeHint(pos);
    };

    if (Number.isFinite(audio.duration) && audio.duration > 0) {
      applyWhenReady();
    } else {
      audio.addEventListener("loadedmetadata", applyWhenReady, { once: true });
    }
  }
```

- [ ] **Step 4: Wire save/restore into the existing lifecycle in `app.js`**

Still in `pwa/app.js`:

(a) Inside `loadManifestAndAudio`, right after `dateEl.textContent = ...` and BEFORE `audio.src = ...`, set the bulletin date and prune old keys:

```javascript
      currentBulletinDate = manifest.date;
      pruneOldPositionKeys(currentBulletinDate);
```

Then, after `setupMediaSession(...)` in the same function, add:

```javascript
      restorePositionOnce();
```

(b) In the `audio.addEventListener("pause", ...)` line, extend the handler to also save:

Replace:
```javascript
  audio.addEventListener("pause", () => { setPlayIcon(false); releaseWakeLock(); });
```

With:
```javascript
  audio.addEventListener("pause", () => {
    setPlayIcon(false);
    releaseWakeLock();
    savePosition();
  });
```

(c) Extend the `ended` handler to clear position:

Replace:
```javascript
  audio.addEventListener("ended", () => { setPlayIcon(false); releaseWakeLock(); });
```

With:
```javascript
  audio.addEventListener("ended", () => {
    setPlayIcon(false);
    releaseWakeLock();
    clearPosition();
  });
```

(d) Extend the existing `timeupdate` listener — currently just updates the UI. Add throttled save at the bottom of its handler:

Replace the existing:
```javascript
  audio.addEventListener("timeupdate", () => {
    const cur = audio.currentTime || 0;
    const dur = audio.duration || 0;
    timeCurrent.textContent = formatTime(cur);
    if (dur > 0) {
      progressBar.style.width = `${(cur / dur) * 100}%`;
    }
  });
```

With:
```javascript
  audio.addEventListener("timeupdate", () => {
    const cur = audio.currentTime || 0;
    const dur = audio.duration || 0;
    timeCurrent.textContent = formatTime(cur);
    if (dur > 0) {
      progressBar.style.width = `${(cur / dur) * 100}%`;
    }
    // Throttled save for crash recovery (battery dead, app killed, etc.)
    const now = Date.now();
    if (!audio.paused && now - lastSavedAt > POSITION_SAVE_THROTTLE_MS) {
      savePosition();
      lastSavedAt = now;
    }
  });
```

(e) Extend the existing `visibilitychange` listener to save when the app is backgrounded:

Replace:
```javascript
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && wakeLock === null && !audio.paused) {
      acquireWakeLock();
    }
  });
```

With:
```javascript
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      savePosition();
    }
    if (document.visibilityState === "visible" && wakeLock === null && !audio.paused) {
      acquireWakeLock();
    }
  });
```

- [ ] **Step 5: Manual verification — save and restore on desktop**

Open the app locally (e.g. serve `pwa/` with `python -m http.server 8000` or use the deployed URL in a test environment). Steps:

1. Open DevTools → Application → Local Storage. Clear any `stiritata:position:*` keys.
2. Play the bulletin until around 2:30, then click pause.
3. Check DevTools: there should now be a `stiritata:position:<today-date>` key with a value around `150` (seconds).
4. Reload the page.
5. Verify: the audio is positioned at ~2:30 (time display shows `2:30`), and a small hint „Continuă de la 2:30" appears briefly near the top, then fades out after ~5 seconds.
6. Press play — audio continues from 2:30.

- [ ] **Step 6: Manual verification — ended clears the key**

1. Seek near the end of the audio (within last ~30s).
2. Let it play through to the end.
3. Check DevTools: the `stiritata:position:*` key should be GONE after the `ended` event fires.

- [ ] **Step 7: Manual verification — cleanup of old keys on date change**

1. In DevTools Local Storage, manually add a key `stiritata:position:2025-01-01` with value `500`.
2. Reload the page.
3. Check DevTools: the `2025-01-01` key should be gone (cleanup ran at manifest load).

- [ ] **Step 8: Manual verification — below-threshold does not trigger restore**

1. Clear all `stiritata:position:*` keys in DevTools.
2. Manually set `stiritata:position:<today-date>` = `5` (below the 10s threshold).
3. Reload.
4. Verify: audio starts at 0:00, no hint shown.

- [ ] **Step 9: Commit**

```bash
git add pwa/index.html pwa/style.css pwa/app.js
git commit -m "feat(pwa): resume pause position with localStorage and fading 'Continuă de la M:SS' hint"
```

---

## Deployment

- [ ] **Final step: Push to main and let GitHub Actions build tomorrow's bulletin**

```bash
git push origin main
```

The next scheduled run (03:00 UTC = 06:00 local) will produce the first bulletin with the history section. The PWA position feature is live immediately for anyone who loads the page after the deploy.

Monitor the first post-deploy run via GitHub Actions logs to confirm `history: using RO only (N total)` or a merge log line appears.

---

## Self-Review Notes

Scanned the plan against the spec — all items covered:

- ✅ `HistoryItem` / `HistoryCandidates` dataclasses (Task 1)
- ✅ `fetch_history.py` with RO primary / EN fallback / merge (Task 2)
- ✅ User-Agent header per Wikipedia policy (Task 2, step 6)
- ✅ Timeout 15s, retry 1x, None on permanent fail (Task 2, step 6)
- ✅ New `history` Section with `target_words=150, min_words=120` (Task 3)
- ✅ Intro phrase "Înainte de a încheia, câteva momente din istoria zilei de astăzi." (Task 3)
- ✅ Guidance: "știați că" style, 2-3 facts, RO priority, years in words (Task 3)
- ✅ Short-circuit when `history is None` to save API cost (Task 4)
- ✅ `fetch_history` in parallel `asyncio.gather` with news+weather (Task 5)
- ✅ `localStorage` keyed by `manifest.date` (Task 7)
- ✅ Save on pause / throttled timeupdate / visibilitychange hidden (Task 7, step 4)
- ✅ Clear on ended (Task 7, step 4)
- ✅ Restore gated on `loadedmetadata` and `POSITION_MIN_SECONDS` threshold (Task 7, step 3)
- ✅ Cleanup of old keys on every manifest load (Task 7, step 3-4)
- ✅ Hint "Continuă de la M:SS" with CSS fade-out (Task 7, steps 2-3)
- ✅ No autoplay — requires user tap (existing platform behavior; nothing to do)
- ✅ try/catch around all localStorage ops (Task 7, step 3: `safeGet`/`safeSet`/`safeRemove`)

Type consistency: `HistoryCandidates.events/births/deaths: List[HistoryItem]` used consistently in models, fetch_history, prompt, summarize. `history: Optional[HistoryCandidates]` kwarg signature consistent across `build_section_user_prompt`, `_call_section`, `summarize`. Function name `fetch_history` consistent between module, imports, and test patches.

No placeholders — every code block is complete and executable.
