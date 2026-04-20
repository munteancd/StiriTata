# Știri Tată — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily-refreshed Romanian news audio app for an elderly user, delivered as a PWA on Android phone/tablet, with the audio bulletin generated automatically by a GitHub Actions cron workflow using RSS + ChatGPT + Piper TTS.

**Architecture:** Two decoupled components. (1) A Python generator runs daily at 06:00 RO time on GitHub Actions: fetches news from RSS feeds and weather from OpenWeatherMap, summarizes everything through ChatGPT `gpt-4o-mini` into a 10-15 min Romanian script, and produces an MP3 via Piper TTS (local, free). (2) A vanilla-JS PWA hosted on GitHub Pages checks a `latest.json` manifest, caches the MP3 via a service worker, and plays it on a huge Play/Pause button.

**Tech Stack:**
- **Generator:** Python 3.11, `feedparser`, `httpx`, `openai` SDK, `piper-tts`, `pyyaml`, `pytest` + `pytest-asyncio` + `respx` for testing
- **Automation:** GitHub Actions (cron), GitHub Pages (deployed via `actions/deploy-pages`)
- **PWA:** Vanilla HTML + CSS + JavaScript, Service Worker, Web App Manifest, Media Session API, Wake Lock API

**Reference spec:** [`docs/superpowers/specs/2026-04-19-stiritata-design.md`](../specs/2026-04-19-stiritata-design.md)

---

## Project Layout

```
stiritata/
├── .github/workflows/daily.yml       # cron workflow
├── generator/
│   ├── __init__.py
│   ├── models.py                     # dataclasses: NewsItem, WeatherReport, Bulletin
│   ├── text_utils.py                 # Romanian date formatting, number normalization
│   ├── fetch_news.py                 # async RSS + dedup + 24h filter
│   ├── fetch_weather.py              # OpenWeatherMap client
│   ├── summarize.py                  # OpenAI ChatGPT integration
│   ├── tts.py                        # Piper TTS wrapper
│   ├── build_manifest.py             # latest.json generator
│   └── main.py                       # orchestrator, CLI entry point
├── pwa/
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   ├── sw.js                         # service worker
│   ├── manifest.webmanifest
│   └── icons/                        # 192x192, 512x512 PNG
├── tests/
│   ├── fixtures/
│   │   ├── sample_feed.xml
│   │   ├── weather_response.json
│   │   └── summarized_bulletin.txt
│   ├── test_models.py
│   ├── test_text_utils.py
│   ├── test_fetch_news.py
│   ├── test_fetch_weather.py
│   ├── test_summarize.py
│   ├── test_tts.py
│   ├── test_build_manifest.py
│   └── test_main.py
├── sources.yaml                      # editable RSS list
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── .gitignore
├── .env.example
└── README.md
```

**File responsibility summary:**
- `models.py`: Plain data shapes shared across modules. No I/O.
- `text_utils.py`: Pure functions for Romanian text — date formatting ("19 aprilie", "sâmbătă"), number-to-word normalization for years, pluralization.
- `fetch_news.py`: Reads `sources.yaml`, pulls RSS feeds in parallel, filters last 24h, deduplicates by normalized title.
- `fetch_weather.py`: Single HTTP call to OpenWeatherMap, returns parsed `WeatherReport`.
- `summarize.py`: Builds the ChatGPT prompt from news + weather, makes the API call, returns bulletin text.
- `tts.py`: Wraps Piper CLI, converts text → MP3, returns duration in seconds.
- `build_manifest.py`: Produces `latest.json` given a date, duration, and section list.
- `main.py`: Orchestrates fetch → summarize → TTS → manifest. Handles errors per §4.5 of spec.
- `pwa/*`: Static client. `app.js` owns audio + manifest check; `sw.js` owns cache.

---

## Task Overview

Tasks are ordered so each leaves the project in a working, committable state. Tests-first for generator modules where feasible; PWA uses manual verification checklists.

1. Project scaffolding (git, dependencies, structure, sources.yaml)
2. Data models
3. Romanian text utilities
4. News fetcher
5. Weather fetcher
6. Summarizer (ChatGPT)
7. TTS wrapper (Piper)
8. Manifest builder
9. Pipeline orchestrator (`main.py`)
10. GitHub Actions workflow
11. PWA static shell (HTML + icons + webmanifest)
12. PWA styling (huge Play button UI)
13. PWA audio logic (app.js)
14. Service worker (offline caching)
15. First end-to-end verification + user deploy actions

---

### Task 1: Project scaffolding

**Files:**
- Create: `.gitignore`, `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `.env.example`, `README.md`, `sources.yaml`
- Create empty package dirs: `generator/__init__.py`, `tests/__init__.py`, `tests/fixtures/`

- [ ] **Step 1: Initialize git repo**

```bash
cd "D:/Proiecte personale/Claude/StiriTata"
git init
git branch -M main
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.venv/
venv/

# Environment
.env
GPT.txt

