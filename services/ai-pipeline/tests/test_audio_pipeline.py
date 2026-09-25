"""
Test Suite: Pipeline de Audio, Silero VAD y Voice Curator (Fase 2)
Verifica los componentes de procesamiento de audio, detección de actividad vocal,
normalización LUFS y cumplimiento estricto del Contrato B.
"""

import json
import os
import sys
import numpy as np
import pytest
import soundfile as sf
import jsonschema

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.curator.voice_curator import VoiceCurator
from core.vad.silero import SileroVADDetector
from core.contracts.models import SessionTranscript, Utterance
from datetime import datetime, timezone

DOCS_SPECS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "docs", "specs"))


@pytest.fixture
def temp_audio_file(tmp_path):
    """Crea un archivo WAV sintético temporal de 48 kHz mono de 3 segundos."""
    sr = 48000
    duration = 3.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # Tono audible de 440 Hz
    audio = 0.5 * np.sin(2 * np.pi * 440 * t)
    wav_path = str(tmp_path / "test_tone.wav")
    sf.write(wav_path, audio.astype(np.float32), sr, subtype="PCM_16")
    return wav_path


@pytest.fixture
def empty_audio_file(tmp_path):
    """Crea un archivo WAV vacío de 44 bytes."""
    wav_path = str(tmp_path / "empty.wav")
    with open(wav_path, "wb") as f:
        # Encabezado WAV mínimo sin datos
        f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
    return wav_path


def test_silero_vad_empty_audio(empty_audio_file):
    detector = SileroVADDetector()
    intervals = detector.detect_speech_intervals(empty_audio_file)
    assert intervals == []


def test_voice_curator_normalization(tmp_path):
    curator = VoiceCurator(target_sample_rate=24000, target_lufs=-18.0)
    # Generar audio con volumen muy alto
    sr = 24000
    t = np.linspace(0, 4.0, int(sr * 4.0), endpoint=False)
    audio = 0.9 * np.sin(2 * np.pi * 440 * t)

    normalized = curator.normalize_loudness(audio, sr)
    assert len(normalized) == len(audio)
    # El pico máximo no debe sobrepasar 0.95 (anti-clipping)
    assert np.max(np.abs(normalized)) <= 0.95


def test_voice_curator_curate_sample(temp_audio_file, tmp_path):
    curator = VoiceCurator(target_sample_rate=24000, target_lufs=-18.0)
    output_dir = str(tmp_path / "clean_samples")

    clean_intervals = [(0.5, 2.5)]
    result = curator.curate_user_sample(
        user_id="user_12345",
        audio_path=temp_audio_file,
        clean_intervals=clean_intervals,
        output_dir=output_dir,
        min_required_duration=1.0,
    )

    assert result is not None
    assert result["user_id"] == "user_12345"
    assert result["duration_seconds"] == 2.0
    assert os.path.exists(result["output_path"])

    # Verificar que el archivo generado sea legible y a 24000 Hz
    info = sf.info(result["output_path"])
    assert info.samplerate == 24000
    assert info.channels == 1


def test_session_transcript_conforms_to_schema():
    """Verifica que el objeto SessionTranscript generado cumpla con transcript.schema.json."""
    schema_path = os.path.join(DOCS_SPECS_DIR, "transcript.schema.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    transcript = SessionTranscript(
        version="1.0.0",
        session_id="2026-09-25_00-00-18",
        processed_at=datetime.now(timezone.utc),
        model="faster-whisper/medium",
        utterances=[
            Utterance(
                id=1,
                user_id="438796478035787780",
                username="saframa",
                start_time=1.45,
                end_time=3.80,
                duration=2.35,
                text="Bo, qué hacés che, todo bien?",
                confidence=0.985,
                overlapping_speakers=[],
            ),
            Utterance(
                id=2,
                user_id="665372153964920858",
                username="tinixx8917",
                start_time=4.10,
                end_time=6.20,
                duration=2.10,
                text="Ta salado esto, pará un cacho.",
                confidence=0.942,
                overlapping_speakers=[],
            ),
        ],
    )

    data = json.loads(transcript.model_dump_json())
    jsonschema.validate(instance=data, schema=schema)
