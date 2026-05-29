from unittest.mock import patch

from generator.tts import (
    VOICE_BY_ID,
    AVAILABLE_VOICES,
    EdgeTTSConfig,
    synthesize_voice,
)


def test_registry_has_female_alina_voice():
    assert "alina" in VOICE_BY_ID
    alina = VOICE_BY_ID["alina"]
    assert alina.gender == "female"
    assert alina.backend == "edge"
    assert isinstance(alina.config, EdgeTTSConfig)
    assert alina.config.voice == "ro-RO-AlinaNeural"


def test_registry_exposes_two_edge_voices():
    ids = {v.id for v in AVAILABLE_VOICES}
    assert ids == {"alina", "emil"}
    assert all(v.backend == "edge" for v in AVAILABLE_VOICES)


def test_synthesize_voice_dispatches_to_edge_for_alina(tmp_path):
    out = tmp_path / "latest-alina.mp3"
    with patch("generator.tts.synthesize_edge", return_value=12.3) as edge_mock:
        dur = synthesize_voice(text="Salut", out_mp3=out, voice=VOICE_BY_ID["alina"])
    assert dur == 12.3
    assert edge_mock.called


def test_synthesize_voice_passes_text_through_unchanged(tmp_path):
    out = tmp_path / "latest.mp3"
    original = "Manchester City a câștigat"
    with patch("generator.tts.synthesize_edge", return_value=1.0) as edge_mock:
        synthesize_voice(text=original, out_mp3=out, voice=VOICE_BY_ID["alina"])
    assert edge_mock.call_args.kwargs["text"] == original
