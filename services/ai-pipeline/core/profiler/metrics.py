"""
Módulo de Métricas Conversacionales Cuantitativas (Pre-LLM)
Calcula métricas estadísticas directas desde los enunciados de la sesión:
volumen de habla, palabras por turno, tasa de interrupción/solapamiento y cadencia.
"""

from collections import Counter
import re
from typing import Any, Dict, List, Literal, Optional
import numpy as np

from core.contracts.models import SessionTranscript, Utterance

# Stopwords gramaticales universales en español (conectores funcionales sin valor de idiolecto)
SPANISH_GRAMMATICAL_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "a", "al", "en",
    "para", "por", "con", "sin", "sobre", "entre", "tras", "durante", "mediante", "hacia",
    "desde", "hasta", "contra", "bajo", "que", "y", "e", "o", "u", "pero", "mas", "aunque",
    "sino", "como", "si", "cuando", "donde", "porque", "pues", "es", "son", "era", "eran",
    "fue", "fueron", "ser", "estar", "esta", "este", "estos", "estas", "ese", "esa", "esos",
    "esas", "aquel", "aquella", "aquellos", "aquellas", "me", "te", "se", "nos", "os", "mi",
    "tu", "su", "mis", "tus", "sus", "le", "les", "lo", "yo", "vosotros", "nosotros",
    "muy", "tan", "ya", "hay", "habia", "había", "todo", "toda", "todos", "todas", "otro",
    "otra", "otros", "otras", "cada", "algo", "nada", "asi", "así", "bien"
}

# Modismos, partículas orales y jerga rioplatense que NUNCA deben descartarse
RIOPLATENSE_IDIOLECT_WHITELIST = {
    "bo", "ta", "che", "pa", "fa", "ah", "eh", "re", "mal", "posta", "salado",
    "flama", "capaz", "mirá", "mira", "viste", "tenés", "tenes", "sos", "dale",
    "pará", "para", "vamo", "vamos", "loco", "fiera", "perro", "amigo", "onda",
    "tipo", "literal", "claro", "manija", "pibe", "gurí", "guri", "vos", "de menos"
}


def extract_user_vocabulary(
    utterances: List[Utterance],
    min_word_len: int = 2,
) -> Dict[str, int]:
    """
    Extrae el vocabulario característico del usuario a partir de sus intervenciones.
    Filtra palabras funcionales vacías (stopwords), preservando modismos rioplatenses,
    partículas orales y acentuación dialectal. Retorna un diccionario ordenado por frecuencia.
    """
    counter: Counter[str] = Counter()

    for u in utterances:
        raw_words = re.findall(r"\b[a-záéíóúñüA-ZÁÉÍÓÚÑÜ]{2,}\b", u.text.lower())
        for word in raw_words:
            if word in RIOPLATENSE_IDIOLECT_WHITELIST:
                counter[word] += 1
                continue

            if word in SPANISH_GRAMMATICAL_STOPWORDS:
                continue

            if len(word) < min_word_len:
                continue

            counter[word] += 1

    return dict(counter.most_common())


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
        session_vocabulary: Optional[Dict[str, int]] = None,
    ):
        self.user_id = user_id
        self.total_speaking_seconds = total_speaking_seconds
        self.turn_count = turn_count
        self.total_words = total_words
        self.avg_words_per_turn = avg_words_per_turn
        self.interruption_ratio = interruption_ratio
        self.cadence = cadence
        self.words_per_second = words_per_second
        self.session_vocabulary = session_vocabulary or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "total_speaking_seconds": round(self.total_speaking_seconds, 2),
            "turn_count": self.turn_count,
            "total_words": self.total_words,
            "avg_words_per_turn": round(self.avg_words_per_turn, 2),
            "interruption_ratio": round(self.interruption_ratio, 3),
            "cadence": self.cadence,
            "words_per_second": round(self.words_per_second, 2),
            "session_vocabulary": self.session_vocabulary,
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

    session_vocab = extract_user_vocabulary(user_utterances)

    return ConversationalMetrics(
        user_id=user_id,
        total_speaking_seconds=total_duration,
        turn_count=turn_count,
        total_words=total_words,
        avg_words_per_turn=avg_words_per_turn,
        interruption_ratio=interruption_ratio,
        cadence=cadence,
        words_per_second=overall_wps,
        session_vocabulary=session_vocab,
    )


