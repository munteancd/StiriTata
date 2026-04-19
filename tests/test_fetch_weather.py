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
