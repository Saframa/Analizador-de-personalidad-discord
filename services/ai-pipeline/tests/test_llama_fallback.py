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