class SessionSocialTemporalMetrics:
    """Métricas cuantitativas de interacción social y contexto temporal de la sesión."""
    def __init__(
        self,
        target_user_id: str,
        peer_interactions: Dict[str, Dict[str, Any]],
        session_hour: int,
        hour_category: str,
    ):
        self.target_user_id = target_user_id
        self.peer_interactions = peer_interactions
        self.session_hour = session_hour
        self.hour_category = hour_category


def compute_social_and_temporal_metrics(
    transcript: SessionTranscript,
    threads: Optional[List[Any]],
    target_user_id: str,
) -> SessionSocialTemporalMetrics:
    """
    Calcula algoritmicamente (0 tokens) las interacciones recíprocas entre el usuario
    y sus compañeros en los hilos discursivos, así como la franja horaria de la sesión.
    """
    peer_stats: Dict[str, Dict[str, Any]] = {}
    user_map: Dict[str, str] = {}

    for u in transcript.utterances:
        user_map[u.user_id] = u.username

    # 1. Contar réplicas e interacciones a partir de hilos conversacionales
    if threads:
        turn_map = {}
        for thread in threads:
            for turn in thread.turns:
                turn_map[turn.utterance_id] = turn

        for thread in threads:
            for turn in thread.turns:
                if turn.reply_to_utterance_id and turn.reply_to_utterance_id in turn_map:
                    parent_turn = turn_map[turn.reply_to_utterance_id]
                    # Si el target le respondió a un compañero
                    if turn.user_id == target_user_id and parent_turn.user_id != target_user_id:
                        p_id = parent_turn.user_id
                        p_name = parent_turn.username
                        if p_id not in peer_stats:
                            peer_stats[p_id] = {"username": p_name, "interactions": 0, "replies_to": 0}
                        peer_stats[p_id]["interactions"] += 1
                        peer_stats[p_id]["replies_to"] += 1
                    # Si un compañero le respondió al target
                    elif turn.user_id != target_user_id and parent_turn.user_id == target_user_id:
                        p_id = turn.user_id
                        p_name = turn.username
                        if p_id not in peer_stats:
                            peer_stats[p_id] = {"username": p_name, "interactions": 0, "replies_to": 0}
                        peer_stats[p_id]["interactions"] += 1

    # 2. Contabilizar solapamientos mutuos (intervenciones simultáneas)
    for u in transcript.utterances:
        if u.user_id == target_user_id and u.overlapping_speakers:
            for p_id in u.overlapping_speakers:
                if p_id and p_id != target_user_id:
                    p_name = user_map.get(p_id, p_id)
                    if p_id not in peer_stats:
                        peer_stats[p_id] = {"username": p_name, "interactions": 0, "replies_to": 0}
                    peer_stats[p_id]["interactions"] += 1

    # 3. Extracción de horario a partir de session_id o processed_at
    session_hour = 20  # default
    try:
        # Formato esperado: YYYY-MM-DD_HH-MM-SS
        time_part = transcript.session_id.split("_")[1]
        session_hour = int(time_part.split("-")[0])
    except Exception:
        if transcript.processed_at:
            session_hour = transcript.processed_at.hour

    if 5 <= session_hour < 12:
        hour_cat = "mañana (05:00 - 12:00)"
    elif 12 <= session_hour < 19:
        hour_cat = "tarde (12:00 - 19:00)"
    elif 19 <= session_hour <= 23:
        hour_cat = "noche (19:00 - 23:59)"
    else:
        hour_cat = "madrugada (00:00 - 04:59)"

    return SessionSocialTemporalMetrics(
        target_user_id=target_user_id,
        peer_interactions=peer_stats,
        session_hour=session_hour,
        hour_category=hour_cat,
    )

