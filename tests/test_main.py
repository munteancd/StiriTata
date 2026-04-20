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
         patch("generator.main.fetch_history", AsyncMock(return_value=None)), \
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
         patch("generator.main.fetch_weather", AsyncMock(return_value=_wr())), \
         patch("generator.main.fetch_history", AsyncMock(return_value=None)):
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
         patch("generator.main.fetch_history", AsyncMock(return_value=None)), \
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
