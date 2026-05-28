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
        voices=generated_voice_infos,
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
