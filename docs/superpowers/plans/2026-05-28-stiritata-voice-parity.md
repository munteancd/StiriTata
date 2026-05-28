# Știri Tată Voice & PWA Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Știri Tată multi-voice TTS (Mihai/Alina/Emil, default female Alina) and the newer PWA player features (voice picker, playback speed, weather theme, headlines) while preserving its chapters, topics, weather location, and branding.

**Architecture:** Surgical port. Backend gains the `tts.py` voice registry, the `text_utils.py` romanization helpers, a multi-voice loop in `main.py`, and an extended `build_manifest.py`. Frontend gains four player features via targeted edits to `index.html`, `style.css`, `app.js` — keeping Știri Tată's chapter nav, seek buttons, and resume-hint.

**Tech Stack:** Python 3 (piper-tts, edge-tts, openai, httpx), vanilla JS PWA, GitHub Actions, pytest.

**Working directories (Windows path mismatch note):** Both repos are checked out at `D:\tmp\StiriTata` (target) and `D:\tmp\StiriCristi` (reference source). In the git-bash Bash tool these are `/d/tmp/StiriTata` and `/d/tmp/StiriCristi`. The Write/Edit tools resolve a leading `/tmp` to `D:\tmp`, so always pass Windows-style absolute paths (e.g. `D:\tmp\StiriTata\...`) to Write/Edit, and `/d/tmp/...` to Bash.

---

## File Structure

**Backend (`generator/`):**
- `tts.py` — REPLACE with voice registry (PiperConfig, EdgeTTSConfig, VoiceSpec, synthesize/synthesize_edge/synthesize_voice).
- `text_utils.py` — APPEND romanization helpers (`romanize_for_tts`, `romanize_for_edge_tts` + tables).
- `build_manifest.py` — REPLACE with version supporting headlines/weather_summary/voices/chapters.
- `main.py` — MODIFY: multi-voice loop, `_resolve_voices`, manifest with headlines+weather_summary+voices, keep `_build_chapters` and single-city Reșița weather.
- `requirements.txt` — ADD `edge-tts>=6.1.10`.

**CI:**
- `.github/workflows/daily.yml` — ADD `TTS_VOICES: alina,mihai,emil` to the generator run step env.

**Frontend (`pwa/`):**
- `index.html` — ADD controls-top (speed + voice buttons), voice-panel, headlines-container.
- `style.css` — ADD `--glass` var, weather theme body classes, controls/voice/headlines/play-pulse classes.
- `app.js` — ADD speed control, voice picker, weather theme, headlines render, play-pulse toggle. Keep chapters/seek/resume.

**Tests (`tests/`):**
- `test_tts.py` — ADD voice-registry tests.
- `test_build_manifest.py` — ADD voices/headlines manifest tests.

---

## Task 1: Backend dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add edge-tts dependency**

Append this line to `D:\tmp\StiriTata\requirements.txt` (after the `piper-tts==1.2.0` line):

```
edge-tts>=6.1.10
```

- [ ] **Step 2: Install it**

Run (in `/d/tmp/StiriTata`): `pip install -r requirements.txt`
Expected: edge-tts installs without error.

- [ ] **Step 3: Commit**

```bash
cd /d/tmp/StiriTata
git add requirements.txt
git commit -m "Add edge-tts dependency for neural Romanian voices"
```

---

## Task 2: Voice registry (`tts.py`)

**Files:**
- Replace: `generator/tts.py`
- Test: `tests/test_tts.py`

- [ ] **Step 1: Replace tts.py with the Știri Cristi voice-registry version**

Copy the reference file verbatim:

Run (in `/d/tmp`): `cp StiriCristi/generator/tts.py StiriTata/generator/tts.py`

This file contains: `PiperConfig`, `EdgeTTSConfig`, `synthesize`, `synthesize_edge`, `synthesize_voice`, and the registry `AVAILABLE_VOICES` (mihai=piper, alina=edge female `ro-RO-AlinaNeural`, emil=edge male `ro-RO-EmilNeural`) + `VOICE_BY_ID`. No edits needed — it is app-agnostic.

- [ ] **Step 2: Add a failing test for the voice registry**

Append to `D:\tmp\StiriTata\tests\test_tts.py`:

