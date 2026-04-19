import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class PiperConfig:
    voice_id: str = "ro_RO-mihai-medium"
    voice_dir: Path = field(default_factory=lambda: Path("generator/voices"))
    piper_binary: str = "piper"
    ffmpeg_binary: str = "ffmpeg"


def _ffprobe_duration_seconds(mp3_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(mp3_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


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

    return _ffprobe_duration_seconds(out_mp3)
