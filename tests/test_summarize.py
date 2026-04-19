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