```python
from generator.tts import (
    VOICE_BY_ID,
    AVAILABLE_VOICES,
    EdgeTTSConfig,
    synthesize_voice,
)


def test_registry_has_female_alina_voice():
    assert "alina" in VOICE_BY_ID
    alina = VOICE_BY_ID["alina"]
    assert alina.gender == "female"
    assert alina.backend == "edge"
    assert isinstance(alina.config, EdgeTTSConfig)
    assert alina.config.voice == "ro-RO-AlinaNeural"


def test_registry_exposes_three_voices():
    ids = {v.id for v in AVAILABLE_VOICES}
    assert ids == {"mihai", "alina", "emil"}


def test_synthesize_voice_dispatches_to_edge_for_alina(tmp_path):
    out = tmp_path / "latest-alina.mp3"
    with patch("generator.tts.synthesize_edge", return_value=12.3) as edge_mock, \
         patch("generator.tts.synthesize", return_value=0.0) as piper_mock:
        dur = synthesize_voice(text="Salut", out_mp3=out, voice=VOICE_BY_ID["alina"])
    assert dur == 12.3
    assert edge_mock.called
    assert not piper_mock.called


def test_synthesize_voice_dispatches_to_piper_for_mihai(tmp_path):
    out = tmp_path / "latest-mihai.mp3"
    with patch("generator.tts.synthesize_edge", return_value=0.0) as edge_mock, \
         patch("generator.tts.synthesize", return_value=7.7) as piper_mock:
        dur = synthesize_voice(text="Salut", out_mp3=out, voice=VOICE_BY_ID["mihai"])
    assert dur == 7.7
    assert piper_mock.called
    assert not edge_mock.called
```

- [ ] **Step 3: Run the new tests, expect FAIL then PASS**

Run (in `/d/tmp/StiriTata`): `python -m pytest tests/test_tts.py -v`
Expected: the 4 new tests PASS (registry exists after Step 1). If `synthesize_voice` import fails, re-check Step 1 copy.

- [ ] **Step 4: Commit**

```bash
cd /d/tmp/StiriTata
git add generator/tts.py tests/test_tts.py
git commit -m "Add multi-voice TTS registry (Mihai/Alina/Emil)"
```

---

## Task 3: Romanization helpers (`text_utils.py`)

**Files:**
- Modify: `generator/text_utils.py`
- Test: `tests/test_text_utils.py`

- [ ] **Step 1: Append the romanization section from Știri Cristi**

`StiriCristi/generator/text_utils.py` lines 1–149 are identical to Știri Tată's current file (date/number/dedup helpers). Lines 150–320 add `romanize_for_tts`, `romanize_for_edge_tts`, and the `_PHONETICS` / `_EDGE_CORRECTIONS` tables plus their compiled-regex helpers.

Append lines 150–320 of `StiriCristi/generator/text_utils.py` to the end of `StiriTata/generator/text_utils.py`. Also ensure the import line `from typing import List, Tuple` is present near the top of Știri Tată's file (add it under `from datetime import datetime` if missing — the tables are typed `List[Tuple[str, str]]`).

Run (in `/d/tmp`) to do the append, then add the import manually if needed:
```bash
sed -n '150,320p' StiriCristi/generator/text_utils.py >> StiriTata/generator/text_utils.py
```
Then verify the top of `StiriTata/generator/text_utils.py` has `from typing import List, Tuple`; add it with the Edit tool if absent.

- [ ] **Step 2: Add tests for the romanization helpers**

Append to `D:\tmp\StiriTata\tests\test_text_utils.py`:

```python
from generator.text_utils import romanize_for_tts, romanize_for_edge_tts


def test_romanize_for_tts_returns_string():
    out = romanize_for_tts("Real Madrid a câștigat meciul")
    assert isinstance(out, str)
    assert len(out) > 0


def test_romanize_for_edge_tts_corrects_spanish_name():
    # Edge corrections map Spanish 'j' names to Romanian-phonetic spelling.
    out = romanize_for_edge_tts("José a marcat un gol")
    assert "Hose" in out
```

- [ ] **Step 3: Run tests**

Run (in `/d/tmp/StiriTata`): `python -m pytest tests/test_text_utils.py -v`
Expected: all PASS. If `test_romanize_for_edge_tts_corrects_spanish_name` fails, confirm `_EDGE_CORRECTIONS` was copied (it maps "José"→"Hose").

- [ ] **Step 4: Commit**

```bash
cd /d/tmp/StiriTata
git add generator/text_utils.py tests/test_text_utils.py
git commit -m "Add Romanian romanization helpers for Piper and Edge TTS"
```

---

## Task 4: Extend manifest (`build_manifest.py`)

**Files:**
- Replace: `generator/build_manifest.py`
- Test: `tests/test_build_manifest.py`