# Build artifacts / audio
public/latest.mp3
public/latest.json
public/archive/
*.mp3
!tests/fixtures/*.mp3

# Piper voice models (downloaded at runtime)
generator/voices/

# IDE
.vscode/
.idea/
*.swp
.DS_Store
```

- [ ] **Step 3: Create `requirements.txt`**

```
feedparser==6.0.11
httpx==0.27.2
openai==1.54.0
PyYAML==6.0.2
python-dotenv==1.0.1
piper-tts==1.2.0
```

- [ ] **Step 4: Create `requirements-dev.txt`**

```
-r requirements.txt
pytest==8.3.3
pytest-asyncio==0.24.0
respx==0.21.1
```

- [ ] **Step 5: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

- [ ] **Step 6: Create `.env.example`**

```
OPENAI_API_KEY=sk-...
OPENWEATHER_API_KEY=...
```

- [ ] **Step 7: Create `sources.yaml`**

```yaml
# RSS feed sources, grouped by bulletin section.
# Comment out or remove entries if a feed dies; edit URLs as needed.

local_politics:
  - name: Caon
    url: https://caon.ro/feed/
  - name: Banatul Montan
    url: https://banatulmontan.ro/feed/
  # Caraș-Severin Expres: URL de confirmat manual la primul run

national_politics:
  - name: Digi24
    url: https://www.digi24.ro/rss
  - name: HotNews
    url: https://www.hotnews.ro/rss
  - name: G4Media
    url: https://www.g4media.ro/feed
  - name: Adevărul
    url: https://adevarul.ro/rss/

international_politics:
  - name: BBC World
    url: https://feeds.bbci.co.uk/news/world/rss.xml
  - name: Reuters World
    url: https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best

football_ro:
  - name: GSP
    url: https://www.gsp.ro/rss
  - name: ProSport
    url: https://www.prosport.ro/rss
  - name: Digi Sport
    url: https://www.digisport.ro/rss

football_eu:
  - name: BBC Sport Football
    url: https://feeds.bbci.co.uk/sport/football/rss.xml
  - name: UEFA News
    url: https://www.uefa.com/rssfeed/news/rss.xml

weather:
  city: Reșița
  country: RO
  lat: 45.3
  lon: 21.8833
```

- [ ] **Step 8: Create minimal `README.md`**

```markdown
# Știri Tată

Aplicație zilnică de buletin de știri vocal în română.

- **Spec:** `docs/superpowers/specs/2026-04-19-stiritata-design.md`
- **Plan:** `docs/superpowers/plans/2026-04-19-stiritata-implementation.md`

## Dev setup

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements-dev.txt
cp .env.example .env  # completează cheile
pytest
```

## Rulare manuală locală

```bash
python -m generator.main
```

Output: `public/latest.mp3` + `public/latest.json`.
```

- [ ] **Step 9: Create package markers + fixture dir**

```bash
mkdir -p generator pwa tests/fixtures public
touch generator/__init__.py tests/__init__.py
```

- [ ] **Step 10: Verify Python env works**

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pytest --collect-only
```
Expected: `collected 0 items` (no tests yet) with no import errors.

- [ ] **Step 11: Commit**

```bash
git add .gitignore requirements.txt requirements-dev.txt pytest.ini .env.example sources.yaml README.md generator/__init__.py tests/__init__.py tests/fixtures/.gitkeep
git commit -m "chore: project scaffolding and dependencies"
```

---

### Task 2: Data models

**Files:**
- Create: `generator/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_models.py`:

```python
from datetime import datetime, timezone
from generator.models import NewsItem, WeatherReport, BulletinSection, Bulletin


def test_news_item_carries_required_fields():
    item = NewsItem(
        title="Guvernul adoptă măsuri noi",
        summary="Rezumat scurt al știrii.",
        url="https://example.ro/art-1",
        source="Digi24",
        category="national_politics",
        published=datetime(2026, 4, 19, 8, 0, tzinfo=timezone.utc),
    )
    assert item.title == "Guvernul adoptă măsuri noi"
    assert item.category == "national_politics"


def test_weather_report_has_current_and_forecast_fields():
    wr = WeatherReport(
        city="Reșița",
        temp_current_c=12.0,
        temp_min_c=8.0,
        temp_max_c=18.0,
        description="cer senin",
        wind_kmh=10.0,
        precipitation_mm=0.0,
    )
    assert wr.city == "Reșița"
    assert wr.temp_max_c == 18.0


def test_bulletin_aggregates_sections_and_metadata():
    section = BulletinSection(title="Meteo", text="Astăzi va fi senin.", start_seconds=15)
    bulletin = Bulletin(
        date=datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc),
        sections=[section],
        full_text="Bună dimineața. Astăzi va fi senin.",
    )
    assert len(bulletin.sections) == 1
    assert bulletin.sections[0].start_seconds == 15
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py -v
```
Expected: ImportError — `generator.models` doesn't exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `generator/models.py`:

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class NewsItem:
    title: str
    summary: str
    url: str
    source: str
    category: str
    published: datetime


@dataclass
class WeatherReport:
    city: str
    temp_current_c: float
    temp_min_c: float
    temp_max_c: float
    description: str
    wind_kmh: float
    precipitation_mm: float


@dataclass
class BulletinSection:
    title: str
    text: str
    start_seconds: int


@dataclass
class Bulletin:
    date: datetime
    sections: List[BulletinSection]
    full_text: str
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_models.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add generator/models.py tests/test_models.py
git commit -m "feat(generator): add data models for news, weather, bulletin"
```

---

### Task 3: Romanian text utilities

**Files:**
- Create: `generator/text_utils.py`
- Test: `tests/test_text_utils.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_text_utils.py`:

```python
from datetime import datetime

from generator.text_utils import (
    format_date_ro,
    year_to_words_ro,
    normalize_title_for_dedup,
)


def test_format_date_ro_weekend():
    # 2026-04-19 is a Sunday
    assert format_date_ro(datetime(2026, 4, 19)) == "duminică, 19 aprilie"


def test_format_date_ro_weekday():
    # 2026-04-20 is a Monday
    assert format_date_ro(datetime(2026, 4, 20)) == "luni, 20 aprilie"


def test_year_to_words_ro_2026():
    assert year_to_words_ro(2026) == "două mii douăzeci și șase"


def test_year_to_words_ro_2000():
    assert year_to_words_ro(2000) == "două mii"


def test_year_to_words_ro_2010():
    assert year_to_words_ro(2010) == "două mii zece"


def test_normalize_title_strips_punctuation_and_lowercases():
    assert normalize_title_for_dedup("  Guvernul, adoptă Măsuri! ") == "guvernul adopta masuri"


def test_normalize_title_dedups_despite_diacritic_difference():
    a = normalize_title_for_dedup("Președintele Iohannis a declarat")
    b = normalize_title_for_dedup("Presedintele Iohannis a declarat")
    assert a == b
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_text_utils.py -v
```
Expected: ImportError on `generator.text_utils`.

- [ ] **Step 3: Write minimal implementation**

Create `generator/text_utils.py`:

```python
import re
import unicodedata
from datetime import datetime

WEEKDAYS_RO = [
    "luni", "marți", "miercuri", "joi", "vineri", "sâmbătă", "duminică",
]
MONTHS_RO = [
    "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie",
    "iulie", "august", "septembrie", "octombrie", "noiembrie", "decembrie",
]
UNITS_RO = [
    "", "unu", "doi", "trei", "patru", "cinci", "șase", "șapte", "opt", "nouă",
    "zece", "unsprezece", "doisprezece", "treisprezece", "paisprezece",
    "cincisprezece", "șaisprezece", "șaptesprezece", "optsprezece", "nouăsprezece",
]
TENS_RO = [
    "", "", "douăzeci", "treizeci", "patruzeci", "cincizeci",
    "șaizeci", "șaptezeci", "optzeci", "nouăzeci",
]


def format_date_ro(dt: datetime) -> str:
    return f"{WEEKDAYS_RO[dt.weekday()]}, {dt.day} {MONTHS_RO[dt.month - 1]}"


def _two_digits_to_words_ro(n: int) -> str:
    if n == 0:
        return ""
    if n < 20:
        return UNITS_RO[n]
    tens, unit = divmod(n, 10)
    if unit == 0:
        return TENS_RO[tens]
    return f"{TENS_RO[tens]} și {UNITS_RO[unit]}"


def year_to_words_ro(year: int) -> str:
    if year < 2000 or year >= 3000:
        raise ValueError(f"Only years 2000-2999 supported, got {year}")
    remainder = year - 2000
    if remainder == 0:
        return "două mii"
    rest = _two_digits_to_words_ro(remainder)
    return f"două mii {rest}"


def normalize_title_for_dedup(title: str) -> str:
    # Strip diacritics, lowercase, remove punctuation, collapse whitespace.
    nfkd = unicodedata.normalize("NFKD", title)
    no_diacritics = "".join(c for c in nfkd if not unicodedata.combining(c))
    lowered = no_diacritics.lower()
    no_punct = re.sub(r"[^\w\s]", " ", lowered)
    collapsed = re.sub(r"\s+", " ", no_punct).strip()
    return collapsed
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_text_utils.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add generator/text_utils.py tests/test_text_utils.py
git commit -m "feat(generator): add Romanian text utilities (dates, years, title dedup)"
```

---

### Task 4: News fetcher

**Files:**
- Create: `generator/fetch_news.py`, `tests/fixtures/sample_feed.xml`
- Test: `tests/test_fetch_news.py`

- [ ] **Step 1: Create RSS fixture**

Create `tests/fixtures/sample_feed.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Sample Feed</title>
    <link>https://example.ro</link>
    <description>Test feed</description>
    <item>
      <title>Guvernul adoptă măsuri noi</title>
      <link>https://example.ro/art-1</link>
      <description>Rezumat scurt al primei știri despre guvern și politici publice.</description>
      <pubDate>Sun, 19 Apr 2026 08:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Guvernul adoptă masuri noi</title>
      <link>https://example.ro/art-2-duplicate</link>
      <description>Duplicat al primei știri, doar fără diacritice.</description>
      <pubDate>Sun, 19 Apr 2026 09:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Știre veche care trebuie filtrată</title>
      <link>https://example.ro/art-old</link>
      <description>Asta e din urmă cu trei zile, nu ar trebui inclusă.</description>
      <pubDate>Thu, 16 Apr 2026 10:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_fetch_news.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_fetch_news.py -v
```
Expected: ImportError on `generator.fetch_news`.

- [ ] **Step 4: Write minimal implementation**

Create `generator/fetch_news.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_fetch_news.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add generator/fetch_news.py tests/test_fetch_news.py tests/fixtures/sample_feed.xml
git commit -m "feat(generator): async RSS fetching with 24h window and title dedup"
```

---

### Task 5: Weather fetcher

**Files:**
- Create: `generator/fetch_weather.py`, `tests/fixtures/weather_response.json`
- Test: `tests/test_fetch_weather.py`

- [ ] **Step 1: Create weather fixture**

Create `tests/fixtures/weather_response.json` (OpenWeatherMap "One Call 3.0" shape, trimmed):

```json
{
  "current": {
    "temp": 12.3,
    "wind_speed": 3.2,
    "weather": [{"description": "cer senin"}]
  },
  "daily": [
    {
      "temp": {"min": 7.8, "max": 18.4},
      "rain": 0.0
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_fetch_weather.py`:

```python
import json
from pathlib import Path

import httpx
import respx

from generator.fetch_weather import fetch_weather, parse_weather_response

FIXTURE = Path(__file__).parent / "fixtures" / "weather_response.json"


def test_parse_weather_response_extracts_fields():
    data = json.loads(FIXTURE.read_text())
    report = parse_weather_response(data, city="Reșița")
    assert report.city == "Reșița"
    assert report.temp_current_c == 12.3
    assert report.temp_min_c == 7.8
    assert report.temp_max_c == 18.4
    assert report.description == "cer senin"
    assert report.precipitation_mm == 0.0
    # 3.2 m/s ≈ 11.52 km/h
    assert 11.0 < report.wind_kmh < 12.0


@respx.mock
async def test_fetch_weather_calls_owm_and_returns_report():
    respx.get("https://api.openweathermap.org/data/3.0/onecall").mock(
        return_value=httpx.Response(200, content=FIXTURE.read_bytes())
    )
    report = await fetch_weather(
        api_key="dummy",
        lat=45.3,
        lon=21.8833,
        city="Reșița",
    )
    assert report.city == "Reșița"
    assert report.temp_max_c == 18.4


@respx.mock
async def test_fetch_weather_returns_none_on_failure():
    respx.get("https://api.openweathermap.org/data/3.0/onecall").mock(
        return_value=httpx.Response(500)
    )
    report = await fetch_weather(
        api_key="dummy",
        lat=45.3,
        lon=21.8833,
        city="Reșița",
    )
    assert report is None
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_fetch_weather.py -v
```
Expected: ImportError on `generator.fetch_weather`.

- [ ] **Step 4: Write minimal implementation**

Create `generator/fetch_weather.py`:

```python
import logging
from typing import Any, Dict, Optional

import httpx

from .models import WeatherReport

log = logging.getLogger(__name__)

OWM_URL = "https://api.openweathermap.org/data/3.0/onecall"


def parse_weather_response(data: Dict[str, Any], *, city: str) -> WeatherReport:
    current = data["current"]
    daily_today = data["daily"][0]
    wind_ms = float(current.get("wind_speed", 0.0))
    precipitation_mm = float(daily_today.get("rain", 0.0) or 0.0)
    return WeatherReport(
        city=city,
        temp_current_c=float(current["temp"]),
        temp_min_c=float(daily_today["temp"]["min"]),
        temp_max_c=float(daily_today["temp"]["max"]),
        description=current["weather"][0]["description"],
        wind_kmh=wind_ms * 3.6,
        precipitation_mm=precipitation_mm,
    )


async def fetch_weather(
    *,
    api_key: str,
    lat: float,
    lon: float,
    city: str,
) -> Optional[WeatherReport]:
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric",
        "lang": "ro",
        "exclude": "minutely,hourly,alerts",
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(OWM_URL, params=params, timeout=15.0)
            resp.raise_for_status()
            return parse_weather_response(resp.json(), city=city)
    except Exception as exc:
        log.warning("weather fetch failed: %s", exc)
        return None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_fetch_weather.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add generator/fetch_weather.py tests/fixtures/weather_response.json tests/test_fetch_weather.py
git commit -m "feat(generator): OpenWeatherMap integration with graceful failure"
```

---

### Task 6: Summarizer (ChatGPT)

**Files:**
- Create: `generator/summarize.py`, `generator/prompt.py`
- Test: `tests/test_summarize.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_summarize.py`:

```python
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from generator.models import NewsItem, WeatherReport
from generator.prompt import build_user_prompt, SYSTEM_PROMPT
from generator.summarize import summarize


def _sample_items() -> list[NewsItem]:
    return [
        NewsItem(
            title="Guvernul adoptă măsuri noi",
            summary="Rezumat.",
            url="https://a.ro/1",
            source="Digi24",
            category="national_politics",
            published=datetime(2026, 4, 19, 8, 0, tzinfo=timezone.utc),
        ),
        NewsItem(
            title="Rapid câștigă cu 2-1",
            summary="Derby bucureștean.",
            url="https://a.ro/2",
            source="GSP",
            category="football_ro",
            published=datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc),
        ),
    ]


def _sample_weather() -> WeatherReport:
    return WeatherReport(
        city="Reșița",
        temp_current_c=12.0,
        temp_min_c=8.0,
        temp_max_c=18.0,
        description="cer senin",
        wind_kmh=10.0,
        precipitation_mm=0.0,
    )


def test_system_prompt_enforces_antihallucination_and_romanian():
    assert "română" in SYSTEM_PROMPT.lower()
    # Must instruct NOT to invent information
    assert "nu inventa" in SYSTEM_PROMPT.lower() or "doar" in SYSTEM_PROMPT.lower()


def test_user_prompt_groups_items_by_category_and_includes_weather():
    prompt = build_user_prompt(
        items=_sample_items(),
        weather=_sample_weather(),
        bulletin_date=datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc),
    )
    assert "POLITICĂ NAȚIONALĂ" in prompt
    assert "FOTBAL ROMÂNIA" in prompt
    assert "Guvernul adoptă măsuri noi" in prompt
    assert "Rapid câștigă cu 2-1" in prompt
    assert "Reșița" in prompt
    assert "duminică, 19 aprilie" in prompt  # Romanian date formatted


def test_user_prompt_marks_missing_weather_explicitly():
    prompt = build_user_prompt(
        items=_sample_items(),
        weather=None,
        bulletin_date=datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc),
    )
    assert "METEO INDISPONIBIL" in prompt or "meteo indisponibil" in prompt.lower()


def test_summarize_calls_openai_and_returns_text():
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Bună dimineața. (buletin)"))]
    )

    text = summarize(
        items=_sample_items(),
        weather=_sample_weather(),
        bulletin_date=datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc),
        client=fake_client,
        model="gpt-4o-mini",
    )

    assert text == "Bună dimineața. (buletin)"
    call_kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4o-mini"
    assert len(call_kwargs["messages"]) == 2
    assert call_kwargs["messages"][0]["role"] == "system"
    assert call_kwargs["messages"][1]["role"] == "user"


def test_summarize_retries_then_raises():
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        summarize(
            items=_sample_items(),
            weather=_sample_weather(),
            bulletin_date=datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc),
            client=fake_client,
            model="gpt-4o-mini",
            max_retries=2,
            retry_sleep=0.0,
        )
    # Called 3 times total (1 initial + 2 retries)
    assert fake_client.chat.completions.create.call_count == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_summarize.py -v
```
Expected: ImportError on `generator.prompt` and `generator.summarize`.

- [ ] **Step 3: Write prompt module**

Create `generator/prompt.py`:

```python
from datetime import datetime
from typing import List, Optional

from .models import NewsItem, WeatherReport
from .text_utils import format_date_ro

SYSTEM_PROMPT = """\
Ești un redactor de știri radio în limba română. Rolul tău este să scrii textul complet \
al unui buletin de dimineață de 10-15 minute, gata de citit cu voce tare.

REGULI STRICTE:
1. Folosește EXCLUSIV informațiile din textele de input primite de la utilizator. \
   Nu inventa știri, nume, cifre sau detalii care nu apar explicit în input.
2. Dacă o secțiune nu are știri în input, spune scurt: \
   „Astăzi nu sunt știri importante din [subiect]." și treci mai departe.
3. Ton neutru, calm, profesionist — ca un prezentator de radio matinal.
4. Propoziții scurte și clare, ușor de urmărit la ascultare.
5. Fără anglicisme dacă există echivalent românesc (scrie „antrenor", nu „coach").
6. Scrie anii în cuvinte pentru TTS natural: 2026 → „două mii douăzeci și șase".
7. Scrie numerele mici în cuvinte ("trei goluri"), dar scorurile le păstrezi cu cifre \
   („a câștigat cu 2-1").
8. Lungime țintă: între 2200 și 2500 de cuvinte (aproximativ 10-15 minute citite).

STRUCTURA BULETINULUI (ordinea obligatorie):
1. Intro: "Bună dimineața, tată. Astăzi este [ziua], [data]. Iată buletinul de știri."
2. Meteo Reșița (~30 sec) — temperatură curentă, min/max ziua, precipitații, vânt.
3. Politică locală Caraș-Severin / Reșița (~1.5-2 min).
4. Politică națională România (~2-3 min).
5. Politică internațională (~1.5-2 min).
6. Fotbal România — SuperLiga, naționala (~2 min).
7. Fotbal — Big 5 (Premier League, La Liga, Bundesliga, Serie A, Ligue 1) (~2-3 min).
8. Fotbal — cupe europene (Champions League, Europa League, Conference League) (~1-2 min).
9. Fotbal — turnee internaționale (World Cup / EURO) — DOAR dacă apar în input, altfel omite.
10. Outro: "Acesta a fost buletinul de astăzi. O zi bună!"

Output: strict textul buletinului, fără titluri de secțiuni scrise, fără paranteze \
explicative, fără markdown. Doar textul curat, ca și cum ar fi citit la microfon.
"""

CATEGORY_HEADERS = {
    "local_politics": "POLITICĂ LOCALĂ (REȘIȚA / CARAȘ-SEVERIN)",
    "national_politics": "POLITICĂ NAȚIONALĂ",
    "international_politics": "POLITICĂ INTERNAȚIONALĂ",
    "football_ro": "FOTBAL ROMÂNIA",
    "football_eu": "FOTBAL EUROPEAN (BIG 5 + CUPE)",
}

CATEGORY_ORDER = [
    "local_politics",
    "national_politics",
    "international_politics",
    "football_ro",
    "football_eu",
]


def _format_weather_block(weather: Optional[WeatherReport]) -> str:
    if weather is None:
        return "METEO INDISPONIBIL: menționează scurt că datele meteo nu au putut fi obținute astăzi."
    return (
        f"METEO {weather.city.upper()}\n"
        f"- Temperatură curentă: {weather.temp_current_c:.1f}°C\n"
        f"- Minimă ziua: {weather.temp_min_c:.1f}°C\n"
        f"- Maximă ziua: {weather.temp_max_c:.1f}°C\n"
        f"- Cer: {weather.description}\n"
        f"- Vânt: {weather.wind_kmh:.0f} km/h\n"
        f"- Precipitații: {weather.precipitation_mm:.1f} mm"
    )


def _format_items_block(items: List[NewsItem]) -> str:
    if not items:
        return "(fără știri în această categorie astăzi)"
    lines = []
    for idx, it in enumerate(items, 1):
        lines.append(f"{idx}. [{it.source}] {it.title}")
        if it.summary:
            lines.append(f"   {it.summary}")
    return "\n".join(lines)


def build_user_prompt(
    *,
    items: List[NewsItem],
    weather: Optional[WeatherReport],
    bulletin_date: datetime,
) -> str:
    by_category: dict[str, list[NewsItem]] = {k: [] for k in CATEGORY_ORDER}
    for it in items:
        by_category.setdefault(it.category, []).append(it)

    parts = [
        f"DATA BULETINULUI: {format_date_ro(bulletin_date)}",
        "",
        _format_weather_block(weather),
        "",
    ]
    for cat in CATEGORY_ORDER:
        parts.append(CATEGORY_HEADERS[cat])
        parts.append(_format_items_block(by_category.get(cat, [])))
        parts.append("")
    parts.append(
        "Scrie acum textul complet al buletinului, respectând toate regulile din mesajul de sistem."
    )
    return "\n".join(parts)
```

- [ ] **Step 4: Write summarize module**

Create `generator/summarize.py`:

```python
import logging
import time
from datetime import datetime
from typing import Any, List, Optional

from .models import NewsItem, WeatherReport
from .prompt import SYSTEM_PROMPT, build_user_prompt

log = logging.getLogger(__name__)


def summarize(
    *,
    items: List[NewsItem],
    weather: Optional[WeatherReport],
    bulletin_date: datetime,
    client: Any,
    model: str = "gpt-4o-mini",
    max_retries: int = 2,
    retry_sleep: float = 2.0,
) -> str:
    user_prompt = build_user_prompt(
        items=items, weather=weather, bulletin_date=bulletin_date
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.4,
            )
            text = response.choices[0].message.content.strip()
            return text
        except Exception as exc:
            last_exc = exc
            log.warning("summarize attempt %d failed: %s", attempt + 1, exc)
            if attempt < max_retries:
                time.sleep(retry_sleep * (2**attempt))
    assert last_exc is not None
    raise last_exc
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_summarize.py -v
```
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add generator/prompt.py generator/summarize.py tests/test_summarize.py
git commit -m "feat(generator): ChatGPT summarizer with structured Romanian prompt and retries"
```

---

### Task 7: TTS wrapper (Piper)

**Files:**
- Create: `generator/tts.py`
- Test: `tests/test_tts.py`

**Note:** Piper is a CLI invoked as a subprocess. Tests mock subprocess and verify arg construction; a real MP3 is produced during integration (Task 15).

- [ ] **Step 1: Write the failing test**

Create `tests/test_tts.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from generator.tts import synthesize, PiperConfig


def test_piper_config_default_voice_is_romanian():
    cfg = PiperConfig()
    assert cfg.voice_id.startswith("ro_RO-")


def test_synthesize_invokes_piper_and_ffmpeg(tmp_path: Path):
    text = "Bună dimineața, tată. Astăzi este duminică."
    out_mp3 = tmp_path / "latest.mp3"
    voice_dir = tmp_path / "voices"
    voice_dir.mkdir()
    # Create dummy voice files so existence check passes
    (voice_dir / "ro_RO-mihai-medium.onnx").write_bytes(b"fake")
    (voice_dir / "ro_RO-mihai-medium.onnx.json").write_bytes(b"{}")

    cfg = PiperConfig(voice_id="ro_RO-mihai-medium", voice_dir=voice_dir)

    # Simulate Piper writing a WAV, then ffmpeg producing an MP3.
    def fake_run(cmd, **kwargs):
        if "piper" in cmd[0].lower() or cmd[0].endswith("piper"):
            # Piper is told to write to `--output-raw` or `--output_file`; use output_file path
            # from the command to create a fake WAV.
            wav_path = Path(cmd[cmd.index("--output_file") + 1])
            wav_path.write_bytes(b"RIFF....WAVEfakeaudio")
        elif "ffmpeg" in cmd[0]:
            out_index = cmd.index("-y") + 1 if "-y" in cmd else -1
            # Output is last arg
            Path(cmd[-1]).write_bytes(b"ID3fakemp3")
        return MagicMock(returncode=0, stdout=b"", stderr=b"")

    with patch("generator.tts.subprocess.run", side_effect=fake_run) as run_mock, \
         patch("generator.tts._ffprobe_duration_seconds", return_value=42.5):
        duration = synthesize(text=text, out_mp3=out_mp3, config=cfg)

    assert out_mp3.exists()
    assert duration == 42.5
    # Piper must have been invoked with the voice model path.
    piper_call = run_mock.call_args_list[0]
    piper_cmd = piper_call.args[0]
    assert any("ro_RO-mihai-medium.onnx" in part for part in piper_cmd)


def test_synthesize_raises_if_voice_model_missing(tmp_path: Path):
    cfg = PiperConfig(voice_id="ro_RO-missing-medium", voice_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        synthesize(text="test", out_mp3=tmp_path / "out.mp3", config=cfg)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_tts.py -v
```
Expected: ImportError on `generator.tts`.

- [ ] **Step 3: Write minimal implementation**

Create `generator/tts.py`:

```python
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class PiperConfig:
    voice_id: str = "ro_RO-mihai-medium"
    voice_dir: Path = field(default_factory=lambda: Path("generator/voices"))
    piper_binary: str = "piper"
    ffmpeg_binary: str = "ffmpeg"


def _ffprobe_duration_seconds(mp3_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(mp3_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def synthesize(*, text: str, out_mp3: Path, config: PiperConfig) -> float:
    model_path = config.voice_dir / f"{config.voice_id}.onnx"
    model_json = config.voice_dir / f"{config.voice_id}.onnx.json"
    if not model_path.exists() or not model_json.exists():
        raise FileNotFoundError(
            f"Piper voice model not found at {model_path}. "
            "Run scripts/download_voice.sh or pass voice_dir."
        )

    out_mp3.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = Path(tmpdir) / "out.wav"

        piper_cmd = [
            config.piper_binary,
            "--model", str(model_path),
            "--output_file", str(wav_path),
        ]
        log.info("running piper: %s", piper_cmd)
        piper = subprocess.run(
            piper_cmd,
            input=text.encode("utf-8"),
            capture_output=True,
            check=False,
        )
        if piper.returncode != 0:
            raise RuntimeError(
                f"piper failed (rc={piper.returncode}): {piper.stderr.decode(errors='replace')}"
            )

        ffmpeg_cmd = [
            config.ffmpeg_binary,
            "-y",
            "-i", str(wav_path),
            "-codec:a", "libmp3lame",
            "-b:a", "96k",
            str(out_mp3),
        ]
        log.info("running ffmpeg: %s", ffmpeg_cmd)
        ff = subprocess.run(ffmpeg_cmd, capture_output=True, check=False)
        if ff.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed (rc={ff.returncode}): {ff.stderr.decode(errors='replace')}"
            )

    return _ffprobe_duration_seconds(out_mp3)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_tts.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Create voice download helper script**

Create `scripts/download_voice.sh`:

```bash
#!/usr/bin/env bash
# Downloads Piper Romanian voice models used by the generator.
# Run once locally, and in the GitHub Actions workflow (cached).
set -euo pipefail

VOICE_DIR="${VOICE_DIR:-generator/voices}"
mkdir -p "$VOICE_DIR"

VOICE="ro_RO-mihai-medium"
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/ro/ro_RO/mihai/medium"

curl -L -o "$VOICE_DIR/${VOICE}.onnx"       "${BASE}/${VOICE}.onnx"
curl -L -o "$VOICE_DIR/${VOICE}.onnx.json"  "${BASE}/${VOICE}.onnx.json"

echo "Downloaded $VOICE to $VOICE_DIR"
```

Make executable and gitignore the voices dir (already handled in `.gitignore` from Task 1).

```bash
chmod +x scripts/download_voice.sh
```

- [ ] **Step 6: Commit**

```bash
git add generator/tts.py tests/test_tts.py scripts/download_voice.sh
git commit -m "feat(generator): Piper TTS wrapper with WAV→MP3 and voice download script"
```

---

### Task 8: Manifest builder

**Files:**
- Create: `generator/build_manifest.py`
- Test: `tests/test_build_manifest.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_build_manifest.py`:

```python
import json
from datetime import datetime, timezone

from generator.build_manifest import build_manifest


def test_manifest_contains_required_fields():
    date = datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc)
    manifest = build_manifest(
        date=date,
        duration_seconds=823.4,
        audio_url="latest.mp3",
        generated_at=datetime(2026, 4, 19, 6, 3, tzinfo=timezone.utc),
    )
    assert manifest["date"] == "2026-04-19"
    assert manifest["duration_seconds"] == 823.4
    assert manifest["audio_url"] == "latest.mp3"
    assert manifest["generated_at"] == "2026-04-19T06:03:00+00:00"


def test_manifest_is_json_serializable():
    date = datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc)
    manifest = build_manifest(
        date=date,
        duration_seconds=900.0,
        audio_url="latest.mp3",
        generated_at=datetime(2026, 4, 19, 6, 3, tzinfo=timezone.utc),
    )
    s = json.dumps(manifest)
    assert "2026-04-19" in s
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_build_manifest.py -v
```
Expected: ImportError.

- [ ] **Step 3: Write minimal implementation**

Create `generator/build_manifest.py`:

```python
from datetime import datetime
from typing import Any, Dict


def build_manifest(
    *,
    date: datetime,
    duration_seconds: float,
    audio_url: str,
    generated_at: datetime,
) -> Dict[str, Any]:
    return {
        "date": date.strftime("%Y-%m-%d"),
        "duration_seconds": duration_seconds,
        "audio_url": audio_url,
        "generated_at": generated_at.isoformat(),
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_build_manifest.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add generator/build_manifest.py tests/test_build_manifest.py
git commit -m "feat(generator): add latest.json manifest builder"
```

---

### Task 9: Pipeline orchestrator

**Files:**
- Create: `generator/main.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_main.py`:

```python
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from generator.models import NewsItem, WeatherReport
from generator.main import run_pipeline


def _one_item() -> list[NewsItem]:
    return [
        NewsItem(
            title="Știre de test",
            summary="S.",
            url="u",
            source="X",
            category="national_politics",
            published=datetime(2026, 4, 19, 8, 0, tzinfo=timezone.utc),
        )
    ]


def _wr() -> WeatherReport:
    return WeatherReport(
        city="Reșița",
        temp_current_c=10, temp_min_c=5, temp_max_c=15,
        description="nor", wind_kmh=5, precipitation_mm=0,
    )


async def test_pipeline_writes_mp3_and_manifest(tmp_path: Path):
    public = tmp_path / "public"
    archive = public / "archive"

    sources_cfg = {
        "national_politics": [{"name": "X", "url": "https://x.example/feed"}],
        "weather": {"city": "Reșița", "country": "RO", "lat": 45.3, "lon": 21.88},
    }

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Buletin simulat."))]
    )

    with patch("generator.main.fetch_all_sources", AsyncMock(return_value=_one_item())), \
         patch("generator.main.fetch_weather", AsyncMock(return_value=_wr())), \
         patch("generator.main.synthesize", return_value=600.0) as tts_mock:
        # Make synthesize actually create the MP3 file so later steps find it.
        def _mk_mp3(*, text, out_mp3, config):
            out_mp3.parent.mkdir(parents=True, exist_ok=True)
            out_mp3.write_bytes(b"ID3fakemp3")
            return 600.0
        tts_mock.side_effect = _mk_mp3

        await run_pipeline(
            sources_cfg=sources_cfg,
            public_dir=public,
            archive_dir=archive,
            openai_client=fake_openai,
            openweather_api_key="k",
            now=datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc),
        )

    assert (public / "latest.mp3").exists()
    assert (public / "latest.json").exists()
    manifest = json.loads((public / "latest.json").read_text())
    assert manifest["date"] == "2026-04-19"
    assert manifest["duration_seconds"] == 600.0
    # Archive copy present
    assert (archive / "2026-04-19.mp3").exists()


async def test_pipeline_preserves_previous_mp3_on_summarize_failure(tmp_path: Path):
    public = tmp_path / "public"
    archive = public / "archive"
    public.mkdir(parents=True)
    # Simulate yesterday's MP3 already there
    (public / "latest.mp3").write_bytes(b"YESTERDAY")
    (public / "latest.json").write_text(json.dumps({
        "date": "2026-04-18",
        "duration_seconds": 500.0,
        "audio_url": "latest.mp3",
        "generated_at": "2026-04-18T06:03:00+00:00",
    }))

    sources_cfg = {
        "national_politics": [{"name": "X", "url": "https://x.example/feed"}],
        "weather": {"city": "Reșița", "country": "RO", "lat": 45.3, "lon": 21.88},
    }

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.side_effect = RuntimeError("api down")

    with patch("generator.main.fetch_all_sources", AsyncMock(return_value=_one_item())), \
         patch("generator.main.fetch_weather", AsyncMock(return_value=_wr())):
        # Pipeline must NOT raise — falls back to previous bulletin.
        await run_pipeline(
            sources_cfg=sources_cfg,
            public_dir=public,
            archive_dir=archive,
            openai_client=fake_openai,
            openweather_api_key="k",
            now=datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc),
        )

    # Yesterday's MP3 is still there
    assert (public / "latest.mp3").read_bytes() == b"YESTERDAY"


async def test_pipeline_trims_archive_to_last_7_days(tmp_path: Path):
    public = tmp_path / "public"
    archive = public / "archive"
    archive.mkdir(parents=True)
    # Seed 10 old archive files
    for d in range(1, 11):
        (archive / f"2026-04-{d:02d}.mp3").write_bytes(b"x")

    sources_cfg = {
        "national_politics": [{"name": "X", "url": "https://x.example/feed"}],
        "weather": {"city": "Reșița", "country": "RO", "lat": 45.3, "lon": 21.88},
    }

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Buletin."))]
    )

    def _mk_mp3(*, text, out_mp3, config):
        out_mp3.parent.mkdir(parents=True, exist_ok=True)
        out_mp3.write_bytes(b"ID3")
        return 600.0

    with patch("generator.main.fetch_all_sources", AsyncMock(return_value=_one_item())), \
         patch("generator.main.fetch_weather", AsyncMock(return_value=_wr())), \
         patch("generator.main.synthesize", side_effect=_mk_mp3):
        await run_pipeline(
            sources_cfg=sources_cfg,
            public_dir=public,
            archive_dir=archive,
            openai_client=fake_openai,
            openweather_api_key="k",
            now=datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc),
        )

    archived_files = sorted(archive.glob("*.mp3"))
    assert len(archived_files) <= 7
    assert (archive / "2026-04-19.mp3") in archived_files
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_main.py -v
```
Expected: ImportError.

- [ ] **Step 3: Write minimal implementation**

Create `generator/main.py`:

```python
import argparse
import asyncio
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

from .build_manifest import build_manifest
from .fetch_news import fetch_all_sources
from .fetch_weather import fetch_weather
from .summarize import summarize
from .tts import PiperConfig, synthesize

log = logging.getLogger(__name__)


async def run_pipeline(
    *,
    sources_cfg: Dict[str, Any],
    public_dir: Path,
    archive_dir: Path,
    openai_client: Any,
    openweather_api_key: str,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(tz=timezone.utc)
    public_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    rss_cfg = {k: v for k, v in sources_cfg.items() if k != "weather"}
    weather_cfg = sources_cfg.get("weather", {})

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

    # 2. Summarize via ChatGPT. On failure, keep yesterday's MP3.
    try:
        text = summarize(
            items=items,
            weather=weather,
            bulletin_date=now,
            client=openai_client,
        )
    except Exception as exc:
        log.error("summarize failed, keeping previous bulletin: %s", exc)
        return

    # 3. TTS → MP3
    out_mp3 = public_dir / "latest.mp3"
    duration = synthesize(text=text, out_mp3=out_mp3, config=PiperConfig())

    # 4. Archive a dated copy
    dated = archive_dir / f"{now.strftime('%Y-%m-%d')}.mp3"
    shutil.copy2(out_mp3, dated)

    # 5. Trim archive to last 7 by mtime
    archives = sorted(archive_dir.glob("*.mp3"), key=lambda p: p.name, reverse=True)
    for old in archives[7:]:
        try:
            old.unlink()
        except OSError as exc:
            log.warning("failed to unlink %s: %s", old, exc)

    # 6. Write manifest
    manifest = build_manifest(
        date=now,
        duration_seconds=duration,
        audio_url="latest.mp3",
        generated_at=datetime.now(tz=timezone.utc),
    )
    (public_dir / "latest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 7. Write the bulletin text too (useful for debugging)
    (public_dir / "latest.txt").write_text(text, encoding="utf-8")

    log.info("pipeline complete: %s (%.1fs)", out_mp3, duration)


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Generate daily Știri Tată bulletin")
    parser.add_argument("--sources", default="sources.yaml")
    parser.add_argument("--public-dir", default="public")
    args = parser.parse_args()

    sources_cfg = yaml.safe_load(Path(args.sources).read_text(encoding="utf-8"))
    public_dir = Path(args.public_dir)
    archive_dir = public_dir / "archive"

    openai_key = os.environ.get("OPENAI_API_KEY")
    openweather_key = os.environ.get("OPENWEATHER_API_KEY")
    if not openai_key:
        raise SystemExit("OPENAI_API_KEY is not set (check .env or GitHub Secrets)")
    if not openweather_key:
        raise SystemExit("OPENWEATHER_API_KEY is not set (check .env or GitHub Secrets)")

    from openai import OpenAI
    client = OpenAI(api_key=openai_key)

    asyncio.run(
        run_pipeline(
            sources_cfg=sources_cfg,
            public_dir=public_dir,
            archive_dir=archive_dir,
            openai_client=client,
            openweather_api_key=openweather_key,
        )
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_main.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Run the whole test suite**

```bash
pytest -v
```
Expected: all tests pass across the 8 test files (approximately 22 tests).

- [ ] **Step 6: Commit**

```bash
git add generator/main.py tests/test_main.py
git commit -m "feat(generator): pipeline orchestrator with fallback and archive rotation"
```

---

### Task 10: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/daily.yml`

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/daily.yml`:

```yaml
name: daily-bulletin

on:
  schedule:
    # 03:00 UTC == 06:00 Romania (EET) / 06:00 EEST.
    # During DST (EEST, UTC+3) this fires at 05:00 local; acceptable.
    - cron: "0 3 * * *"
  workflow_dispatch: {}

permissions:
  contents: write
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install system deps (ffmpeg)
        run: sudo apt-get update && sudo apt-get install -y ffmpeg

      - name: Install Python deps
        run: pip install -r requirements.txt

      - name: Cache Piper voice model
        id: cache-voice
        uses: actions/cache@v4
        with:
          path: generator/voices
          key: piper-voice-ro_RO-mihai-medium-v1

      - name: Download Piper voice (if not cached)
        if: steps.cache-voice.outputs.cache-hit != 'true'
        run: bash scripts/download_voice.sh

      - name: Fetch previous public/ from gh-pages (for fallback)
        run: |
          git fetch origin gh-pages || echo "no gh-pages yet"
          if git show-ref --verify --quiet refs/remotes/origin/gh-pages; then
            mkdir -p public
            git --work-tree=public checkout origin/gh-pages -- . || true
          fi

      - name: Run generator
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          OPENWEATHER_API_KEY: ${{ secrets.OPENWEATHER_API_KEY }}
        run: python -m generator.main --sources sources.yaml --public-dir public

      - name: Copy PWA static files into public/
        run: |
          cp -r pwa/* public/

      - name: Upload artifact for Pages
        uses: actions/upload-pages-artifact@v3
        with:
          path: public

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Lint YAML locally (optional but recommended)**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/daily.yml'))"
```
Expected: no output (valid YAML).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/daily.yml
git commit -m "ci: add daily GitHub Actions workflow deploying to Pages"
```

---

### Task 11: PWA static shell

**Files:**
- Create: `pwa/index.html`, `pwa/manifest.webmanifest`, `pwa/icons/icon-192.png`, `pwa/icons/icon-512.png`

- [ ] **Step 1: Create `pwa/index.html`**

```html
<!DOCTYPE html>
<html lang="ro">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <meta name="theme-color" content="#1a1a1a">
  <title>Știri Tată</title>
  <link rel="manifest" href="manifest.webmanifest">
  <link rel="icon" href="icons/icon-192.png" type="image/png">
  <link rel="apple-touch-icon" href="icons/icon-192.png">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <main class="app">
    <h1 class="app__title">Știri Tată</h1>
    <p class="app__date" id="bulletin-date">Se încarcă…</p>

    <button
      id="play-btn"
      class="play-btn"
      aria-label="Redare"
      type="button"
    >
      <span class="play-btn__icon" id="play-btn-icon" aria-hidden="true">▶</span>
    </button>

    <div class="progress" aria-hidden="true">
      <div class="progress__bar" id="progress-bar"></div>
    </div>

    <p class="time">
      <span id="time-current">0:00</span>
      <span class="time__sep">/</span>
      <span id="time-total">0:00</span>
    </p>

    <div class="seek-buttons">
      <button class="seek-btn" id="seek-back" type="button" aria-label="Înapoi 30 secunde">⏪ 30</button>
      <button class="seek-btn" id="seek-fwd" type="button" aria-label="Înainte 30 secunde">30 ⏩</button>
    </div>

    <p class="status" id="status" role="status" aria-live="polite"></p>
  </main>

  <audio id="audio" preload="auto"></audio>
  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `pwa/manifest.webmanifest`**

```json
{
  "name": "Știri Tată",
  "short_name": "Știri",
  "description": "Buletin zilnic de știri vocal în română",
  "start_url": ".",
  "scope": ".",
  "display": "standalone",
  "orientation": "portrait",
  "background_color": "#1a1a1a",
  "theme_color": "#1a1a1a",
  "lang": "ro",
  "icons": [
    {
      "src": "icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ]
}
```

- [ ] **Step 3: Generate icons**

Use Python + Pillow to render simple placeholder icons (a filled circle with "SȚ" text). Run once locally:

```bash
python -c "
from PIL import Image, ImageDraw, ImageFont
import os
os.makedirs('pwa/icons', exist_ok=True)
for size in (192, 512):
    img = Image.new('RGB', (size, size), (26, 26, 26))
    d = ImageDraw.Draw(img)
    r = int(size * 0.42)
    c = size // 2
    d.ellipse((c - r, c - r, c + r, c + r), fill=(235, 70, 55))
    try:
        font = ImageFont.truetype('arial.ttf', int(size * 0.36))
    except OSError:
        font = ImageFont.load_default()
    text = 'SȚ'
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]), text, fill='white', font=font)
    img.save(f'pwa/icons/icon-{size}.png')
print('done')
"
```
Expected: `pwa/icons/icon-192.png` and `pwa/icons/icon-512.png` created.

- [ ] **Step 4: Manual verification**

Open `pwa/index.html` in a browser (double-click or `start pwa/index.html`).
Expected: title "Știri Tată" visible, big Play button placeholder (unstyled — styling comes in Task 12).

- [ ] **Step 5: Commit**

```bash
git add pwa/index.html pwa/manifest.webmanifest pwa/icons/icon-192.png pwa/icons/icon-512.png
git commit -m "feat(pwa): add HTML shell, web manifest, and app icons"
```

---

### Task 12: PWA styling

**Files:**
- Create: `pwa/style.css`

- [ ] **Step 1: Write `pwa/style.css`**

```css
:root {
  --bg: #1a1a1a;
  --fg: #f7f7f7;
  --accent: #eb4637;
  --muted: #8a8a8a;
  --progress-bg: #333;
}

* {
  box-sizing: border-box;
}

html, body {
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--fg);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  -webkit-user-select: none;
  user-select: none;
  overscroll-behavior: none;
  height: 100%;
}

body {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: env(safe-area-inset-top, 0) env(safe-area-inset-right, 0) env(safe-area-inset-bottom, 0) env(safe-area-inset-left, 0);
}

.app {
  width: 100%;
  max-width: 520px;
  padding: 24px 16px 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 24px;
}

.app__title {
  font-size: clamp(2rem, 6vw, 2.8rem);
  font-weight: 700;
  margin: 0;
  letter-spacing: 0.5px;
}

.app__date {
  font-size: clamp(1.1rem, 4vw, 1.4rem);
  color: var(--muted);
  margin: 0;
}

.play-btn {
  width: 60vw;
  max-width: 280px;
  height: 60vw;
  max-height: 280px;
  min-width: 180px;
  min-height: 180px;
  border-radius: 50%;
  border: none;
  background: var(--accent);
  color: white;
  font-size: 5rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
  transition: transform 120ms ease, background 120ms ease;
  touch-action: manipulation;
}

.play-btn:active {
  transform: scale(0.96);
  background: #c53b2e;
}

.play-btn__icon {
  line-height: 1;
}

.progress {
  width: 100%;
  height: 6px;
  background: var(--progress-bg);
  border-radius: 3px;
  overflow: hidden;
}

.progress__bar {
  height: 100%;
  width: 0%;
  background: var(--accent);
  transition: width 200ms linear;
}

.time {
  margin: 0;
  font-size: 1.2rem;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}

.time__sep {
  margin: 0 6px;
}

.seek-buttons {
  display: flex;
  gap: 16px;
  width: 100%;
  justify-content: center;
}

.seek-btn {
  flex: 1;
  max-width: 140px;
  padding: 14px 16px;
  border-radius: 14px;
  background: transparent;
  color: var(--fg);
  border: 2px solid var(--muted);
  font-size: 1.1rem;
  cursor: pointer;
  touch-action: manipulation;
}

.seek-btn:active {
  background: rgba(255, 255, 255, 0.06);
}

.status {
  min-height: 1.4em;
  margin: 0;
  color: var(--muted);
  font-size: 1rem;
}
```

- [ ] **Step 2: Manual verification**

Open `pwa/index.html` in a desktop browser and resize to phone width (DevTools → Device Toolbar → iPhone/Pixel).
Expected:
- Dark background, white text
- Title centered, red circular Play button is the dominant element
- Progress bar and time display below
- Seek buttons at bottom, large enough to tap

- [ ] **Step 3: Commit**

```bash
git add pwa/style.css
git commit -m "feat(pwa): dark-theme styling with huge Play button UI"
```

---

### Task 13: PWA audio logic

**Files:**
- Create: `pwa/app.js`

- [ ] **Step 1: Write `pwa/app.js`**

```javascript
(() => {
  "use strict";

  const MONTHS_RO = [
    "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie",
    "iulie", "august", "septembrie", "octombrie", "noiembrie", "decembrie",
  ];

  const audio = document.getElementById("audio");
  const playBtn = document.getElementById("play-btn");
  const playIcon = document.getElementById("play-btn-icon");
  const dateEl = document.getElementById("bulletin-date");
  const progressBar = document.getElementById("progress-bar");
  const timeCurrent = document.getElementById("time-current");
  const timeTotal = document.getElementById("time-total");
  const seekBack = document.getElementById("seek-back");
  const seekFwd = document.getElementById("seek-fwd");
  const statusEl = document.getElementById("status");

  let wakeLock = null;

  function formatDateRo(isoDate) {
    const [y, m, d] = isoDate.split("-").map(Number);
    return `${d} ${MONTHS_RO[m - 1]}`;
  }

  function formatTime(seconds) {
    if (!Number.isFinite(seconds) || seconds < 0) seconds = 0;
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  }

  function setPlayIcon(isPlaying) {
    playIcon.textContent = isPlaying ? "⏸" : "▶";
    playBtn.setAttribute("aria-label", isPlaying ? "Pauză" : "Redare");
  }

  async function acquireWakeLock() {
    if (!("wakeLock" in navigator)) return;
    try {
      wakeLock = await navigator.wakeLock.request("screen");
    } catch (_) { /* ignore */ }
  }

  function releaseWakeLock() {
    if (wakeLock) {
      wakeLock.release().catch(() => {});
      wakeLock = null;
    }
  }

  function setupMediaSession(title, date) {
    if (!("mediaSession" in navigator)) return;
    navigator.mediaSession.metadata = new MediaMetadata({
      title: "Știri Tată",
      artist: `Buletin din ${formatDateRo(date)}`,
      album: "Știri Tată",
      artwork: [
        { src: "icons/icon-192.png", sizes: "192x192", type: "image/png" },
        { src: "icons/icon-512.png", sizes: "512x512", type: "image/png" },
      ],
    });
    navigator.mediaSession.setActionHandler("play", () => audio.play());
    navigator.mediaSession.setActionHandler("pause", () => audio.pause());
    navigator.mediaSession.setActionHandler("seekbackward", (d) => seek(-(d.seekOffset || 30)));
    navigator.mediaSession.setActionHandler("seekforward", (d) => seek(d.seekOffset || 30));
  }

  function seek(delta) {
    const target = Math.max(0, Math.min(audio.duration || 0, audio.currentTime + delta));
    audio.currentTime = target;
  }

  async function loadManifestAndAudio() {
    statusEl.textContent = "";
    try {
      // Cache-bust manifest so we always see the latest even when the SW is cached.
      const resp = await fetch(`latest.json?t=${Date.now()}`, { cache: "no-cache" });
      if (!resp.ok) throw new Error(`manifest http ${resp.status}`);
      const manifest = await resp.json();

      dateEl.textContent = `Buletin din ${formatDateRo(manifest.date)}`;
      audio.src = `latest.mp3?v=${encodeURIComponent(manifest.date)}`;
      setupMediaSession("Știri Tată", manifest.date);

      if (Number.isFinite(manifest.duration_seconds)) {
        timeTotal.textContent = formatTime(manifest.duration_seconds);
      }
    } catch (err) {
      // Offline / server down: fall back to whatever the SW has cached.
      statusEl.textContent = "Folosim buletinul salvat local.";
      audio.src = "latest.mp3";
      dateEl.textContent = "Buletin din cache";
    }
  }

  // --- event wiring ---

  playBtn.addEventListener("click", async () => {
    if (audio.paused) {
      try {
        await audio.play();
        await acquireWakeLock();
      } catch (err) {
        statusEl.textContent = "Nu pot reda audio. Verifică conexiunea.";
      }
    } else {
      audio.pause();
    }
  });

  seekBack.addEventListener("click", () => seek(-30));
  seekFwd.addEventListener("click", () => seek(30));

  audio.addEventListener("play", () => setPlayIcon(true));
  audio.addEventListener("pause", () => { setPlayIcon(false); releaseWakeLock(); });
  audio.addEventListener("ended", () => { setPlayIcon(false); releaseWakeLock(); });

  audio.addEventListener("loadedmetadata", () => {
    if (Number.isFinite(audio.duration)) {
      timeTotal.textContent = formatTime(audio.duration);
    }
  });

  audio.addEventListener("timeupdate", () => {
    const cur = audio.currentTime || 0;
    const dur = audio.duration || 0;
    timeCurrent.textContent = formatTime(cur);
    if (dur > 0) {
      progressBar.style.width = `${(cur / dur) * 100}%`;
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && wakeLock === null && !audio.paused) {
      acquireWakeLock();
    }
  });

  // Register service worker
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    });
  }

  loadManifestAndAudio();
})();
```

- [ ] **Step 2: Manual verification (smoke test)**

1. Create a stub `pwa/latest.json`:
   ```json
   {"date":"2026-04-19","duration_seconds":120,"audio_url":"latest.mp3","generated_at":"2026-04-19T06:03:00+00:00"}
   ```
2. Drop any short MP3 file as `pwa/latest.mp3` (any test MP3 works; if you don't have one, use an online sample).
3. Run a quick local server and open the page:
   ```bash
   cd pwa && python -m http.server 8000
   ```
4. Open `http://localhost:8000` in Chrome.

