"""
Test Suite: Fallback a LLaMA para el Gemelo Digital
Verifica que cuando Gemini API falla o agota la cuota diaria (429 Quota Exceeded),
el sistema delega automáticamente la respuesta a la API de LLaMA (Groq/OpenRouter/Ollama).
"""

from unittest.mock import MagicMock, patch
import pytest
from datetime import datetime, timezone

from core.contracts.models import (
    BigFiveTraits,
    CommunicationStyle,
    DialectMarkers,
    GroupRole,
    TraitEvaluation,
    UserProfile,
)
from core.twin.chat_session import DigitalTwinChat
from core.twin.llama_client import LlamaClient


@pytest.fixture
def sample_user_profile():
    trait = TraitEvaluation(score=0.7, confidence=0.8, evidence_quotes=[])
    return UserProfile(
        version="1.0.0",
        user_id="960401021757169694",
        username="garmadius",
        display_name="Suna",
        last_updated=datetime.now(timezone.utc),
        total_sessions_analyzed=5,
        total_speaking_seconds=500.0,
        big_five=BigFiveTraits(
            openness=trait,
            conscientiousness=trait,
            extraversion=trait,
            agreeableness=trait,
            neuroticism=trait,
        ),
        communication_style=CommunicationStyle(
            avg_words_per_turn=8.5,
            cadence="rapido",
            interruption_ratio=0.3,
            humor_type="chicanas afectuosas",
        ),
        group_role=GroupRole(
            primary_role="El Conductor",
            description="Lidera la charla",
            conflict_style="ironía",
        ),
        dialect_markers=DialectMarkers(
            rioplatense_frequency=0.2,
            favorite_slang=["bo", "ta", "flama"],
            discourse_fillers=["bo", "che"],
        ),
    )


def test_llama_client_availability():
    """Verifica detección de disponibilidad de LlamaClient según keys configuradas."""
    # Sin credenciales ni Ollama local
    client_empty = LlamaClient(api_key="")
    client_empty.groq_key = ""
    client_empty.openrouter_key = ""
    with patch.object(client_empty, "_check_ollama_alive", return_value=False):
        assert not client_empty.is_available()

    # Con Groq key configurada
    client_groq = LlamaClient(api_key="gsk_test_fake_key_12345")
    assert client_groq.is_available()


def test_llama_client_groq_call():
    """Verifica que LlamaClient invoque la API de Groq correctamente."""
    client = LlamaClient(api_key="gsk_test_key")
    mock_groq = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content="¡Qué hacés bo! Todo tranqui."))]
    mock_groq.chat.completions.create.return_value = mock_completion
    client._groq_client = mock_groq

    reply = client.chat(
        system_prompt="Eres Suna",
        messages=[{"role": "user", "text": "Hola Suna"}],
        temperature=0.75,
    )

    assert "bo" in reply
    mock_groq.chat.completions.create.assert_called_once()
    call_args = mock_groq.chat.completions.create.call_args[1]
    assert call_args["model"] == "llama-3.3-70b-versatile"
    assert call_args["messages"][0]["role"] == "system"
    assert call_args["messages"][1]["role"] == "user"


def test_digital_twin_fallback_to_llama_on_gemini_error(sample_user_profile):
    """Verifica que DigitalTwinChat delegue a LLaMA cuando Gemini lanza 429 RESOURCE_EXHAUSTED."""
    mock_llama = MagicMock(spec=LlamaClient)
    mock_llama.is_available.return_value = True
    mock_llama.chat.return_value = "¡Bo, acá andamos con la física, flama total!"

    chat = DigitalTwinChat(
        profile=sample_user_profile,
        api_key="fake_key",
        mock=False,
        llama_client=mock_llama,
    )

    # Simular fallo 429 en Gemini
    mock_gemini_chat = MagicMock()
    mock_gemini_chat.send_message.side_effect = Exception("429 RESOURCE_EXHAUSTED. Quota exceeded.")
    chat._chat = mock_gemini_chat

    reply = chat.send_message("¿Qué hacés Suna?")

    assert reply == "¡Bo, acá andamos con la física, flama total!"
    mock_llama.chat.assert_called_once()
    assert chat.history[-1]["role"] == "assistant"
    assert chat.history[-1]["text"] == reply


def test_digital_twin_forced_llama_backend(sample_user_profile):
    """Verifica que si backend='llama', responda directamente con LLaMA sin consultar a Gemini."""
    mock_llama = MagicMock(spec=LlamaClient)
    mock_llama.is_available.return_value = True
    mock_llama.chat.return_value = "Respuesta directa de LLaMA 3.3"

    chat = DigitalTwinChat(
        profile=sample_user_profile,
        backend="llama",
        llama_client=mock_llama,
    )

    assert chat.backend == "llama"
    assert chat._chat is None  # No inicializó chat de Gemini

    reply = chat.send_message("Test directo")
    assert reply == "Respuesta directa de LLaMA 3.3"
    mock_llama.chat.assert_called_once()


