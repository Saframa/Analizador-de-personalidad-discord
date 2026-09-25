"""
Tests unitarios para el Módulo TTS y Clonación de Voz Zero-Shot (Fase 5).
"""

import os
import tempfile
import pytest
import soundfile as sf

from core.tts.cloner import MockVoiceCloner, get_voice_cloner, release_tts_gpu_memory
from core.tts.normalizer import chunk_text_by_sentences, normalize_text_for_tts
from core.tts.player import play_audio_file


def test_normalize_text_rioplatense():
    """Valida la limpieza fonética, eliminación de emojis y expansión de modismos rioplatenses."""
    raw = "Boooo, mirá que xq me decís eso? 😂🚀 Dale porfa, dnd quedó el 50% de las cosas? Siiii, taaa!"
    normalized = normalize_text_for_tts(raw)

    # Modismos con vocales estiradas
    assert "boooo" not in normalized.lower()
    assert "bo" in normalized.lower()
    assert "ta" in normalized.lower()
    assert "sí" in normalized.lower()

    # Abreviaciones
    assert "porque" in normalized.lower()
    assert "por favor" in normalized.lower()
    assert "de nada" in normalized.lower()
    assert "por ciento" in normalized.lower()

    # Emojis eliminados
    assert "😂" not in normalized
    assert "🚀" not in normalized


def test_normalize_text_voseo_and_prosody():
    """Valida la acentuación de voseo, suavizado de risas y pausas prosódicas."""
    raw = "che tenes que venir, para un poco que mira que esta salado y estas loco jajajajajaja dale bo"
    normalized = normalize_text_for_tts(raw)

    # Acentuación forzada de voseo y verbos rioplatenses
    assert "tenés" in normalized
    assert "pará un poco" in normalized
    assert "mirá que" in normalized
    assert "está salado" in normalized
    assert "estás" in normalized

    # Suavizado de risas continuas
    assert "jajajajajaja" not in normalized
    assert "jaja jaja" in normalized

    # Pausa prosódica antes de bo terminal
    assert "dale, bo." in normalized


def test_chunk_text_by_sentences():
    """Verifica que el texto se divida adecuadamente para mantener la prosodia."""
    text = "Hola bo. ¿Cómo andás? Mirá que esto está flama! Todo bien por suerte."
    chunks = chunk_text_by_sentences(text, max_words_per_chunk=10)

    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk.split()) <= 10

    # Texto vacío
    assert chunk_text_by_sentences("") == []


def test_mock_voice_cloner_generates_valid_24khz_audio():
    """Verifica que el clonador Mock genere audio en formato PCM 24kHz mono."""
    cloner = MockVoiceCloner(sample_rate=24000)

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_wav = os.path.join(tmp_dir, "test_output.wav")
        res = cloner.clone_speech(
            target_text="Bo, mirá que esto quedó flama.",
            reference_audio_path="dummy.wav",
            output_path=out_wav,
        )

        assert os.path.exists(res)
        info = sf.info(res)
        assert info.samplerate == 24000
        assert info.channels == 1
        assert info.subtype == "PCM_16"
        assert info.duration > 0.3


def test_voice_cloner_clone_for_user_validation():
    """Verifica que clone_for_user valide la existencia de las muestras curadas."""
    cloner = MockVoiceCloner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with pytest.raises(FileNotFoundError, match="No se encontró la muestra"):
            cloner.clone_for_user("usuario_inexistente", "hola", tmp_dir)


def test_vram_release_safety():
    """Verifica que la rutina de liberación de memoria GPU se ejecute sin excepciones."""
    release_tts_gpu_memory(model=None)


def test_play_audio_nonexistent():
    """Verifica que el reproductor maneje rutas inexistentes de forma segura."""
    assert play_audio_file("ruta/falsa/inexistente.wav") is False


def test_get_voice_cloner_mock():
    """Verifica que la factory entregue la instancia adecuada con mock=True."""
    cloner = get_voice_cloner(mock=True)
    assert isinstance(cloner, MockVoiceCloner)
