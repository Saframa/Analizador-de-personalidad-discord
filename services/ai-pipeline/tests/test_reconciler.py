import os
import wave
import pytest
from datetime import datetime, timezone

from core.session_reconciler import reconcile_orphan_sessions, is_audio_file_empty
from core.contracts.models import SessionMetadata, SessionTranscript


def test_is_audio_file_empty(tmp_path):
    # Archivo inexistente
    assert is_audio_file_empty(str(tmp_path / "nonexistent.wav")) is True

    # Archivo WAV vacío (0 frames)
    wav_path = tmp_path / "empty.wav"
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
    assert is_audio_file_empty(str(wav_path)) is True

    # Archivo WAV con frames reales
    real_wav = tmp_path / "real.wav"
    with wave.open(str(real_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(b"\x00\x00" * 4800)  # 0.1s de audio
    assert is_audio_file_empty(str(real_wav)) is False

    # Archivo OGG de cabecera vacía (<= 107 bytes)
    empty_ogg = tmp_path / "empty.ogg"
    empty_ogg.write_bytes(b"OggS" + b"\x00" * 100)
    assert is_audio_file_empty(str(empty_ogg)) is True

    # Archivo OGG con datos (> 107 bytes)
    real_ogg = tmp_path / "real.ogg"
    real_ogg.write_bytes(b"OggS" + b"\x00" * 500)
    assert is_audio_file_empty(str(real_ogg)) is False


def test_reconcile_orphan_sessions_empty_aborted(tmp_path):
    storage_dir = tmp_path / "storage"
    raw_dir = storage_dir / "raw_sessions" / "2026-09-25_10-00-00"
    audio_dir = raw_dir / "audio"
    audio_dir.mkdir(parents=True)

    # Crear audio vacío de prueba
    empty_ogg = audio_dir / "438796478035787780.ogg"
    empty_ogg.write_bytes(b"OggS" + b"\x00" * 103)

    result = reconcile_orphan_sessions(str(storage_dir))
    assert result["reconciled_empty"] == 1

    # Verificar que se crearon los contratos formales
    meta_file = raw_dir / "session_metadata.json"
    transcript_file = raw_dir / "transcript.json"
    purged_file = audio_dir / ".purged"

    assert meta_file.exists()
    assert transcript_file.exists()
    assert purged_file.exists()

    meta = SessionMetadata.model_validate_json(meta_file.read_text(encoding="utf-8"))
    assert meta.duration_seconds == 0.0
    assert len(meta.participants) >= 1

    transcript = SessionTranscript.model_validate_json(transcript_file.read_text(encoding="utf-8"))
    assert len(transcript.utterances) == 0


def test_reconcile_orphan_sessions_active_interrupted(tmp_path):
    storage_dir = tmp_path / "storage"
    raw_dir = storage_dir / "raw_sessions" / "2026-09-25_12-00-00"
    audio_dir = raw_dir / "audio"
    audio_dir.mkdir(parents=True)

    # Crear audio con voz real
    real_wav = audio_dir / "438796478035787780.wav"
    with wave.open(str(real_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(b"\x01\x00" * 96000)  # 2.0s de audio

    result = reconcile_orphan_sessions(str(storage_dir))
    assert result["reconstructed_active"] == 1

    meta_file = raw_dir / "session_metadata.json"
    assert meta_file.exists()

    meta = SessionMetadata.model_validate_json(meta_file.read_text(encoding="utf-8"))
    assert meta.duration_seconds >= 1.0
    assert "438796478035787780" in meta.audio_files

    # transcript.json no debe existir aún para permitir que Whisper lo procese
    assert not (raw_dir / "transcript.json").exists()
