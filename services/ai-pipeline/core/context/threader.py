"""
Motor de Reconstrucción de Contexto Conversacional y Grafos de Discurso (Discourse Threader).
Reconstruye qué interlocutor responde a quién, detecta hilos paralelos y agrupa intervenciones
con 0 consumo de tokens de API.
"""

import math
import re
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx
from pydantic import BaseModel, Field

from core.contracts.models import SessionTranscript, Utterance
from core.context.topic_detector import TopicDetector
from core.user_manager.manager import UserManager


class TurnRef(BaseModel):
    """Representa una intervención individual dentro de un hilo estructurado."""
    utterance_id: str
    user_id: str
    username: str
    start_time: float
    end_time: float
    text: str
    reply_to_utterance_id: Optional[str] = None
    reply_confidence: float = 0.0

    @property
    def start(self) -> float:
        return self.start_time

    @property
    def end(self) -> float:
        return self.end_time


class ConversationThread(BaseModel):
    """Representa un hilo temático y conversacional completo."""
    thread_id: str
    start_time: float
    end_time: float
    duration_seconds: float
    participants: List[str]
    turns: List[TurnRef]
    keywords: List[str] = Field(default_factory=list)
    intent: str = "Charla Casual"

    def format_tree(self) -> str:
        """Genera una representación en árbol legible en consola de la interacción."""
        lines = []
        lines.append(f"🧵 Hilo #{self.thread_id} | [{self.start_time:.1f}s - {self.end_time:.1f}s] | Dinámica: {self.intent}")
        if self.keywords:
            lines.append(f"   🔑 Palabras clave: {', '.join(self.keywords)}")
        lines.append("   " + "-" * 55)

        turn_dict = {t.utterance_id: t for t in self.turns}
        children_map: Dict[Optional[str], List[TurnRef]] = {}
        for t in self.turns:
            parent = t.reply_to_utterance_id
            children_map.setdefault(parent, []).append(t)

        def _print_node(turn: TurnRef, prefix: str = "", is_last: bool = True):
            connector = "└── " if is_last else "├── "
            conf_str = f" ({turn.reply_confidence*100:.0f}%)" if turn.reply_to_utterance_id else ""
            lines.append(f"   {prefix}{connector}[{turn.username}]: \"{turn.text}\"{conf_str}")
            
            sub_prefix = prefix + ("    " if is_last else "│   ")
            sub_children = children_map.get(turn.utterance_id, [])
            for i, child in enumerate(sub_children):
                _print_node(child, sub_prefix, i == len(sub_children) - 1)

        # Imprimir raíces del árbol (intervenciones sin padre dentro de este hilo)
        roots = [t for t in self.turns if not t.reply_to_utterance_id or t.reply_to_utterance_id not in turn_dict]
        for idx, root in enumerate(roots):
            _print_node(root, prefix="", is_last=(idx == len(roots) - 1))

        return "\n".join(lines)


