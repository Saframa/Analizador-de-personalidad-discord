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
from core.profiler.metrics import compute_user_metrics
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
