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


def test_manifest_includes_chapters_when_provided():
    date = datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc)
    chapters = [{"key": "meteo", "title": "Meteo", "start_seconds": 0}]
    manifest = build_manifest(
        date=date,
        duration_seconds=900.0,
        audio_url="latest.mp3",
        generated_at=datetime(2026, 4, 19, 6, 3, tzinfo=timezone.utc),
        chapters=chapters,
    )
    assert manifest["chapters"] == chapters


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