class DiscourseThreader:
    def __init__(
        self,
        user_manager: Optional[UserManager] = None,
        max_gap_seconds: float = 10.0,
        min_connection_score: float = 0.25,
    ):
        self.user_manager = user_manager
        self.max_gap_seconds = max_gap_seconds
        self.min_connection_score = min_connection_score
        self.topic_detector = TopicDetector(top_n_keywords=5)

    def _get_user_aliases(self, user_id: str, username: str) -> Set[str]:
        """Obtiene todos los apodos, nombres y motes conocidos para un usuario."""
        aliases = {username.lower(), user_id.lower()}
        # Agregar variaciones del username
        clean_user = re.sub(r"[0-9_]+", "", username).lower()
        if len(clean_user) >= 3:
            aliases.add(clean_user)

        if self.user_manager:
            user = self.user_manager.get_user(user_id)
            if user:
                if user.display_name:
                    aliases.add(user.display_name.lower())
                for nick in user.nicknames:
                    aliases.add(nick.lower())

        return aliases

    def _compute_adjacency_score(
        self,
        prev: Utterance,
        curr: Utterance,
        prev_aliases: Set[str],
    ) -> float:
        """
        Calcula la probabilidad de que `curr` sea una respuesta directa o reacción a `prev`.
        Combina proximidad temporal, mención de nombres, marcadores Q&A y similitud léxica.
        """
        delta_t = curr.start_time - prev.end_time

        # Si el turno actual ocurrió mucho antes o más allá del límite temporal
        if delta_t > self.max_gap_seconds or delta_t < -3.0:
            return 0.0

        # 1. Decaimiento Temporal Exponencial (w_time = 0.40)
        # Cuanto más rápido responde, mayor la probabilidad
        if delta_t < 0:
            # Solapamiento / interrupción
            time_score = 0.90
        else:
            time_score = math.exp(-delta_t / 3.0)

        # 2. Mención Directa de Nombre o Apodo (w_mention = 0.35)
        mention_score = 0.0
        curr_text_lower = curr.text.lower()
        for alias in prev_aliases:
            # Búsqueda de palabra completa
            if re.search(r"\b" + re.escape(alias) + r"\b", curr_text_lower):
                mention_score = 1.0
                break

        # 3. Marcador de Pregunta -> Respuesta (w_qa = 0.20)
        qa_score = 0.0
        prev_text = prev.text.strip()
        curr_text = curr.text.strip().lower()

        is_prev_question = (
            "?" in prev_text
            or "¿" in prev_text
            or any(q in prev_text.lower() for q in ["qué", "cómo", "cuándo", "por qué", "viste", "sabés", "sabe"])
        )
        is_curr_answer = (
            curr_text.startswith("sí")
            or curr_text.startswith("si")
            or curr_text.startswith("no")
            or curr_text.startswith("capaz")
            or curr_text.startswith("claro")
            or curr_text.startswith("pasa que")
            or curr_text.startswith("es que")
            or curr_text.startswith("acá")
            or curr_text.startswith("aca")
        )
        if is_prev_question and is_curr_answer and prev.user_id != curr.user_id:
            qa_score = 1.0
        elif is_prev_question and prev.user_id != curr.user_id:
            qa_score = 0.5

        # 4. Solapamiento Léxico (w_lex = 0.10)
        tokens_prev = set(w.lower() for w in re.findall(r"\w{3,}", prev.text))
        tokens_curr = set(w.lower() for w in re.findall(r"\w{3,}", curr.text))
        lex_score = 0.0
        if tokens_prev and tokens_curr:
            jaccard = len(tokens_prev & tokens_curr) / len(tokens_prev | tokens_curr)
            lex_score = min(1.0, jaccard * 3.0)

        # 5. Penalización si es el mismo hablante continuando (a menos que sea consecutivo inmediato)
        same_speaker_penalty = 1.0
        if curr.user_id == prev.user_id:
            if delta_t < 1.0:
                same_speaker_penalty = 0.85
            else:
                same_speaker_penalty = 0.30

        total_score = (
            0.40 * time_score
            + 0.35 * mention_score
            + 0.20 * qa_score
            + 0.10 * lex_score
        ) * same_speaker_penalty

        return min(1.0, total_score)

    def reconstruct_threads(self, transcript: SessionTranscript) -> List[ConversationThread]:
        """
        Reconstruye la llamada completa agrupándola en hilos conversacionales estructurados.
        """
        utterances = transcript.utterances
        if not utterances:
            return []

        # Cache de alias por usuario
        user_aliases_map: Dict[str, Set[str]] = {}
        for u in utterances:
            if u.user_id not in user_aliases_map:
                user_aliases_map[u.user_id] = self._get_user_aliases(u.user_id, u.username)

        # Construir Grafo Dirigido con NetworkX
        dag = nx.DiGraph()
        for idx, u in enumerate(utterances):
            u_id = f"u_{idx}"
            dag.add_node(u_id, utterance=u, original_idx=idx)

        # Enlazar cada intervención con su padre más probable
        parent_links: Dict[int, Tuple[int, float]] = {}

        for j in range(1, len(utterances)):
            curr_u = utterances[j]
            best_prev_idx = None
            best_score = 0.0

            # Buscar hacia atrás en ventana temporal
            for i in range(j - 1, -1, -1):
                prev_u = utterances[i]
                if curr_u.start_time - prev_u.end_time > self.max_gap_seconds:
                    break

                prev_aliases = user_aliases_map.get(prev_u.user_id, set())
                score = self._compute_adjacency_score(prev_u, curr_u, prev_aliases)
                if score > best_score:
                    best_score = score
                    best_prev_idx = i

            if best_prev_idx is not None and best_score >= self.min_connection_score:
                parent_links[j] = (best_prev_idx, best_score)
                dag.add_edge(f"u_{best_prev_idx}", f"u_{j}", weight=best_score)

        # Extraer componentes débilmente conexas (hilos conversacionales)
        undirected = dag.to_undirected()
        connected_components = list(nx.connected_components(undirected))

        threads: List[ConversationThread] = []

        # Ordenar componentes por tiempo de inicio del primer mensaje
        def get_comp_start(comp: Set[str]) -> float:
            indices = [dag.nodes[n]["original_idx"] for n in comp]
            return min(utterances[i].start_time for i in indices)

        connected_components.sort(key=get_comp_start)

        for thread_idx, comp in enumerate(connected_components, start=1):
            sorted_nodes = sorted(list(comp), key=lambda n: dag.nodes[n]["original_idx"])
            comp_indices = [dag.nodes[n]["original_idx"] for n in sorted_nodes]

            turns: List[TurnRef] = []
            participants: Set[str] = set()
            texts: List[str] = []

            for idx in comp_indices:
                u = utterances[idx]
                participants.add(u.username)
                texts.append(u.text)

                parent_info = parent_links.get(idx)
                parent_uid = f"u_{parent_info[0]}" if parent_info else None
                conf = parent_info[1] if parent_info else 0.0

                turns.append(
                    TurnRef(
                        utterance_id=f"u_{idx}",
                        user_id=u.user_id,
                        username=u.username,
                        start_time=u.start_time,
                        end_time=u.end_time,
                        text=u.text,
                        reply_to_utterance_id=parent_uid,
                        reply_confidence=round(conf, 2),
                    )
                )

            start_t = turns[0].start_time
            end_t = max(t.end_time for t in turns)
            duration = round(end_t - start_t, 2)

            keywords = self.topic_detector.extract_keywords(texts)
            intent = self.topic_detector.classify_thread_intent(texts)

            threads.append(
                ConversationThread(
                    thread_id=str(thread_idx),
                    start_time=round(start_t, 2),
                    end_time=round(end_t, 2),
                    duration_seconds=duration,
                    participants=sorted(list(participants)),
                    turns=turns,
                    keywords=keywords,
                    intent=intent,
                )
            )

        return threads
