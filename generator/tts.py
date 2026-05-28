import asyncio
import concurrent.futures
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Piper (offline, local model)
# ---------------------------------------------------------------------------

@dataclass
class PiperConfig:
    voice_id: str = "ro_RO-mihai-medium"
    voice_dir: Path = field(default_factory=lambda: Path("generator/voices"))
    piper_binary: str = "piper"
    ffmpeg_binary: str = "ffmpeg"


def _ffprobe_duration_seconds(mp3_path: Path, ffmpeg_binary: str) -> float:
    """Extract duration from MP3 using ffmpeg stderr output."""
    try:
        cmd = [ffmpeg_binary, "-i", str(mp3_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        import re
        match = re.search(r"Duration:\s+(\d+):(\d+):(\d+\.\d+)", proc.stderr)
        if match:
            hours, minutes, seconds = match.groups()
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except Exception as exc:
        log.warning("failed to extract duration for %s: %s", mp3_path, exc)
    return 0.0


def synthesize(*, text: str, out_mp3: Path, config: PiperConfig) -> float:
    model_path = config.voice_dir / f"{config.voice_id}.onnx"
    model_json = config.voice_dir / f"{config.voice_id}.onnx.json"
    if not model_path.exists() or not model_json.exists():
        raise FileNotFoundError(
            f"Piper voice model not found at {model_path}. "
            "Run scripts/download_voice.sh or pass voice_dir."
        )

    out_mp3.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = Path(tmpdir) / "out.wav"

        piper_cmd = [
            config.piper_binary,
            "--model", str(model_path),
            "--output_file", str(wav_path),
        ]
        log.info("running piper: %s", piper_cmd)
        piper = subprocess.run(
            piper_cmd,
            input=text.encode("utf-8"),
            capture_output=True,
            check=False,
        )
        if piper.returncode != 0:
            raise RuntimeError(
                f"piper failed (rc={piper.returncode}): {piper.stderr.decode(errors='replace')}"
            )

        ffmpeg_cmd = [
            config.ffmpeg_binary,
            "-y",
            "-i", str(wav_path),
            "-codec:a", "libmp3lame",
            "-b:a", "96k",
            str(out_mp3),
        ]
        log.info("running ffmpeg: %s", ffmpeg_cmd)
        ff = subprocess.run(ffmpeg_cmd, capture_output=True, check=False)
        if ff.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed (rc={ff.returncode}): {ff.stderr.decode(errors='replace')}"
            )

    return _ffprobe_duration_seconds(out_mp3, config.ffmpeg_binary)


# ---------------------------------------------------------------------------
# Edge TTS (Microsoft neural voices, free, requires internet at generation)
# ---------------------------------------------------------------------------

@dataclass
class EdgeTTSConfig:
    # Romanian neural voices: ro-RO-AlinaNeural (female), ro-RO-EmilNeural (male)
    voice: str = "ro-RO-AlinaNeural"
    rate: str = "+0%"    # e.g. "+10%" to speed up slightly
    pitch: str = "+0Hz"
    ffmpeg_binary: str = "ffmpeg"


async def _synthesize_edge_async(
    *, text: str, out_mp3: Path, config: EdgeTTSConfig
) -> float:
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError(
            "edge-tts is not installed. Run: pip install edge-tts"
        ) from exc

    out_mp3.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_mp3 = Path(tmpdir) / "raw.mp3"

        communicate = edge_tts.Communicate(
            text,
            voice=config.voice,
            rate=config.rate,
            pitch=config.pitch,
        )
        log.info("edge-tts: generating with voice=%s", config.voice)
        await communicate.save(str(raw_mp3))

        # Re-encode with ffmpeg for consistent bitrate / metadata.
        ffmpeg_cmd = [
            config.ffmpeg_binary,
            "-y",
            "-i", str(raw_mp3),
            "-codec:a", "libmp3lame",
            "-b:a", "96k",
            str(out_mp3),
        ]
        ff = subprocess.run(ffmpeg_cmd, capture_output=True, check=False)
        if ff.returncode != 0:
            raise RuntimeError(
                f"ffmpeg re-encode failed (rc={ff.returncode}): "
                f"{ff.stderr.decode(errors='replace')}"
            )

    return _ffprobe_duration_seconds(out_mp3, config.ffmpeg_binary)


def synthesize_edge(*, text: str, out_mp3: Path, config: EdgeTTSConfig) -> float:
    """Synchronous wrapper around the async edge-tts call.

    Runs in a fresh thread so it never conflicts with an already-running
    event loop (e.g. the one started by asyncio.run(run_pipeline(...))).
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            asyncio.run,
            _synthesize_edge_async(text=text, out_mp3=out_mp3, config=config),
        )
        return future.result()


# ---------------------------------------------------------------------------
# Unified voice registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VoiceSpec:
    """A named TTS voice that the pipeline can generate audio for."""
    id: str          # short slug used in filenames, e.g. "mihai", "alina"
    label: str       # display name shown in the UI
    gender: str      # "male" | "female"
    backend: str     # "piper" | "edge"
    config: Union[PiperConfig, EdgeTTSConfig]


# Built-in voices — subset is enabled per-run via sources.yaml or env config.
AVAILABLE_VOICES: list[VoiceSpec] = [
    VoiceSpec(
        id="mihai",
        label="Mihai",
        gender="male",
        backend="piper",
        config=PiperConfig(voice_id="ro_RO-mihai-medium"),
    ),
    VoiceSpec(
        id="alina",
        label="Alina",
        gender="female",
        backend="edge",
        config=EdgeTTSConfig(voice="ro-RO-AlinaNeural"),
    ),
    VoiceSpec(
        id="emil",
        label="Emil",
        gender="male",
        backend="edge",
        config=EdgeTTSConfig(voice="ro-RO-EmilNeural"),
    ),
]

VOICE_BY_ID: dict[str, VoiceSpec] = {v.id: v for v in AVAILABLE_VOICES}


def synthesize_voice(*, text: str, out_mp3: Path, voice: VoiceSpec) -> float:
    """Generate an MP3 for the given voice spec. Returns duration in seconds.

    Piper reads everything with raw Romanian phonetics, so we apply the
    romanize_for_tts() substitution table before synthesis.
    Edge TTS is a neural voice that handles foreign words natively, so it
    receives the original text unchanged.
    """
    if voice.backend == "piper":
        from .text_utils import romanize_for_tts
        assert isinstance(voice.config, PiperConfig)
        return synthesize(text=romanize_for_tts(text), out_mp3=out_mp3, config=voice.config)
    elif voice.backend == "edge":
        from .text_utils import romanize_for_edge_tts
        assert isinstance(voice.config, EdgeTTSConfig)
        return synthesize_edge(text=romanize_for_edge_tts(text), out_mp3=out_mp3, config=voice.config)
    else:
        raise ValueError(f"Unknown TTS backend: {voice.backend!r}")
