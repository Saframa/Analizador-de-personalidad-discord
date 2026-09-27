"""
Prueba Funcional: Árbol de Procesamiento de Lenguaje Natural (Discourse Threader)
Simula una conversación realista de 7 personas anónimas sin mención explícita de nombres/destinatarios,
separa los diálogos individuales de cada persona, los reconcilia en el transcript
y evalúa la reconstrucción de grafos y árboles conversacionales.
"""

from datetime import datetime, timezone
import json
import pytest
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.contracts.models import SessionTranscript, Utterance
from core.context.threader import DiscourseThreader


def generate_raw_conversation():
    """
    Genera una charla natural de 7 personas sin mención de nombres directos.
    Retorna la lista de intervenciones ordenadas temporalmente.
    """
    return [
        # --- Hilo 1: Problema técnico con el servidor ---
        {
            "speaker_id": "anon_1",
            "start": 1.0,
            "end": 3.5,
            "text": "¿Alguien sabe por qué se cayó el servidor recién?",
        },
        {
            "speaker_id": "anon_2",
            "start": 4.2,
            "end": 7.8,
            "text": "Sí, me parece que crasheó la base de datos por un pico de memoria.",
        },
        {
            "speaker_id": "anon_3",
            "start": 8.5,
            "end": 11.2,
            "text": "¿Reiniciamos el proceso o esperamos que levante solo?",
        },
        {
            "speaker_id": "anon_1",
            "start": 11.8,
            "end": 14.5,
            "text": "No, mejor levantalo a mano porque si no no arranca más.",
        },

        # --- Hilo 2: Pedido de comida (ocurre poco después) ---
        {
            "speaker_id": "anon_4",
            "start": 18.0,
            "end": 20.8,
            "text": "Che, ¿al final qué vamos a pedir para comer hoy?",
        },
        {
            "speaker_id": "anon_5",
            "start": 21.5,
            "end": 24.5,
            "text": "Yo tengo ganas de unas pizzas de muzzarella bien cargadas.",
        },
        {
            "speaker_id": "anon_6",
            "start": 25.0,
            "end": 27.8,
            "text": "Capaz que empanadas rinde más si somos varios.",
        },
        {
            "speaker_id": "anon_4",
            "start": 28.5,
            "end": 31.0,
            "text": "¿Cuántas calculamos por persona, tres o cuatro?",
        },
        {
            "speaker_id": "anon_5",
            "start": 31.6,
            "end": 34.2,
            "text": "Con tres estamos sobrados, no seas animal.",
        },

        # --- Hilo 3: Broma y anécdota personal ---
        {
            "speaker_id": "anon_7",
            "start": 35.0,
            "end": 38.5,
            "text": "Bueno, mientras ustedes deciden la comida, yo ya me mandé un alfajor.",
        },
        {
            "speaker_id": "anon_6",
            "start": 39.0,
            "end": 42.0,
            "text": "Jajaja no tenés vergüenza, no aguantás media hora.",
        },
        {
            "speaker_id": "anon_7",
            "start": 42.6,
            "end": 45.8,
            "text": "Es que tenía un hambre tremendo desde que salí del laburo.",
        },

        # --- Hilo 4: Retorno al tema del servidor luego de una pausa (> 15s de silencio) ---
        {
            "speaker_id": "anon_2",
            "start": 62.0,
            "end": 65.5,
            "text": "Aviso que ya levantó de vuelta el servicio y está corriendo sin errores.",
        },
        {
            "speaker_id": "anon_3",
            "start": 66.2,
            "end": 69.2,
            "text": "Menos mal, pensé que se había roto toda la configuración.",
        },
        {
            "speaker_id": "anon_1",
            "start": 69.8,
            "end": 72.0,
            "text": "Quedó impecable, gracias por la mano.",
        },
    ]


def test_functional_7_users_discourse_tree():
    # 1. Generar la conversación general
    raw_convo = generate_raw_conversation()
    
    # 2. Separar la conversación en los diálogos individuales de cada persona (como en las pistas de Discord)
    isolated_dialogues = {f"anon_{i}": [] for i in range(1, 8)}
    for turn in raw_convo:
        speaker = turn["speaker_id"]
        isolated_dialogues[speaker].append({
            "start": turn["start"],
            "end": turn["end"],
            "text": turn["text"]
        })
    
    print("\n--- Diálogos individuales separados por persona ---")
    for spk, turns in isolated_dialogues.items():
        print(f"[{spk}]: {len(turns)} intervenciones")

    # 3. Reconciliar los diálogos individuales en una línea de tiempo ordenada
    merged_utterances = []
    for spk, turns in isolated_dialogues.items():
        for t in turns:
            merged_utterances.append({
                "user_id": spk,
                "username": spk,
                "start_time": t["start"],
                "end_time": t["end"],
                "duration": round(t["end"] - t["start"], 2),
                "text": t["text"],
                "confidence": 0.96,
            })
    
    # Orden cronológico natural
    merged_utterances.sort(key=lambda u: u["start_time"])
    for idx, u in enumerate(merged_utterances):
        u["id"] = idx + 1

    transcript = SessionTranscript(
        version="1.0.0",
        session_id="test_7_users_session",
        processed_at=datetime.now(timezone.utc),
        model="faster-whisper/medium",
        utterances=[Utterance(**u) for u in merged_utterances],
    )

    # 4. Pasar al motor de árbol de PLN (DiscourseThreader)
    threader = DiscourseThreader(max_gap_seconds=10.0, min_connection_score=0.25)
    threads = threader.reconstruct_threads(transcript)

    print("\n" + "=" * 65)
    print(f"RESULTADO: {len(threads)} hilos detectados")
    print("=" * 65)
    for t in threads:
        print(t.format_tree())
        print()

    # Validaciones funcionales
    assert len(threads) >= 2, "Debe detectar múltiples hilos o componentes conexas debido a la pausa temporal"
    
    # Verificar que los 7 usuarios participaron
    all_participants = set()
    for t in threads:
        all_participants.update(t.participants)
    assert len(all_participants) == 7, "Todos los 7 participantes anónimos deben estar presentes en el árbol"


if __name__ == "__main__":
    test_functional_7_users_discourse_tree()
