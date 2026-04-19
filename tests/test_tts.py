from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from generator.tts import synthesize, PiperConfig


def test_piper_config_default_voice_is_romanian():
    cfg = PiperConfig()
    assert cfg.voice_id.startswith("ro_RO-")


def test_synthesize_invokes_piper_and_ffmpeg(tmp_path: Path):
    text = "Bună dimineața, tată. Astăzi este duminică."
    out_mp3 = tmp_path / "latest.mp3"
    voice_dir = tmp_path / "voices"
    voice_dir.mkdir()
    # Create dummy voice files so existence check passes
    (voice_dir / "ro_RO-mihai-medium.onnx").write_bytes(b"fake")
    (voice_dir / "ro_RO-mihai-medium.onnx.json").write_bytes(b"{}")

    cfg = PiperConfig(voice_id="ro_RO-mihai-medium", voice_dir=voice_dir)

    # Simulate Piper writing a WAV, then ffmpeg producing an MP3.
    def fake_run(cmd, **kwargs):
        if "piper" in cmd[0].lower() or cmd[0].endswith("piper"):
            # Piper is told to write to `--output-raw` or `--output_file`; use output_file path
            # from the command to create a fake WAV.
            wav_path = Path(cmd[cmd.index("--output_file") + 1])
            wav_path.write_bytes(b"RIFF....WAVEfakeaudio")
        elif "ffmpeg" in cmd[0]:
            out_index = cmd.index("-y") + 1 if "-y" in cmd else -1
            # Output is last arg
            Path(cmd[-1]).write_bytes(b"ID3fakemp3")
        return MagicMock(returncode=0, stdout=b"", stderr=b"")

    with patch("generator.tts.subprocess.run", side_effect=fake_run) as run_mock, \
         patch("generator.tts._ffprobe_duration_seconds", return_value=42.5):
        duration = synthesize(text=text, out_mp3=out_mp3, config=cfg)

    assert out_mp3.exists()
    assert duration == 42.5
    # Piper must have been invoked with the voice model path.
    piper_call = run_mock.call_args_list[0]
    piper_cmd = piper_call.args[0]
    assert any("ro_RO-mihai-medium.onnx" in part for part in piper_cmd)


def test_synthesize_raises_if_voice_model_missing(tmp_path: Path):
    cfg = PiperConfig(voice_id="ro_RO-missing-medium", voice_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        synthesize(text="test", out_mp3=tmp_path / "out.mp3", config=cfg)
