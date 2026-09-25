"""
Test Suite: Motor de Perfilado Psicológico, Métricas y Síntesis Multisesión (Fase 3)
Verifica el cálculo de métricas conversacionales, la evaluación con citas de evidencia,
la síntesis continua incremental (N -> N+1) y la conformidad con user_profile.schema.json.
"""

import json
import os
import sys
from datetime import datetime, timezone
import pytest
import jsonschema

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.contracts.models import SessionTranscript, Utterance, UserProfile
from core.profiler.metrics import compute_user_metrics, compute_social_and_temporal_metrics
from core.profiler.gemini_analyzer import GeminiProfiler, GeminiSessionEvaluation
from core.profiler.profile_synthesizer import ProfileSynthesizer, running_avg

DOCS_SPECS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "docs", "specs"))


@pytest.fixture
def sample_transcript():
    return SessionTranscript(
        version="1.0.0",
        session_id="2026-09-25_00-00-18",
        processed_at=datetime.now(timezone.utc),
        model="faster-whisper/medium",
        utterances=[
            Utterance(
                id=1,
                user_id="user_marce",
                username="saframa",
                start_time=1.0,
                end_time=4.0,
                duration=3.0,
                text="Hola Kevin, te voy a clonar la voz, bo!",
                confidence=0.95,
                overlapping_speakers=["user_arbustin"],
            ),
            Utterance(
                id=2,
                user_id="user_arbustin",
                username="tinixx8917",
                start_time=3.5,
                end_time=5.5,
                duration=2.0,
                text="Ta salado esto, pará un poco.",
                confidence=0.92,
                overlapping_speakers=["user_marce"],
            ),
            Utterance(
                id=3,
                user_id="user_marce",
                username="saframa",
                start_time=6.0,
                end_time=10.0,
                duration=4.0,
                text="Dejá quieto, mirá que esto está dando flama posta.",
                confidence=0.98,
                overlapping_speakers=[],
            ),
        ],
    )


def test_compute_user_metrics(sample_transcript):
    metrics = compute_user_metrics(sample_transcript, "user_marce")
    assert metrics.user_id == "user_marce"
    assert metrics.turn_count == 2
    assert metrics.total_speaking_seconds == 7.0
    # Turn 1: 9 words, Turn 2: 9 words -> 18 words / 2 turns = 9.0
    assert metrics.avg_words_per_turn == 9.0
    # 1 of 2 turns had overlap -> 0.5
    assert metrics.interruption_ratio == 0.5
    assert metrics.cadence in ["rapido", "pausado", "irregular", "moderado"]


def test_compute_user_metrics_empty(sample_transcript):
    metrics = compute_user_metrics(sample_transcript, "user_ghost")
    assert metrics.turn_count == 0
    assert metrics.total_speaking_seconds == 0.0
    assert metrics.avg_words_per_turn == 0.0
    assert metrics.interruption_ratio == 0.0


def test_gemini_profiler_mock(sample_transcript):
    metrics = compute_user_metrics(sample_transcript, "user_marce")
    profiler = GeminiProfiler(mock=True)
    eval_res = profiler.analyze_user_session(
        transcript=sample_transcript,
        target_user_id="user_marce",
        target_username="saframa",
        metrics=metrics,
    )

    assert isinstance(eval_res, GeminiSessionEvaluation)
    assert 0.0 <= eval_res.openness_score <= 1.0
    assert 0.0 <= eval_res.extraversion_score <= 1.0
    assert len(eval_res.openness_evidence) >= 1
    assert len(eval_res.extraversion_evidence) >= 1
    assert eval_res.primary_role != ""
    assert eval_res.humor_type != ""