- [ ] **Step 1: Replace build_manifest.py with the Știri Cristi version**

Run (in `/d/tmp`): `cp StiriCristi/generator/build_manifest.py StiriTata/generator/build_manifest.py`

This version accepts `headlines`, `weather_summary`, `chapters`, and `voices` (all optional, additive). Chapters still work, so existing tests stay green.

- [ ] **Step 2: Add tests for the new optional fields**

Append to `D:\tmp\StiriTata\tests\test_build_manifest.py`:

```python
def test_manifest_includes_voices_and_headlines_when_provided():
    date = datetime(2026, 5, 28, 6, 0, tzinfo=timezone.utc)
    voices = [{"id": "alina", "label": "Alina", "gender": "female", "url": "latest-alina.mp3"}]
    headlines = ["Titlu unu", "Titlu doi"]
    manifest = build_manifest(
        date=date,
        duration_seconds=600.0,
        audio_url="latest.mp3",
        generated_at=datetime(2026, 5, 28, 6, 3, tzinfo=timezone.utc),
        headlines=headlines,
        weather_summary="cer senin",
        voices=voices,
    )
    assert manifest["voices"] == voices
    assert manifest["headlines"] == headlines
    assert manifest["weather_summary"] == "cer senin"


def test_manifest_omits_voices_when_not_provided():
    date = datetime(2026, 5, 28, 6, 0, tzinfo=timezone.utc)
    manifest = build_manifest(
        date=date,
        duration_seconds=600.0,
        audio_url="latest.mp3",
        generated_at=datetime(2026, 5, 28, 6, 3, tzinfo=timezone.utc),
    )
    assert "voices" not in manifest
    assert "headlines" not in manifest
```

- [ ] **Step 3: Run tests**

Run (in `/d/tmp/StiriTata`): `python -m pytest tests/test_build_manifest.py -v`
Expected: all PASS (existing chapter test + 2 new).

- [ ] **Step 4: Commit**

```bash
cd /d/tmp/StiriTata
git add generator/build_manifest.py tests/test_build_manifest.py
git commit -m "Extend manifest with voices, headlines, weather_summary"
```

---

## Task 5: Multi-voice pipeline (`main.py`)

**Files:**
- Modify: `generator/main.py`
- Test: `tests/test_main.py`

This is a merge: take Știri Tată's `main.py` (single-city Reșița weather + `_build_chapters`) and add Știri Cristi's multi-voice loop + `_resolve_voices` + extended manifest. Below is the **complete** new file.

- [ ] **Step 1: Write the new main.py**

Replace the entire contents of `D:\tmp\StiriTata\generator\main.py` with:

```python
import argparse
import asyncio
import json
import logging
import math
import os
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml
from dotenv import load_dotenv

from .build_manifest import build_manifest
from .fetch_news import fetch_all_sources
from .fetch_weather import fetch_weather
from .fetch_history import fetch_history
from .models import NewsItem
from .prompt import SECTIONS
from .summarize import summarize
from .tts import VOICE_BY_ID, VoiceSpec, synthesize_voice

log = logging.getLogger(__name__)

DEFAULT_MAX_ITEMS_PER_CATEGORY = 12

CHAPTER_TITLES = {
    "meteo": "Meteo",
    "local_politics": "Locale",
    "ukraine_war": "Ucraina",
    "national_politics": "Naționale",
    "international_politics": "Internațional",
    "football_ro": "Fotbal RO",
    "football_eu": "Fotbal Europa",
    "history": "Istorie",
}


def _cap_items_per_category(items: List[NewsItem], max_per_cat: int) -> List[NewsItem]:
    by_cat: "defaultdict[str, list[NewsItem]]" = defaultdict(list)
    for it in items:
        by_cat[it.category].append(it)
    capped: List[NewsItem] = []
    for cat, cat_items in by_cat.items():
        cat_items.sort(key=lambda x: x.published, reverse=True)
        capped.extend(cat_items[:max_per_cat])
    return capped


def _build_chapters(duration_seconds: float) -> list[dict[str, Any]]:
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        return []
    total_weight = sum(max(1, section.target_words) for section in SECTIONS)
    cursor = 0
    chapters: list[dict[str, Any]] = []
    for section in SECTIONS:
        chapters.append({
            "key": section.key,
            "title": CHAPTER_TITLES.get(section.key, section.key.replace("_", " ").title()),
            "start_seconds": round((cursor / total_weight) * duration_seconds, 1),
        })
        cursor += max(1, section.target_words)
    return chapters


def _resolve_voices(voice_ids: list[str]) -> list[VoiceSpec]:
    voices = []
    for vid in voice_ids:
        if vid not in VOICE_BY_ID:
            log.warning("unknown voice id %r, skipping (available: %s)", vid, list(VOICE_BY_ID))
            continue
        voices.append(VOICE_BY_ID[vid])
    if not voices:
        log.warning("no valid voices configured; falling back to 'alina'")
        voices = [VOICE_BY_ID["alina"]]
    return voices


async def run_pipeline(
    *,
    sources_cfg: Dict[str, Any],
    public_dir: Path,
    archive_dir: Path,
    openai_client: Any,
    openweather_api_key: str,
    now: datetime | None = None,
    max_items_per_category: int = DEFAULT_MAX_ITEMS_PER_CATEGORY,
    voice_ids: list[str] | None = None,
) -> None:
    now = now or datetime.now(tz=timezone.utc)
    public_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    voices = _resolve_voices(voice_ids or ["alina"])

    rss_cfg = {k: v for k, v in sources_cfg.items() if k != "weather"}
    weather_cfg = sources_cfg.get("weather", {})

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

    items = _cap_items_per_category(items, max_items_per_category)
    log.info("capped to %d items (max %d per category)", len(items), max_items_per_category)

    # 2. Summarize via ChatGPT. On failure, keep yesterday's MP3.
    try:
        text = summarize(
            items=items,
            weather=weather,
            bulletin_date=now,
            client=openai_client,
            history=history,
        )
    except Exception as exc:
        log.error("summarize failed, keeping previous bulletin: %s", exc)
        return

    # 3. TTS → MP3 (one file per configured voice)
    duration = 0.0
    generated_voice_infos: list[dict] = []

    for voice in voices:
        voice_mp3 = public_dir / f"latest-{voice.id}.mp3"
        try:
            dur = synthesize_voice(text=text, out_mp3=voice_mp3, voice=voice)
            log.info("TTS OK: %s → %s (%.1fs)", voice.id, voice_mp3, dur)
            generated_voice_infos.append({
                "id": voice.id,
                "label": voice.label,
                "gender": voice.gender,
                "url": f"latest-{voice.id}.mp3",
            })
            # First voice that succeeds becomes the default latest.mp3
            if not duration:
                shutil.copy2(voice_mp3, public_dir / "latest.mp3")
                duration = dur
        except (FileNotFoundError, RuntimeError, Exception) as exc:
            log.warning("TTS failed for voice %r: %s", voice.id, exc)

    if not generated_voice_infos:
        log.error("All TTS voices failed (%s), saving text only", [v.id for v in voices])
        (public_dir / "latest.txt").write_text(text, encoding="utf-8")
        return

    log.info(
        "TTS complete: %d/%d voices ok: %s",
        len(generated_voice_infos), len(voices),
        [v["id"] for v in generated_voice_infos],
    )
    out_mp3 = public_dir / "latest.mp3"

    # 4. Archive a dated copy
    dated = archive_dir / f"{now.strftime('%Y-%m-%d')}.mp3"
    shutil.copy2(out_mp3, dated)

    # 5. Trim archive to last 7
    archives = sorted(archive_dir.glob("*.mp3"), key=lambda p: p.name, reverse=True)
    for old in archives[7:]:
        try:
            old.unlink()
        except OSError as exc:
            log.warning("failed to unlink %s: %s", old, exc)

    # 6. Write manifest (chapters + headlines + weather_summary + voices)
    headlines = [it.title for it in items[:15]]
    weather_summary = weather.description if weather else ""

    manifest = build_manifest(
        date=now,
        duration_seconds=duration,
        audio_url="latest.mp3",
        generated_at=datetime.now(tz=timezone.utc),
        headlines=headlines,
        weather_summary=weather_summary,
        chapters=_build_chapters(duration),
        voices=generated_voice_infos if len(generated_voice_infos) > 1 else None,
    )

    (public_dir / "latest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 7. Write the bulletin text
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
    parser.add_argument(
        "--voices",
        default=None,
        help="Comma-separated voice IDs to generate (e.g. alina,mihai,emil). "
             "Overrides TTS_VOICES env var. Default: alina.",
    )
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

    raw_voices = args.voices or os.environ.get("TTS_VOICES", "alina")
    voice_ids = [v.strip() for v in raw_voices.split(",") if v.strip()]

    from openai import OpenAI
    client = OpenAI(api_key=openai_key)

    asyncio.run(
        run_pipeline(
            sources_cfg=sources_cfg,
            public_dir=public_dir,
            archive_dir=archive_dir,
            openai_client=client,
            openweather_api_key=openweather_key,
            voice_ids=voice_ids,
        )
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add a test for `_resolve_voices`**

Append to `D:\tmp\StiriTata\tests\test_main.py`:

```python
from generator.main import _resolve_voices


