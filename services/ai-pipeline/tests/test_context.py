"""
Tests unitarios para el Motor de Contexto Conversacional y Topic Modeling (Zero-Token).
"""

from datetime import datetime, timezone
import pytest

from core.context.threader import DiscourseThreader
from core.context.topic_detector import TopicDetector
from core.contracts.models import SessionTranscript, Utterance
from core.user_manager.manager import UserManager


def test_topic_detector_keywords():
    """Verifica que TF-IDF filtre stopwords y extraiga palabras clave relevantes."""
    detector = TopicDetector(top_n_keywords=3)
    texts = [
        "El bot de Discord no está funcionando bien.",
        "Parece que el audio del bot se rompió.",
        "Probá reiniciar el bot de nuevo.",
    ]
    keywords = detector.extract_keywords(texts)
    assert "bot" in keywords
    assert "discord" in keywords or "audio" in keywords


def test_topic_detector_intent():
    """Verifica la clasificación de intenciones conversacionales."""
    detector = TopicDetector()
    assert detector.classify_thread_intent(["¿Che, qué pasó que no anda el bot?"]) == "Consulta Técnica / Verificación"
    assert detector.classify_thread_intent(["Jajaja qué fiera que sos Kevin"]) == "Broma / Chicana Afectuosa"
    assert detector.classify_thread_intent(["Salgamos y volvemos a entrar a la llamada"]) == "Coordinación de Llamada / Juego"


def test_discourse_threader_reconstruction():
    """Verifica la reconstrucción de hilos y la detección de pares pregunta-respuesta."""
    threader = DiscourseThreader(max_gap_seconds=8.0)

    # Simular una interacción típica de Discord
    now = datetime.now(timezone.utc)
    utterances = [
        # Hilo 1: Pregunta de Kevin y respuesta de Marce
        Utterance(id=1, user_id="101", username="kevinjaffe", start_time=1.0, end_time=3.0, duration=2.0, confidence=0.95, text="¿El bot está grabando ahora?"),
        Utterance(id=2, user_id="102", username="saframa", start_time=3.5, end_time=5.0, duration=1.5, confidence=0.95, text="Sí, Kevin, está grabando flama."),
        
        # Hilo 2 (mucho después): Arbustin cambiando de tema
        Utterance(id=3, user_id="103", username="tinixx8917", start_time=25.0, end_time=27.0, duration=2.0, confidence=0.95, text="Che, ¿jugamos una partidita de LoL?"),
        Utterance(id=4, user_id="102", username="saframa", start_time=27.5, end_time=29.0, duration=1.5, confidence=0.95, text="Dale, abrí el cliente."),
    ]

    transcript = SessionTranscript(
        version="1.0.0",
        session_id="session_test_context",
        processed_at=now,
        model="whisper-test",
        utterances=utterances,
    )

    threads = threader.reconstruct_threads(transcript)

    assert len(threads) == 2

    # Hilo 1
    t1 = threads[0]
    assert "kevinjaffe" in t1.participants
    assert "saframa" in t1.participants
    assert t1.turns[1].reply_to_utterance_id == "u_0"  # Marce responde a Kevin
    assert t1.turns[1].reply_confidence > 0.4

    # Hilo 2
    t2 = threads[1]
    assert "tinixx8917" in t2.participants
    assert t2.turns[1].reply_to_utterance_id == "u_2"  # Marce responde a Arbustin


def test_discourse_threader_with_user_manager_nicknames(tmp_path):
    """Verifica que los apodos registrados en UserManager aumenten la probabilidad de enlace."""
    u_mgr = UserManager(str(tmp_path))
    u_mgr.create_user(user_id="101", username="kevinjaffe", nicknames=["cabeza", "kev"])

    threader = DiscourseThreader(user_manager=u_mgr)

    now = datetime.now(timezone.utc)
    utterances = [
        Utterance(id=1, user_id="101", username="kevinjaffe", start_time=1.0, end_time=2.5, duration=1.5, confidence=0.95, text="Hola a todos."),
        Utterance(id=2, user_id="102", username="saframa", start_time=4.0, end_time=6.0, duration=2.0, confidence=0.95, text="¿Qué hacés, cabeza? Todo bien."),
    ]

    transcript = SessionTranscript(
        version="1.0.0",
        session_id="session_nick_test",
        processed_at=now,
        model="whisper-test",
        utterances=utterances,
    )

    threads = threader.reconstruct_threads(transcript)
    assert len(threads) == 1
    # Debe asociar la respuesta de Marce a Kevin debido a la mención del apodo 'cabeza'
    assert threads[0].turns[1].reply_to_utterance_id == "u_0"


def test_thread_format_tree():
    """Verifica que format_tree devuelva una cadena válida con estructura de árbol."""
    threader = DiscourseThreader()
    now = datetime.now(timezone.utc)
    utterances = [
        Utterance(id=1, user_id="1", username="kevin", start_time=1.0, end_time=2.0, duration=1.0, confidence=0.95, text="¿Probamos el audio?"),
        Utterance(id=2, user_id="2", username="marce", start_time=2.5, end_time=4.0, duration=1.5, confidence=0.95, text="Sí, dale."),
    ]
    transcript = SessionTranscript(
        version="1.0.0",
        session_id="session_tree_test",
        processed_at=now,
        model="whisper-test",
        utterances=utterances,
    )
    threads = threader.reconstruct_threads(transcript)
    tree_str = threads[0].format_tree()
    assert "🧵 Hilo #1" in tree_str
    assert "[kevin]" in tree_str
    assert "[marce]" in tree_str
