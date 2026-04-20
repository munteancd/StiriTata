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