def test_resolve_voices_keeps_known_and_drops_unknown():
    voices = _resolve_voices(["alina", "bogus", "mihai"])
    ids = [v.id for v in voices]
    assert ids == ["alina", "mihai"]


def test_resolve_voices_defaults_to_alina_when_all_unknown():
    voices = _resolve_voices(["bogus"])
    assert [v.id for v in voices] == ["alina"]
```

- [ ] **Step 3: Run the full test suite**

Run (in `/d/tmp/StiriTata`): `python -m pytest -v`
Expected: all tests PASS, including existing `test_main.py` tests. If an existing main test calls `run_pipeline` without `voice_ids`, it still works (defaults to alina) — confirm those tests mock `synthesize_voice` or the weather/summarize calls. If a pre-existing test patched `generator.main.synthesize` (the old single-voice symbol), update it to patch `generator.main.synthesize_voice`.

- [ ] **Step 4: Commit**

```bash
cd /d/tmp/StiriTata
git add generator/main.py tests/test_main.py
git commit -m "Generate one MP3 per voice; default to female Alina"
```

---

## Task 6: CI workflow voice env

**Files:**
- Modify: `.github/workflows/daily.yml`

- [ ] **Step 1: Add TTS_VOICES to the generator run step**

Open `D:\tmp\StiriTata\.github\workflows\daily.yml`. Find the step that runs `python -m generator.main --sources sources.yaml --public-dir public`. Add an `env:` block to that step (or add to its existing `env:`):

```yaml
        env:
          TTS_VOICES: alina,mihai,emil
```

Ensure indentation matches the existing step (the `env:` key aligns with `run:` under the same `- name:` step). The existing `OPENAI_API_KEY` / `OPENWEATHER_API_KEY` env entries (if present on that step) must be preserved — add `TTS_VOICES` alongside them.

- [ ] **Step 2: Validate YAML**

Run (in `/d/tmp/StiriTata`): `python -c "import yaml; yaml.safe_load(open('.github/workflows/daily.yml')); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
cd /d/tmp/StiriTata
git add .github/workflows/daily.yml
git commit -m "Enable Alina/Mihai/Emil voices in daily workflow"
```

---

## Task 7: Frontend — index.html

**Files:**
- Modify: `pwa/index.html`

- [ ] **Step 1: Add the controls-top, voice panel, and headlines container**

In `D:\tmp\StiriTata\pwa\index.html`:

(a) Add `class="theme-default"` to the `<body>` tag: change `<body>` to `<body class="theme-default">`.

(b) Immediately after `<main class="app">` and BEFORE `<h1 class="app__title">Știri Tată</h1>`, insert:

```html
    <div class="controls-top">
      <button id="speed-btn" class="speed-btn" type="button" aria-label="Viteză redare">1×</button>
      <button id="voice-btn" class="voice-btn" type="button" aria-label="Alege vocea" hidden>🎙</button>
    </div>

    <!-- Voice picker panel -->
    <div id="voice-panel" class="voice-panel" hidden role="dialog" aria-label="Selectare voce">
      <p class="voice-panel__title">Voce narator</p>
      <div id="voice-options" class="voice-options">
        <!-- populated by app.js -->
      </div>
    </div>

```

(c) Immediately after the `<p class="status" ...></p>` line and BEFORE `</main>`, insert:

```html

    <div class="headlines-container" id="headlines-container" hidden>
      <h2 class="headlines-title">În ediția de azi:</h2>
      <ul class="headlines-list" id="headlines-list">
        <!-- populated by app.js -->
      </ul>
    </div>
```

- [ ] **Step 2: Commit**

```bash
cd /d/tmp/StiriTata
git add pwa/index.html
git commit -m "Add voice picker, speed control, and headlines markup"
```

---

## Task 8: Frontend — style.css

**Files:**
- Modify: `pwa/style.css`

- [ ] **Step 1: Add the --glass variable**

In `D:\tmp\StiriTata\pwa\style.css`, inside the `:root { ... }` block, add after `--progress-bg: #333;`:

```css
  --glass: rgba(255, 255, 255, 0.05);
```