def test_gemini_profiler_fallback_to_llama_on_quota():
    """Verifica que GeminiProfiler delegue automáticamente a LLaMA cuando Gemini agota la cuota (429 RESOURCE_EXHAUSTED)."""
    import json
    from core.contracts.models import SessionTranscript, Utterance
    from core.profiler.metrics import compute_user_metrics
    from core.profiler.gemini_analyzer import GeminiProfiler, GeminiSessionEvaluation

    transcript = SessionTranscript(
        version="1.0.0",
        session_id="2026-09-25_test_session",
        processed_at=datetime.now(timezone.utc),
        model="faster-whisper/medium",
        utterances=[
            Utterance(
                id=1,
                user_id="user_test",
                username="test_user",
                start_time=0.0,
                end_time=3.0,
                duration=3.0,
                text="Bo, esto está tremendo posta!",
                confidence=0.95,
                overlapping_speakers=[],
            )
        ],
    )
    metrics = compute_user_metrics(transcript, "user_test")

    mock_llama = MagicMock(spec=LlamaClient)
    mock_llama.is_available.return_value = True
    llama_evaluation_json = {
        "openness_score": 0.8,
        "openness_confidence": 0.9,
        "openness_evidence": ["Bo, esto está tremendo posta!"],
        "conscientiousness_score": 0.6,
        "conscientiousness_confidence": 0.8,
        "conscientiousness_evidence": ["Bo, esto está tremendo posta!"],
        "extraversion_score": 0.85,
        "extraversion_confidence": 0.95,
        "extraversion_evidence": ["Bo, esto está tremendo posta!"],
        "agreeableness_score": 0.7,
        "agreeableness_confidence": 0.85,
        "agreeableness_evidence": ["Bo, esto está tremendo posta!"],
        "neuroticism_score": 0.3,
        "neuroticism_confidence": 0.75,
        "neuroticism_evidence": ["Bo, esto está tremendo posta!"],
        "primary_role": "El Conductor",
        "role_description": "Lidera la interacción con humor y confianza",
        "conflict_style": "chicanas amigables",
        "humor_type": "ironía cómplice",
        "rioplatense_frequency": 0.45,
        "favorite_slang": ["bo", "posta"],
        "discourse_fillers": ["bo"],
        "initiative": "iniciador",
    }
    mock_llama.chat.return_value = json.dumps(llama_evaluation_json)

    profiler = GeminiProfiler(api_key="fake_key", mock=False)
    profiler._llama_client = mock_llama

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED: Quota exceeded for quota metric 'Generate Content API'")
    profiler._client = mock_client

    evaluation = profiler.analyze_user_session(
        transcript=transcript,
        target_user_id="user_test",
        target_username="test_user",
        metrics=metrics,
    )

    assert isinstance(evaluation, GeminiSessionEvaluation)
    assert evaluation.openness_score == 0.8
    assert evaluation.extraversion_score == 0.85
    assert evaluation.primary_role == "El Conductor"
    assert "bo" in evaluation.favorite_slang
    mock_llama.chat.assert_called_once()


def test_gemini_profiler_uses_llama_when_gemini_key_missing():
    """Verifica que si la API key de Gemini no está configurada o es vacía, use LLaMA si está disponible."""
    import json
    from core.contracts.models import SessionTranscript, Utterance
    from core.profiler.metrics import compute_user_metrics
    from core.profiler.gemini_analyzer import GeminiProfiler, GeminiSessionEvaluation

    transcript = SessionTranscript(
        version="1.0.0",
        session_id="2026-09-25_test_session_2",
        processed_at=datetime.now(timezone.utc),
        model="faster-whisper/medium",
        utterances=[
            Utterance(
                id=1,
                user_id="user_test",
                username="test_user",
                start_time=0.0,
                end_time=3.0,
                duration=3.0,
                text="Tranqui, que esto sale flama.",
                confidence=0.95,
                overlapping_speakers=[],
            )
        ],
    )
    metrics = compute_user_metrics(transcript, "user_test")

    mock_llama = MagicMock(spec=LlamaClient)
    mock_llama.is_available.return_value = True
    llama_evaluation_json = {
        "openness_score": 0.75,
        "openness_confidence": 0.85,
        "openness_evidence": ["Tranqui, que esto sale flama."],
        "conscientiousness_score": 0.7,
        "conscientiousness_confidence": 0.8,
        "conscientiousness_evidence": ["Tranqui, que esto sale flama."],
        "extraversion_score": 0.9,
        "extraversion_confidence": 0.9,
        "extraversion_evidence": ["Tranqui, que esto sale flama."],
        "agreeableness_score": 0.8,
        "agreeableness_confidence": 0.85,
        "agreeableness_evidence": ["Tranqui, que esto sale flama."],
        "neuroticism_score": 0.2,
        "neuroticism_confidence": 0.7,
        "neuroticism_evidence": ["Tranqui, que esto sale flama."],
        "primary_role": "El Facilitador",
        "role_description": "Promueve la tranquilidad y buen ambiente",
        "conflict_style": "mediación y calma",
        "humor_type": "humor relajado",
        "rioplatense_frequency": 0.35,
        "favorite_slang": ["flama", "tranqui"],
        "discourse_fillers": ["tranqui"],
        "initiative": "iniciador",
    }
    mock_llama.chat.return_value = json.dumps(llama_evaluation_json)

    profiler = GeminiProfiler(mock=True)
    profiler.api_key = ""
    profiler._llama_client = mock_llama

    evaluation = profiler.analyze_user_session(
        transcript=transcript,
        target_user_id="user_test",
        target_username="test_user",
        metrics=metrics,
    )

    assert isinstance(evaluation, GeminiSessionEvaluation)
    assert evaluation.openness_score == 0.75
    assert evaluation.primary_role == "El Facilitador"
    mock_llama.chat.assert_called_once()


