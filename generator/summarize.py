import logging
import time
from datetime import datetime
from typing import Any, List, Optional

from .models import NewsItem, WeatherReport
from .prompt import SYSTEM_PROMPT, build_user_prompt

log = logging.getLogger(__name__)


def summarize(
    *,
    items: List[NewsItem],
    weather: Optional[WeatherReport],
    bulletin_date: datetime,
    client: Any,
    model: str = "gpt-4o-mini",
    max_retries: int = 2,
    retry_sleep: float = 2.0,
) -> str:
    user_prompt = build_user_prompt(
        items=items, weather=weather, bulletin_date=bulletin_date
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.4,
            )
            text = response.choices[0].message.content.strip()
            return text
        except Exception as exc:
            last_exc = exc
            log.warning("summarize attempt %d failed: %s", attempt + 1, exc)
            if attempt < max_retries:
                time.sleep(retry_sleep * (2**attempt))
    assert last_exc is not None
    raise last_exc