- [ ] **Step 2: Add weather theme classes and make background fixed**

Immediately after the closing `}` of the `:root` block, add:

```css
/* Weather Themes */
body.theme-clear { --bg: linear-gradient(180deg, #1a1a1a 0%, #2c3e50 100%); --accent: #f39c12; }
body.theme-clouds { --bg: linear-gradient(180deg, #1a1a1a 0%, #4a4a4a 100%); --accent: #95a5a6; }
body.theme-rain { --bg: linear-gradient(180deg, #1a1a1a 0%, #1e3a5f 100%); --accent: #3498db; }
body.theme-snow { --bg: linear-gradient(180deg, #1a1a1a 0%, #2c3e50 100%); --accent: #ecf0f1; }
body.theme-storm { --bg: linear-gradient(180deg, #000000 0%, #1a1a1a 100%); --accent: #9b59b6; }
```

In the `html, body { ... }` rule, add `background-attachment: fixed;` and `min-height: 100%;` (so gradient themes fill the screen).

- [ ] **Step 3: Append the component classes (controls, voice, headlines, play-pulse)**

Append to the end of `D:\tmp\StiriTata\pwa\style.css`:

```css
.controls-top {
  width: 100%;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  align-items: center;
}

.speed-btn {
  background: var(--glass);
  border: 1px solid var(--muted);
  color: var(--fg);
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 0.9rem;
  cursor: pointer;
}

.voice-btn {
  background: var(--glass);
  border: 1px solid var(--muted);
  color: var(--fg);
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 1rem;
  cursor: pointer;
  line-height: 1;
}

.voice-panel {
  width: 100%;
  background: var(--glass);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 14px;
  padding: 16px;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.voice-panel__title {
  margin: 0 0 12px;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--muted);
}

.voice-options {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.voice-option {
  flex: 1;
  min-width: 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 8px;
  border-radius: 10px;
  border: 2px solid var(--muted);
  background: transparent;
  color: var(--fg);
  cursor: pointer;
  font-size: 0.85rem;
  transition: border-color 120ms, background 120ms;
}

.voice-option__icon {
  font-size: 1.4rem;
  line-height: 1;
}

.voice-option--active {
  border-color: var(--accent);
  background: rgba(235, 70, 55, 0.12);
}

.play-btn--playing::after {
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { transform: scale(1); opacity: 0.6; }
  100% { transform: scale(1.4); opacity: 0; }
}

.headlines-container {
  width: 100%;
  background: var(--glass);
  border-radius: 16px;
  padding: 20px;
  text-align: left;
  margin-top: 12px;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.headlines-title {
  font-size: 1rem;
  color: var(--accent);
  margin: 0 0 12px 0;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.headlines-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.headline-item {
  font-size: 0.95rem;
  line-height: 1.4;
  color: var(--fg);
  display: flex;
  gap: 10px;
}

.headline-item::before {
  content: "•";
  color: var(--accent);
}
```

> Note: `.play-btn--playing::after` reuses the existing pulse ring. If Știri Tată's `.play-btn` does not already define an `::after` ring (absolute-positioned, `border: 4px solid var(--accent); opacity: 0;`), the animation has nothing to animate — verify the `.play-btn` rule has a positioned `::after`; if not, this is cosmetic-only and can be skipped without breaking anything.

- [ ] **Step 4: Commit**

```bash
cd /d/tmp/StiriTata
git add pwa/style.css
git commit -m "Add styles for voice picker, speed, weather themes, headlines"
```

---

## Task 9: Frontend — app.js

**Files:**
- Modify: `pwa/app.js`

All edits are inside the existing IIFE. Keep every existing function (chapters, seek, resume).

- [ ] **Step 1: Add DOM references**

In `D:\tmp\StiriTata\pwa\app.js`, after the line `const chaptersEl = document.getElementById("chapters");`, add:

```javascript
  const speedBtn = document.getElementById("speed-btn");
  const voiceBtn = document.getElementById("voice-btn");
  const voicePanel = document.getElementById("voice-panel");
  const voiceOptions = document.getElementById("voice-options");
  const headlinesList = document.getElementById("headlines-list");
  const headlinesContainer = document.getElementById("headlines-container");
```

- [ ] **Step 2: Add speed control + voice picker state/handlers**

Immediately after the `let wakeLock = null;` line, add:

```javascript
  // --- playback speed ---
  const speeds = [1, 1.25, 1.5, 2];
  let speedIdx = 0;
  speedBtn.addEventListener("click", () => {
    speedIdx = (speedIdx + 1) % speeds.length;
    const s = speeds[speedIdx];
    audio.playbackRate = s;
    speedBtn.textContent = `${s}×`;
  });

  // --- voice picker ---
  const VOICE_KEY = "stiritata:voice";
  let availableVoices = [];
  let currentVoiceId = null;

  function savedVoiceId() {
    return safeGet(VOICE_KEY);
  }

  function buildVoiceSrc(voice, date) {
    return `${voice.url}?v=${encodeURIComponent(date)}`;
  }

  function renderVoiceOptions() {
    const activeId = currentVoiceId;
    voiceOptions.innerHTML = availableVoices
      .map(v => {
        const icon = v.gender === "female" ? "👩" : "👨";
        const active = v.id === activeId ? " voice-option--active" : "";
        return `<button class="voice-option${active}" data-voice-id="${v.id}" type="button" aria-pressed="${v.id === activeId}">
          <span class="voice-option__icon">${icon}</span>
          <span>${v.label}</span>
        </button>`;
      })
      .join("");

    voiceOptions.querySelectorAll(".voice-option").forEach(btn => {
      btn.addEventListener("click", () => {
        const vid = btn.dataset.voiceId;
        const voice = availableVoices.find(v => v.id === vid);
        if (!voice || vid === currentVoiceId) return;

        const wasPlaying = !audio.paused;
        const pos = audio.currentTime;

        currentVoiceId = vid;
        safeSet(VOICE_KEY, vid);
        audio.src = buildVoiceSrc(voice, currentBulletinDate);

        audio.addEventListener("loadedmetadata", () => {
          audio.currentTime = Math.min(pos, audio.duration || 0);
          if (wasPlaying) audio.play().catch(() => {});
        }, { once: true });

        renderVoiceOptions();
      });
    });
  }

  voiceBtn.addEventListener("click", () => {
    voicePanel.hidden = !voicePanel.hidden;
  });

  document.addEventListener("click", (e) => {
    if (!voicePanel.hidden && !voicePanel.contains(e.target) && e.target !== voiceBtn) {
      voicePanel.hidden = true;
    }
  });
```

> The voice picker uses `safeGet`/`safeSet` (defined later in the file) and `currentBulletinDate` (declared later). Both are in the same closure scope and only referenced inside callbacks fired after init, so ordering is fine.

- [ ] **Step 3: Add weather theme + headlines render functions**

Before the `async function loadManifestAndAudio()` line, add:

```javascript
  function applyWeatherTheme(summary) {
    if (!summary) return;
    const s = summary.toLowerCase();
    let theme = "theme-default";
    if (s.includes("senin") || s.includes("clear")) theme = "theme-clear";
    else if (s.includes("nor") || s.includes("cloud")) theme = "theme-clouds";
    else if (s.includes("ploaie") || s.includes("rain") || s.includes("drizzle")) theme = "theme-rain";
    else if (s.includes("zăpadă") || s.includes("snow")) theme = "theme-snow";
    else if (s.includes("furtună") || s.includes("thunderstorm")) theme = "theme-storm";
    document.body.className = theme;
  }

  function renderHeadlines(headlines) {
    if (!headlines || headlines.length === 0) {
      headlinesContainer.hidden = true;
      return;
    }
    headlinesContainer.hidden = false;
    headlinesList.innerHTML = headlines
      .map(h => `<li class="headline-item">${h}</li>`)
      .join("");
  }
```

- [ ] **Step 4: Wire voices/theme/headlines into manifest loading**

In `loadManifestAndAudio`, replace this block:

```javascript
      audio.src = `latest.mp3?v=${encodeURIComponent(manifest.date)}`;
      setupMediaSession("Știri Tată", manifest.date);
      restorePositionOnce();

      if (Number.isFinite(manifest.duration_seconds)) {
        timeTotal.textContent = formatTime(manifest.duration_seconds);
      }
      renderChapters(manifest.chapters);
```

with:

