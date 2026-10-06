"""
Tests unitarios y de integración para VoiceStudioCloner y su integración en el pipeline.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch
import pytest
import soundfile as sf

from core.tts.cloner import (
    BaseVoiceCloner,
    MockVoiceCloner,
    VoiceStudioCloner,
    get_voice_cloner,
)


def test_voicestudio_cloner_init():
    """Valida la inicialización de VoiceStudioCloner con valores por defecto."""
    cloner = VoiceStudioCloner(api_url="http://127.0.0.1:3900")
    assert cloner.api_url == "http://127.0.0.1:3900"
    assert cloner.model == "omnivoice"
    assert isinstance(cloner, BaseVoiceCloner)


def test_voicestudio_is_available_false_when_offline():
    """Valida que is_available() retorne False si el puerto no está levantado."""
    cloner = VoiceStudioCloner(api_url="http://127.0.0.1:59999")  # Puerto no existente
    assert cloner.is_available() is False


def test_voicestudio_is_available_true_when_online():
    """Valida que is_available() retorne True si el endpoint /v1/models responde 200."""
    cloner = VoiceStudioCloner(api_url="http://127.0.0.1:3900")
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("requests.get", return_value=mock_resp):
        assert cloner.is_available() is True


def test_voicestudio_fallback_when_offline():
    """Valida que si VoiceStudio no está activo, use transparentemente el fallback cloner."""
    mock_fallback = MockVoiceCloner(sample_rate=24000)
    cloner = VoiceStudioCloner(
        api_url="http://127.0.0.1:59999",
        fallback_cloner=mock_fallback,
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_wav = os.path.join(tmp_dir, "fallback_test.wav")
        ref_wav = os.path.join(tmp_dir, "ref_dummy.wav")
        # Generar ref dummy
        sf.write(ref_wav, [0.0] * 1000, 24000)

        res = cloner.clone_speech(
            target_text="Bo, esto es una prueba con fallback.",
            reference_audio_path=ref_wav,
            output_path=out_wav,
        )

        assert os.path.exists(res)
        info = sf.info(res)
        assert info.samplerate == 24000
        assert info.channels == 1


def test_voicestudio_clone_speech_success():
    """Valida el flujo exitoso de petición a VoiceStudio API."""
    cloner = VoiceStudioCloner(api_url="http://127.0.0.1:3900")

    mock_models_resp = MagicMock()
    mock_models_resp.status_code = 200

    mock_profiles_resp = MagicMock()
    mock_profiles_resp.status_code = 200
    mock_profiles_resp.json.return_value = [{"id": "prof_123", "name": "user_samples"}]

    mock_speech_resp = MagicMock()
    mock_speech_resp.status_code = 200
    # Generar bytes de un WAV válido
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_name = f.name
        sf.write(tmp_name, [0.1] * 2400, 24000)
    with open(tmp_name, "rb") as f:
        mock_speech_resp.content = f.read()
    os.remove(tmp_name)

    def mock_get(url, *args, **kwargs):
        if "models" in url:
            return mock_models_resp
        if "profiles" in url:
            return mock_profiles_resp
        return MagicMock(status_code=404)

    with patch("requests.get", side_effect=mock_get), \
         patch("requests.post", return_value=mock_speech_resp):

        with tempfile.TemporaryDirectory() as tmp_dir:
            ref_wav = os.path.join(tmp_dir, "samples", "ref.wav")
            os.makedirs(os.path.dirname(ref_wav), exist_ok=True)
            sf.write(ref_wav, [0.0] * 1000, 24000)

            out_wav = os.path.join(tmp_dir, "out_vs.wav")
            res = cloner.clone_speech(
                target_text="Buenas tardes che, todo bien?",
                reference_audio_path=ref_wav,
                output_path=out_wav,
            )

            assert os.path.exists(res)
            assert os.path.getsize(res) > 0


def test_get_voice_cloner_env_voicestudio(monkeypatch):
    """Valida que get_voice_cloner instancie VoiceStudioCloner cuando TTS_ENGINE=voicestudio."""
    monkeypatch.setenv("TTS_ENGINE", "voicestudio")
    cloner = get_voice_cloner()
    assert isinstance(cloner, VoiceStudioCloner)
    assert cloner.fallback_cloner is not None
