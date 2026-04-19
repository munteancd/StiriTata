from datetime import datetime
from typing import Any, Dict


def build_manifest(
    *,
    date: datetime,
    duration_seconds: float,
    audio_url: str,
    generated_at: datetime,
) -> Dict[str, Any]:
    return {
        "date": date.strftime("%Y-%m-%d"),
        "duration_seconds": duration_seconds,
        "audio_url": audio_url,
        "generated_at": generated_at.isoformat(),
    }