```javascript
      // Set up voice picker if manifest has multiple voices.
      if (Array.isArray(manifest.voices) && manifest.voices.length > 1) {
        availableVoices = manifest.voices;
        const preferred = savedVoiceId();
        const match = availableVoices.find(v => v.id === preferred);
        const chosen = match || availableVoices[0];
        currentVoiceId = chosen.id;
        audio.src = buildVoiceSrc(chosen, manifest.date);
        voiceBtn.hidden = false;
        renderVoiceOptions();
      } else {
        audio.src = `latest.mp3?v=${encodeURIComponent(manifest.date)}`;
        voiceBtn.hidden = true;
        voicePanel.hidden = true;
      }

      setupMediaSession("Știri Tată", manifest.date);
      restorePositionOnce();
      applyWeatherTheme(manifest.weather_summary);
      renderHeadlines(manifest.headlines);

      if (Number.isFinite(manifest.duration_seconds)) {
        timeTotal.textContent = formatTime(manifest.duration_seconds);
      }
      renderChapters(manifest.chapters);
```

In the `catch` block of `loadManifestAndAudio`, after `dateEl.textContent = "Buletin din cache";`, add:

```javascript
      headlinesContainer.hidden = true;
      voiceBtn.hidden = true;
```

- [ ] **Step 5: Add the play-pulse class toggle**

In `setPlayIcon`, after the existing two lines, add:

```javascript
    if (isPlaying) playBtn.classList.add("play-btn--playing");
    else playBtn.classList.remove("play-btn--playing");
```

- [ ] **Step 6: Sanity-check JS syntax**

Run (in `/d/tmp/StiriTata`): `node --check pwa/app.js`
Expected: no output (valid). If `node` is unavailable, open the page (next task) and check the browser console for errors instead.

- [ ] **Step 7: Commit**

```bash
cd /d/tmp/StiriTata
git add pwa/app.js
git commit -m "Wire voice picker, speed, weather theme, headlines in PWA"
```

---

## Task 10: Manual verification

**Files:** none (verification only)

- [ ] **Step 1: Generate a bulletin with all three voices**

Ensure `.env` has `OPENAI_API_KEY` and `OPENWEATHER_API_KEY`, and the Piper model is present (`bash scripts/download_voice.sh`).

Run (in `/d/tmp/StiriTata`): `python -m generator.main --voices alina,mihai,emil --public-dir public`

Expected: `public/latest-alina.mp3`, `public/latest-mihai.mp3`, `public/latest-emil.mp3`, a `public/latest.mp3` (copy of the first success = Alina), and `public/latest.json` containing `voices` (3 entries), `headlines`, `weather_summary`, and `chapters`.

- [ ] **Step 2: Inspect the manifest**

Run (in `/d/tmp/StiriTata`): `python -c "import json;m=json.load(open('public/latest.json'));print('voices',[v['id'] for v in m.get('voices',[])]);print('has headlines',bool(m.get('headlines')));print('weather',m.get('weather_summary'));print('chapters',len(m.get('chapters',[])))"`
Expected: voices `['alina','mihai','emil']`, has headlines True, a weather string, chapters > 0.

- [ ] **Step 3: Serve the PWA and test in a browser**

Run (in `/d/tmp/StiriTata`): `python -m http.server 8765 --directory public &` then also serve the pwa shell, OR copy `pwa/*` next to `public/` as the daily workflow does. Simplest local check: `cd pwa && python -m http.server 8770` after copying `public/latest.*` into `pwa/`. Open `http://localhost:8770`.

Verify in the browser:
- 🎙 voice button appears; panel shows Alina (👩) active by default, plus Mihai/Emil (👨).
- Switching voice swaps audio and resumes near the same position.
- Speed button cycles 1× → 1.25× → 1.5× → 2× and changes playback rate.
- "În ediția de azi:" headlines list renders.
- Background theme reflects the weather (e.g. blue-ish on rain).
- Chapter buttons still jump to sections; seek ⏪30/30⏩ and resume hint still work.

- [ ] **Step 4: Final full test run**

Run (in `/d/tmp/StiriTata`): `python -m pytest -v`
Expected: all PASS.

---

## Self-Review Notes (author checklist — already verified)

- **Spec coverage:** edge-tts dep (T1), voice registry incl. female Alina (T2), romanization (T3), manifest voices/headlines/weather (T4), multi-voice default Alina + kept chapters/Reșița weather (T5), workflow env (T6), PWA picker/speed/theme/headlines + kept chapters/seek/resume (T7–T9), manual checks (T10). `pronunciation.py` intentionally excluded.
- **Type consistency:** `synthesize_voice`, `VOICE_BY_ID`, `_resolve_voices`, `build_manifest(..., voices=)`, manifest keys (`voices`/`headlines`/`weather_summary`/`chapters`) used consistently across backend tasks and frontend (`manifest.voices`, `manifest.headlines`, `manifest.weather_summary`). localStorage key `stiritata:voice` matches the existing `stiritata:` prefix.
