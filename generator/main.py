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