def test_profile_synthesizer_lifecycle(sample_transcript, tmp_path):
    synthesizer = ProfileSynthesizer(storage_dir=str(tmp_path))
    metrics = compute_user_metrics(sample_transcript, "user_marce")
    profiler = GeminiProfiler(mock=True)

    eval_1 = profiler.analyze_user_session(
        transcript=sample_transcript,
        target_user_id="user_marce",
        target_username="saframa",
        metrics=metrics,
    )

    # 1. Primera síntesis (N=1)
    profile_1 = synthesizer.synthesize_profile(
        user_id="user_marce",
        username="saframa",
        session_id="2026-09-25_00-00-18",
        session_metrics=metrics,
        evaluation=eval_1,
    )

    assert profile_1.total_sessions_analyzed == 1
    assert profile_1.total_speaking_seconds == 7.0
    assert profile_1.user_id == "user_marce"

    # Verificar cumplimiento con JSON Schema formal
    schema_path = os.path.join(DOCS_SPECS_DIR, "user_profile.schema.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    data_1 = json.loads(profile_1.model_dump_json())
    jsonschema.validate(instance=data_1, schema=schema)

    # 2. Segunda síntesis (N=2, actualización incremental multisesión)
    # Crear una segunda evaluación con score diferente para probar el promedio continuo
    eval_2 = eval_1.model_copy(
        update={
            "openness_score": 0.90,
            "extraversion_score": 0.80,
            "openness_evidence": ["Segunda sesión con evidencia nueva."],
        }
    )

    profile_2 = synthesizer.synthesize_profile(
        user_id="user_marce",
        username="saframa",
        session_id="2026-09-25_01-00-00",
        session_metrics=metrics,
        evaluation=eval_2,
    )

    assert profile_2.total_sessions_analyzed == 2
    assert profile_2.total_speaking_seconds == 14.0

    # Promedio matemático exacto: ((score_1 * 1) + 0.90) / 2
    expected_openness = round(((eval_1.openness_score * 1) + 0.90) / 2, 3)
    assert profile_2.big_five.openness.score == expected_openness

    # Verificar que el perfil actualizado siga cumpliendo el JSON Schema
    data_2 = json.loads(profile_2.model_dump_json())
    jsonschema.validate(instance=data_2, schema=schema)


def test_adaptive_running_avg_longitudinal():
    # En sesión 1 (n_prev=0): adopta el nuevo valor
    assert running_avg(0.5, 0.8, 0) == 0.8

    # En sesión 5 (n_prev=4): peso = 1/5 = 0.20
    val_5 = running_avg(0.5, 1.0, 4)
    assert val_5 == 0.6  # 0.8 * 0.5 + 0.2 * 1.0 = 0.6

    # En sesión 50 (n_prev=49): peso acotado en min_alpha (0.05) para plasticidad a largo plazo
    val_50 = running_avg(0.5, 1.0, 49)
    assert val_50 == 0.525  # 0.95 * 0.5 + 0.05 * 1.0 = 0.525


def test_calculate_accumulated_confidence_asymptotic():
    from core.profiler.profile_synthesizer import calculate_accumulated_confidence

    # Sesión 1: confianza inicial
    c1 = calculate_accumulated_confidence(0.70, 0.70, 1)
    assert c1 == 0.70

    # Sesión 5: confianza acumulada crece
    c5 = calculate_accumulated_confidence(0.70, 0.75, 5)
    assert c5 > 0.75

    # Sesión 30 (más de 1 mes de llamadas): certeza satura cerca de 0.99
    c30 = calculate_accumulated_confidence(0.85, 0.85, 30)
    assert c30 >= 0.95
    assert c30 <= 0.99


def test_cleanup_session_audio(tmp_path):
    from main import cleanup_session_audio

    # Crear estructura simulada de sesión
    session_dir = tmp_path / "2026-09-25_test"
    audio_dir = session_dir / "audio"
    audio_dir.mkdir(parents=True)

    track1 = audio_dir / "user1.wav"
    track2 = audio_dir / "user2.wav"
    track1.write_bytes(b"A" * 1024)
    track2.write_bytes(b"B" * 2048)

    transcript_file = session_dir / "transcript.json"
    transcript_file.write_text('{"test": true}', encoding="utf-8")

    # Ejecutar limpieza
    freed_bytes = cleanup_session_audio(str(session_dir))
    assert freed_bytes == 3072

    # Verificar que los archivos .wav fueron borrados
    assert not track1.exists()
    assert not track2.exists()

    # Verificar que el marcador .purged fue creado
    assert (audio_dir / ".purged").exists()

    # Verificar que transcript.json sigue intacto
    assert transcript_file.exists()


def test_create_daily_backup(tmp_path):
    from main import create_daily_backup

    # Simular profiles_dir
    profiles_dir = tmp_path / "profiles" / "12345"
    profiles_dir.mkdir(parents=True)
    (profiles_dir / "profile.json").write_text('{"user_id": "12345"}', encoding="utf-8")

    backup_path = create_daily_backup(str(tmp_path))
    assert backup_path is not None
    assert os.path.exists(backup_path)
    assert backup_path.endswith(".zip")

    # Llamar de nuevo hoy debe retornar el mismo archivo existente
    second_call = create_daily_backup(str(tmp_path))
    assert second_call == backup_path


def test_compute_social_and_temporal_metrics(sample_transcript):
    social_metrics = compute_social_and_temporal_metrics(
        transcript=sample_transcript,
        threads=None,
        target_user_id="user_marce",
    )
    assert social_metrics.target_user_id == "user_marce"
    # Interacción por solapamiento con user_arbustin
    assert "user_arbustin" in social_metrics.peer_interactions
    assert social_metrics.peer_interactions["user_arbustin"]["interactions"] >= 1
    # Hora de la sesión: 00:00 -> madrugada
    assert "madrugada" in social_metrics.hour_category


def test_profile_synthesis_multidimensional(tmp_path, sample_transcript):
    synthesizer = ProfileSynthesizer(storage_dir=str(tmp_path))
    metrics = compute_user_metrics(sample_transcript, "user_marce")
    profiler = GeminiProfiler(mock=True)
    evaluation = profiler.analyze_user_session(sample_transcript, "user_marce", "saframa", metrics)
    social_metrics = compute_social_and_temporal_metrics(sample_transcript, None, "user_marce")

    # Sesión 1
    profile_s1 = synthesizer.synthesize_profile(
        user_id="user_marce",
        username="saframa",
        session_id=sample_transcript.session_id,
        session_metrics=metrics,
        evaluation=evaluation,
        social_temporal_metrics=social_metrics,
    )

    assert profile_s1.social_dynamics is not None
    assert "user_arbustin" in profile_s1.social_dynamics.affinities
    assert len(profile_s1.group_lore.inside_jokes) >= 1
    assert "dar flama" in profile_s1.group_lore.inside_jokes or len(profile_s1.group_lore.inside_jokes) > 0
    assert profile_s1.temporal_patterns.cronotype == "noctambulo"
    assert len(profile_s1.temporal_patterns.peak_hours) >= 1

    # Sesión 2: acumulación y enriquecimiento
    evaluation_s2 = evaluation.model_copy()
    evaluation_s2.inside_jokes = ["dar flama", "el bot se fue de tema"]
    evaluation_s2.tilts = ["lag en discord"]

    profile_s2 = synthesizer.synthesize_profile(
        user_id="user_marce",
        username="saframa",
        session_id="2026-09-25_00-15-00",
        session_metrics=metrics,
        evaluation=evaluation_s2,
        social_temporal_metrics=social_metrics,
    )

    assert profile_s2.total_sessions_analyzed == 2
    # Las interacciones deben haberse incrementado
    assert profile_s2.social_dynamics.affinities["user_arbustin"].interaction_count >= 2
    # Inside jokes combinados y deduplicados
    assert "el bot se fue de tema" in profile_s2.group_lore.inside_jokes
    assert "lag en discord" in profile_s2.emotional_triggers.tilts


def test_extract_user_vocabulary():
    from core.profiler.metrics import extract_user_vocabulary
    utterances = [
        Utterance(
            id=1,
            user_id="u1",
            username="mateo",
            start_time=0.0,
            end_time=3.0,
            duration=3.0,
            text="Bo, mirá que el loco se fue al carajo, qué salado posta.",
            confidence=0.99,
        ),
        Utterance(
            id=2,
            user_id="u1",
            username="mateo",
            start_time=4.0,
            end_time=7.0,
            duration=3.0,
            text="Sí bo, salado mal, posta te digo.",
            confidence=0.98,
        ),
    ]
    vocab = extract_user_vocabulary(utterances)
    assert isinstance(vocab, dict)
    assert vocab["bo"] == 2
    assert vocab["salado"] == 2
    assert vocab["posta"] == 2
    assert vocab["mirá"] == 1
    # Universal grammatical stopwords must be filtered out
    assert "el" not in vocab
    assert "se" not in vocab
    assert "al" not in vocab


def test_profile_synthesizer_vocabulary_accumulation(tmp_path):
    synthesizer = ProfileSynthesizer(storage_dir=str(tmp_path))
    profiler = GeminiProfiler(mock=True)

    t1 = SessionTranscript(
        version="1.0.0",
        session_id="2026-09-25_00-00-00",
        processed_at=datetime.now(timezone.utc),
        model="faster-whisper/medium",
        utterances=[
            Utterance(id=1, user_id="u1", username="test", start_time=0, end_time=2, duration=2, text="bo salado flama", confidence=0.9)
        ]
    )
    m1 = compute_user_metrics(t1, "u1")
    eval1 = profiler.analyze_user_session(t1, "u1", "test", m1)
    p1 = synthesizer.synthesize_profile("u1", "test", "2026-09-25_00-00-00", m1, eval1)

    assert p1.dialect_markers.vocabulary_frequencies.get("bo") == 1
    assert p1.dialect_markers.vocabulary_frequencies.get("salado") == 1
    assert p1.dialect_markers.vocabulary_frequencies.get("flama") == 1

    t2 = SessionTranscript(
        version="1.0.0",
        session_id="2026-09-25_00-15-00",
        processed_at=datetime.now(timezone.utc),
        model="faster-whisper/medium",
        utterances=[
            Utterance(id=1, user_id="u1", username="test", start_time=0, end_time=2, duration=2, text="bo salado de nuevo bo", confidence=0.9)
        ]
    )
    m2 = compute_user_metrics(t2, "u1")
    eval2 = profiler.analyze_user_session(t2, "u1", "test", m2)
    p2 = synthesizer.synthesize_profile("u1", "test", "2026-09-25_00-15-00", m2, eval2)

    assert p2.dialect_markers.vocabulary_frequencies["bo"] == 3
    assert p2.dialect_markers.vocabulary_frequencies["salado"] == 2
    assert p2.dialect_markers.vocabulary_frequencies["flama"] == 1