Expected:
- "Buletin din 19 aprilie" text visible
- Play button starts audio; icon flips to ⏸
- Progress bar advances; time counter updates
- `⏪ 30` and `30 ⏩` seek correctly
- No console errors (ignore SW warnings — Task 14 covers SW)

- [ ] **Step 3: Clean up smoke-test files (don't commit the stub)**

```bash
rm pwa/latest.json pwa/latest.mp3
```

- [ ] **Step 4: Commit**

```bash
git add pwa/app.js
git commit -m "feat(pwa): audio player logic with wake lock and media session"
```

---

### Task 14: Service worker (offline caching)

**Files:**
- Create: `pwa/sw.js`

- [ ] **Step 1: Write `pwa/sw.js`**

```javascript
// Cache strategy:
// - APP_SHELL (HTML, CSS, JS, icons, manifest): cache-first, versioned.
// - AUDIO (latest.mp3): stale-while-revalidate keyed by manifest date.
// - MANIFEST (latest.json): network-first with cache fallback.

const SHELL_CACHE = "stiritata-shell-v1";
const AUDIO_CACHE = "stiritata-audio-v1";

const SHELL_ASSETS = [
  "./",
  "index.html",
  "style.css",
  "app.js",
  "manifest.webmanifest",
  "icons/icon-192.png",
  "icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names
          .filter((n) => ![SHELL_CACHE, AUDIO_CACHE].includes(n))
          .map((n) => caches.delete(n))
      )
    )
  );
  self.clients.claim();
});

function isManifest(url) {
  return url.pathname.endsWith("/latest.json") || url.pathname.endsWith("latest.json");
}

function isAudio(url) {
  return url.pathname.endsWith(".mp3");
}

function isShell(url) {
  return SHELL_ASSETS.some((asset) => {
    if (asset === "./") return url.pathname.endsWith("/") || url.pathname.endsWith("/index.html");
    return url.pathname.endsWith(asset);
  });
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  if (isManifest(url)) {
    // Network-first for the manifest so we pick up new bulletins quickly.
    event.respondWith(
      fetch(req)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(AUDIO_CACHE).then((c) => c.put(req, copy));
          return resp;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  if (isAudio(url)) {
    // Stale-while-revalidate: serve cache immediately, refresh in background.
    event.respondWith(
      caches.open(AUDIO_CACHE).then(async (cache) => {
        const cached = await cache.match(req, { ignoreSearch: true });
        const networkPromise = fetch(req)
          .then((resp) => {
            if (resp && resp.ok) cache.put(req, resp.clone());
            return resp;
          })
          .catch(() => cached);
        return cached || networkPromise;
      })
    );
    return;
  }

  if (isShell(url)) {
    event.respondWith(
      caches.match(req).then((cached) => cached || fetch(req))
    );
    return;
  }

  // Default: try network, fall back to cache.
  event.respondWith(fetch(req).catch(() => caches.match(req)));
});
```

- [ ] **Step 2: Manual verification**

1. Serve the PWA again with `python -m http.server 8000` from `pwa/` (with the stub files recreated).
2. Open Chrome DevTools → Application → Service Workers. Confirm `sw.js` is registered and running.
3. Reload once. Check Application → Cache Storage — you should see `stiritata-shell-v1` populated.
4. Switch DevTools → Network to "Offline" and reload.
   Expected: page loads from cache, status text falls back gracefully.
5. Clean up stub files again: `rm pwa/latest.json pwa/latest.mp3`.

- [ ] **Step 3: Commit**

```bash
git add pwa/sw.js
git commit -m "feat(pwa): service worker with cache strategies for shell, audio, and manifest"
```

---

### Task 15: End-to-end verification + user deploy actions

**Files:** none new; this task is integration + user-side actions.

**Goal:** First successful production run, installation on devices, OpenAI key rotation.

- [ ] **Step 1: User action — create GitHub repo**

Tell the user:
> Create a new **public** repo on GitHub called `stiritata`. Do NOT initialize with README (we have local files).
> Copy the remote URL.

Then locally:

```bash
git remote add origin <repo-url-from-user>
git push -u origin main
```

- [ ] **Step 2: User action — set GitHub Secrets**

Tell the user:
> 1. Go to https://platform.openai.com/api-keys → create a NEW key (we will not use the one from `GPT.txt`).
> 2. Go to https://openweathermap.org/api → create free account → copy the default API key.
> 3. On GitHub: `Settings → Secrets and variables → Actions → New repository secret` twice:
>    - `OPENAI_API_KEY` = new OpenAI key
>    - `OPENWEATHER_API_KEY` = OpenWeatherMap key

- [ ] **Step 3: User action — enable GitHub Pages**

Tell the user:
> `Settings → Pages → Build and deployment → Source: GitHub Actions`

- [ ] **Step 4: Trigger first run**

Tell the user:
> `Actions → daily-bulletin → Run workflow → Run`

Then watch the job logs. Expected: build job completes in ~3-5 min; deploy job publishes to Pages URL like `https://<user>.github.io/stiritata/`.

- [ ] **Step 5: Verification — open the PWA on desktop**

Open the Pages URL in Chrome. Expected:
- Page loads, shows today's date formatted in Romanian
- Press Play → audio starts, is in Romanian with the Piper voice
- Listen to first 2 minutes. Verify:
  - Intro says "Bună dimineața, tată. Astăzi este [ziua], [data]."
  - Weather section mentions Reșița with a reasonable temperature
  - At least one local/national news item is recognizable
  - Audio has no loud clicks or severely broken pronunciation

If any of these fail, fix before proceeding:
- Voice model wrong → check `scripts/download_voice.sh` output in Actions logs
- Empty news categories → `sources.yaml` RSS URLs may be broken; check warnings in logs
- ChatGPT timed out → retry workflow; if persistent, check OpenAI quota

- [ ] **Step 6: Duration and quality check**

Note the total duration on the PWA. Expected: between 9 and 16 minutes. If off:
- Too short (< 8 min): prompt's word target needs bumping — edit `generator/prompt.py` SYSTEM_PROMPT line about "2200-2500 de cuvinte" upward
- Too long (> 17 min): same, downward

- [ ] **Step 7: Install on devices (user action)**

Tell the user:
> On tata's phone and tablet, in Chrome:
> 1. Open `https://<user>.github.io/stiritata/`
> 2. Menu (⋮) → `Add to Home screen` → confirm
> 3. The icon appears on the home screen; tap to open as an app (no browser UI)
> 4. Press Play to test

- [ ] **Step 8: Revoke the exposed OpenAI key**

Tell the user:
> On https://platform.openai.com/api-keys, **revoke** the old key that was in `GPT.txt`. The new key in GitHub Secrets is the only one still active.

Then locally, delete the exposed key file so it can't leak further:

```bash
rm GPT.txt
git add -A
git commit -m "chore: remove exposed local OpenAI key file"
git push
```

- [ ] **Step 9: Monitor for 3-4 days**

Tell the user:
> Each morning for the next 3-4 days, open the Actions tab and check the run succeeded, then ask tata how the bulletin sounded. Adjust `generator/prompt.py` or `sources.yaml` based on his feedback (e.g., "prea mult fotbal", "vreau mai multe știri locale"). Commit + push = live next morning.

- [ ] **Step 10: Mark plan complete**

Tell the user the app is live and running daily. Point to the spec's §8 risks list — if any show up, they're handled there.

---

## Out of Scope (per spec §9)

These were discussed and deliberately excluded from this plan:
- Multi-user profiles
- In-app subject/duration customization by tata
- Dark mode toggle (already dark)
- Push notifications
- Playback speed controls (±10%)
- Exposing archive in UI
- Authentication
- Other languages

Any of these can become a follow-up plan if needed.
