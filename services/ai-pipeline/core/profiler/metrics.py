"""
Módulo de Métricas Conversacionales Cuantitativas (Pre-LLM)
Calcula métricas estadísticas directas desde los enunciados de la sesión:
volumen de habla, palabras por turno, tasa de interrupción/solapamiento y cadencia.
"""

from typing import Dict, List, Literal, Optional
import numpy as np

from core.contracts.models import SessionTranscript, Utterance


class ConversationalMetrics:
    def __init__(
        self,
        user_id: str,
        total_speaking_seconds: float,
        turn_count: int,
        total_words: int,
        avg_words_per_turn: float,
        interruption_ratio: float,
        cadence: Literal["rapido", "pausado", "irregular", "moderado"],
        words_per_second: float,
    ):
        self.user_id = user_id
        self.total_speaking_seconds = total_speaking_seconds
        self.turn_count = turn_count
        self.total_words = total_words
        self.avg_words_per_turn = avg_words_per_turn
        self.interruption_ratio = interruption_ratio
        self.cadence = cadence
        self.words_per_second = words_per_second

    def to_dict(self) -> Dict[str, any]:
        return {
            "user_id": self.user_id,
            "total_speaking_seconds": round(self.total_speaking_seconds, 2),
            "turn_count": self.turn_count,
            "total_words": self.total_words,
            "avg_words_per_turn": round(self.avg_words_per_turn, 2),
            "interruption_ratio": round(self.interruption_ratio, 3),
            "cadence": self.cadence,
            "words_per_second": round(self.words_per_second, 2),
        }


def compute_user_metrics(
    transcript: SessionTranscript,
    user_id: str,
) -> ConversationalMetrics:
    """
    Analiza todos los enunciados de un usuario en una sesión y extrae
    métricas conversacionales cuantitativas rigurosas.
    """
    user_utterances: List[Utterance] = [
        u for u in transcript.utterances if u.user_id == user_id
    ]

    turn_count = len(user_utterances)
    if turn_count == 0:
        return ConversationalMetrics(
            user_id=user_id,
            total_speaking_seconds=0.0,
            turn_count=0,
            total_words=0,
            avg_words_per_turn=0.0,
            interruption_ratio=0.0,
            cadence="moderado",
            words_per_second=0.0,
        )

    total_duration = sum(u.duration for u in user_utterances)
    words_per_turn_list = []
    wps_list = []
    interrupted_turns = 0

    for u in user_utterances:
        words = u.text.split()
        num_words = len(words)
        words_per_turn_list.append(num_words)

        if u.duration > 0.2:
            wps = num_words / u.duration
            wps_list.append(wps)

        if u.overlapping_speakers and len(u.overlapping_speakers) > 0:
            interrupted_turns += 1

    total_words = sum(words_per_turn_list)
    avg_words_per_turn = total_words / turn_count if turn_count > 0 else 0.0
    interruption_ratio = interrupted_turns / turn_count if turn_count > 0 else 0.0

    overall_wps = total_words / total_duration if total_duration > 0 else 0.0

    # Determinación de cadencia según velocidad y dispersión
    cadence: Literal["rapido", "pausado", "irregular", "moderado"] = "moderado"
    if len(wps_list) >= 3:
        std_wps = float(np.std(wps_list))
        # Si la varianza entre turnos es muy alta, es irregular (ej. alterna monosílabos y ametralladoras de texto)
        if std_wps > 1.8:
            cadence = "irregular"
        elif overall_wps > 3.2:
            cadence = "rapido"
        elif overall_wps < 1.8:
            cadence = "pausado"
        else:
            cadence = "moderado"
    else:
        if overall_wps > 3.2:
            cadence = "rapido"
        elif overall_wps < 1.8:
            cadence = "pausado"
        else:
            cadence = "moderado"

    return ConversationalMetrics(
        user_id=user_id,
        total_speaking_seconds=total_duration,
        turn_count=turn_count,
        total_words=total_words,
        avg_words_per_turn=avg_words_per_turn,
        interruption_ratio=interruption_ratio,
        cadence=cadence,
        words_per_second=overall_wps,
    )
