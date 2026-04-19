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
