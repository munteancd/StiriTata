from datetime import datetime
from typing import Any, Dict, List, Optional


def build_manifest(
    *,
    date: datetime,
    duration_seconds: float,
    audio_url: str,
    generated_at: datetime,
    headlines: Optional[List[str]] = None,
    weather_summary: Optional[str] = None,
    chapters: Optional[List[Dict[str, Any]]] = None,
    voices: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    manifest: Dict[str, Any] = {
        "date": date.strftime("%Y-%m-%d"),
        "duration_seconds": duration_seconds,
        "audio_url": audio_url,
        "generated_at": generated_at.isoformat(),
    }
    if headlines:
        manifest["headlines"] = headlines
    if weather_summary:
        manifest["weather_summary"] = weather_summary
    if chapters:
        manifest["chapters"] = chapters
    if voices:
        manifest["voices"] = voices
    return manifest
