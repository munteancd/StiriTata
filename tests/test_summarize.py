from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from generator.models import HistoryCandidates, HistoryItem, NewsItem, WeatherReport
from generator.prompt import (
    OUTRO,
    SECTIONS,
    SYSTEM_PROMPT,
    build_intro,
    build_section_user_prompt,
    build_user_prompt,
)
from generator.summarize import _strip_trailing_wrap_up, summarize


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


def test_summarize_calls_openai_per_section_and_concatenates():
    """summarize() makes one API call per section, stitches intro + sections + outro."""
    fake_client = MagicMock()
    # Return a unique string per call so we can verify concatenation order
    responses = iter([
        MagicMock(choices=[MagicMock(message=MagicMock(content=f"SECTION_{i}_TEXT"))])
        for i in range(len(SECTIONS))
    ])
    fake_client.chat.completions.create.side_effect = lambda **kw: next(responses)

    text = summarize(
        items=_sample_items(),
        weather=_sample_weather(),
        bulletin_date=datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc),
        client=fake_client,
        model="gpt-4o-mini",
        history=_sample_history(),
    )

    # One call per section
    assert fake_client.chat.completions.create.call_count == len(SECTIONS)

    # Bulletin contains hardcoded intro, all sections, and outro in order
    intro = build_intro(datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc))
    assert text.startswith(intro)
    assert text.endswith(OUTRO)
    for i in range(len(SECTIONS)):
        assert f"SECTION_{i}_TEXT" in text

    # Each call has system + user messages with the requested model
    for call in fake_client.chat.completions.create.call_args_list:
        kwargs = call.kwargs
        assert kwargs["model"] == "gpt-4o-mini"
        assert len(kwargs["messages"]) == 2
        assert kwargs["messages"][0]["role"] == "system"
        assert kwargs["messages"][1]["role"] == "user"


def test_summarize_raises_when_too_many_sections_fail():
    """If more than max_section_failures sections fall back, summarize RAISES.
    This is critical: we'd rather keep yesterday's bulletin than overwrite
    it with a degraded 30-second file full of 'no info available'.
    """
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="too many sections failed"):
        summarize(
            items=_sample_items(),
            weather=_sample_weather(),
            bulletin_date=datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc),
            client=fake_client,
            model="gpt-4o-mini",
            max_retries=2,
            retry_sleep=0.0,
            history=_sample_history(),
        )


def test_summarize_tolerates_a_couple_section_failures():
    """Up to max_section_failures (default 2) bad sections → bulletin still returned."""
    fake_client = MagicMock()

    # Craft: first 2 sections fail permanently (each hit 3 times = 6 calls),
    # remaining len(SECTIONS) - 2 sections succeed on first try.
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
    # len(SECTIONS) - 2 real sections present (2 used fallback)
    assert text.count("OK_SECTION") == len(SECTIONS) - 2
    # 2 fallback lines present
    assert "nu avem informații" in text.lower() or "trecem mai departe" in text.lower()


def test_strip_wrap_up_removes_acestea_au_fost():
    text = (
        "În Ucraina, șeful poliției a demisionat.\n\n"
        "Acestea au fost principalele știri din fotbalul românesc."
    )
    out = _strip_trailing_wrap_up(text, section_key="football_ro")
    assert "Acestea au fost" not in out
    assert "demisionat" in out


def test_strip_wrap_up_removes_in_concluzie():
    text = (
        "Bayern a câștigat cu patru la doi.\n\n"
        "În concluzie, săptămâna a fost plină de evenimente."
    )
    out = _strip_trailing_wrap_up(text, section_key="football_eu")
    assert "În concluzie" not in out


def test_strip_wrap_up_preserves_meteo_closing():
    """Meteo's practical closing tip must NOT be stripped."""
    text = (
        "Temperatura este de șapte grade.\n\n"
        "Luați o umbrelă, se anunță ploi pe parcursul zilei."
    )
    out = _strip_trailing_wrap_up(text, section_key="meteo")
    assert "umbrelă" in out


def test_strip_wrap_up_removes_aceste_premii_subliniaza():
    """The looser 'Aceste [noun] [verb]' pattern catches premii/distinctii/etc."""
    text = (
        "Frank Lampard a fost desemnat antrenorul sezonului. "
        "Aceste premii subliniază performanțele remarcabile ale celor doi."
    )
    out = _strip_trailing_wrap_up(text, section_key="football_eu")
    assert "subliniază" not in out
    assert "Lampard" in out


def test_strip_wrap_up_removes_inline_in_concluzie():
    """Model sometimes glues the wrap-up onto the last news sentence, no \\n\\n."""
    text = (
        "Frank Lampard de la Coventry a fost desemnat antrenorul sezonului. "
        "În concluzie, fotbalul european ne-a oferit meciuri spectaculoase."
    )
    out = _strip_trailing_wrap_up(text, section_key="football_eu")
    assert "În concluzie" not in out
    assert "Lampard" in out


def test_strip_wrap_up_leaves_real_news_alone():
    """Text without a trailing filler wrap-up is returned unchanged."""
    text = (
        "CSM Reșița a pierdut meciul cu unu la doi.\n\n"
        "Antrenorul a declarat că echipa nu merita să piardă."
    )
    out = _strip_trailing_wrap_up(text, section_key="local_politics")
    assert out == text


def test_summarize_retries_transient_failure_then_succeeds():
    """A section that fails twice then succeeds on the third try should still return real content."""
    fake_client = MagicMock()

    call_count = {"n": 0}

    def flaky(**kwargs):
        call_count["n"] += 1
        # Fail the first two calls overall, then succeed for every call after
        if call_count["n"] <= 2:
            raise RuntimeError("transient")
        return MagicMock(
            choices=[MagicMock(message=MagicMock(content="RECOVERED"))]
        )

    fake_client.chat.completions.create.side_effect = flaky

    text = summarize(
        items=_sample_items(),
        weather=_sample_weather(),
        bulletin_date=datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc),
        client=fake_client,
        model="gpt-4o-mini",
        max_retries=2,
        retry_sleep=0.0,
        history=_sample_history(),
    )

    # First section recovers after 2 retries; subsequent sections succeed on first try
    # Total calls: 3 (first section: 2 fails + 1 success) + (len(SECTIONS) - 1) successes
    assert fake_client.chat.completions.create.call_count == 3 + (len(SECTIONS) - 1)
    assert "RECOVERED" in text


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
