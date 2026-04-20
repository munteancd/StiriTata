import logging
import re
import time
from datetime import datetime
from typing import Any, List, Optional

from .models import NewsItem, WeatherReport
from .prompt import (
    OUTRO,
    SECTIONS,
    Section,
    build_intro,
    build_section_system_prompt,
    build_section_user_prompt,
)

log = logging.getLogger(__name__)

# Fallback text when a section's API call fails permanently.
# Keeps the bulletin flowing even if one segment errors out.
_SECTION_FALLBACK = (
    "Din păcate, pentru această secțiune nu avem informații disponibile astăzi. "
    "Trecem mai departe."
)

# gpt-4o loves to close every segment with a filler wrap-up
# ("Acestea au fost...", "În concluzie, ..."). We ban these in the prompt
# but the model cheats anyway — so we also strip the final paragraph
# post-hoc if it matches one of these tell-tale openings.
# Each pattern matches the START of a paragraph (case-insensitive).
_WRAP_UP_PATTERNS = [
    r"^acestea\s+au\s+fost\b",
    r"^acestea\s+sunt\b",
    r"^aceasta\s+a\s+fost\b",
    r"^acesta\s+a\s+fost\b",
    r"^în\s+concluzie\b",
    r"^în\s+rezumat\b",
    r"^în\s+final,\s+(săptămâna|ziua|această|fotbalul|sportul)",
    # "Aceste [anything] (subliniază|arată|reflectă|...)" — generalizes the
    # filler "Aceste rezultate/evenimente/premii subliniază performanțele..."
    r"^aceste\s+\S+\s+(subliniază|arată|reflectă|reprezintă|demonstrează|evidențiază|pun|marchează)\b",
    r"^aceasta\s+(subliniază|arată|reflectă|demonstrează|evidențiază)\b",
    r"^rămâne\s+de\s+văzut\b",
    r"^rămânem\s+atenți\b",
    r"^vom\s+urmări\b",
    r"^așteptăm\s+cu\s+interes\b",
]
_WRAP_UP_REGEX = re.compile(
    "(" + "|".join(_WRAP_UP_PATTERNS) + ")",
    re.IGNORECASE,
)


def _strip_trailing_wrap_up(text: str, *, section_key: str) -> str:
    """Remove trailing filler wrap-up, at paragraph OR sentence granularity.

    The model sometimes emits the wrap-up as its own paragraph
    („…\\n\\nAcestea au fost…") and sometimes glues it onto the last
    news item („…remarcabile în acest sezon. În concluzie, fotbalul…").
    We strip both shapes.

    Meteo is exempt — its closing practical tip (umbrella, warm clothes)
    is allowed and doesn't match these patterns anyway.
    """
    if section_key == "meteo":
        return text

    # 1. Paragraph-level strip
    paragraphs = text.split("\n\n") if "\n\n" in text else [text]
    while len(paragraphs) > 1 and _WRAP_UP_REGEX.match(paragraphs[-1].lstrip()):
        log.info("stripping wrap-up paragraph from %s: %r",
                 section_key, paragraphs[-1][:80])
        paragraphs.pop()

    # 2. Sentence-level strip on the final paragraph (inline wrap-up).
    # Split on sentence terminators followed by whitespace.
    last = paragraphs[-1]
    sentences = re.split(r"(?<=[.!?])\s+", last)
    while len(sentences) > 1 and _WRAP_UP_REGEX.match(sentences[-1].lstrip()):
        log.info("stripping wrap-up sentence from %s: %r",
                 section_key, sentences[-1][:80])
        sentences.pop()
    paragraphs[-1] = " ".join(sentences).rstrip()

    return "\n\n".join(paragraphs).rstrip()


def _call_section(
    *,
    section: Section,
    items: List[NewsItem],
    weather: Optional[WeatherReport],
    bulletin_date: datetime,
    client: Any,
    model: str,
    max_retries: int,
    retry_sleep: float,
) -> str:
    """Generate the text for a single bulletin section via one OpenAI call."""
    system_prompt = build_section_system_prompt(section)
    user_prompt = build_section_user_prompt(
        section=section,
        items=items,
        weather=weather,
        bulletin_date=bulletin_date,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # Budget ~2x target words in tokens. Romanian averages ~1.5 tokens/word
    # with gpt-4o tokenizer, so 2x gives comfortable headroom.
    max_tokens = max(800, section.target_words * 3)

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.4,
                max_tokens=max_tokens,
            )
            text = response.choices[0].message.content.strip()
            text = _strip_trailing_wrap_up(text, section_key=section.key)
            word_count = len(text.split())
            log.info(
                "section %s: %d words (target %d, min %d)",
                section.key, word_count, section.target_words, section.min_words,
            )
            return text
        except Exception as exc:
            last_exc = exc
            log.warning(
                "section %s attempt %d failed: %s",
                section.key, attempt + 1, exc,
            )
            if attempt < max_retries:
                time.sleep(retry_sleep * (2**attempt))

    assert last_exc is not None
    log.error(
        "section %s permanently failed after %d attempts, using fallback",
        section.key, max_retries + 1,
    )
    return _SECTION_FALLBACK


def summarize(
    *,
    items: List[NewsItem],
    weather: Optional[WeatherReport],
    bulletin_date: datetime,
    client: Any,
    model: str = "gpt-4o",
    max_retries: int = 2,
    retry_sleep: float = 2.0,
    max_section_failures: int = 2,
) -> str:
    """Generate the full bulletin text by calling the API once per section.

    The per-section architecture gives us reliable control over total length:
    each call has a focused scope and a narrow word-count target, so the
    model actually hits it (unlike single-call mode where gpt-4o ignored
    length directives for the long tail).

    Intro and outro are hardcoded (no API call needed — they're deterministic).
    If a section's API call permanently fails, we substitute a fallback line
    and continue — but if *too many* sections fall back (default >2 out of 6),
    we RAISE instead of returning a degraded 30-second bulletin. The caller
    (main.py) catches the exception and keeps yesterday's MP3 live, which is
    a far better experience for the listener than a broken short file.
    """
    parts: List[str] = [build_intro(bulletin_date)]
    failed_sections = 0

    for section in SECTIONS:
        text = _call_section(
            section=section,
            items=items,
            weather=weather,
            bulletin_date=bulletin_date,
            client=client,
            model=model,
            max_retries=max_retries,
            retry_sleep=retry_sleep,
        )
        if text == _SECTION_FALLBACK:
            failed_sections += 1
        parts.append(text)

    if failed_sections > max_section_failures:
        raise RuntimeError(
            f"too many sections failed ({failed_sections}/{len(SECTIONS)}); "
            f"refusing to produce degraded bulletin — previous MP3 will be preserved"
        )

    parts.append(OUTRO)

    total_words = sum(len(p.split()) for p in parts)
    log.info(
        "bulletin complete: %d sections ok, %d failed, %d words total",
        len(SECTIONS) - failed_sections, failed_sections, total_words,
    )

    return "\n\n".join(parts)
