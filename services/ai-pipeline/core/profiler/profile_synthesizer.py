"""
Motor de Síntesis y Actualización Incremental Multisesión (Profile Synthesizer).
Implementa la ecuación de promedio ponderado continuo:
Score_new = ((Score_prev * N) + Score_session) / (N + 1)
Preserva citas históricas de evidencia y vincula muestras de voz limpias (Contrato C).
"""

from __future__ import annotations

import glob
import os
from datetime import datetime, timezone
from typing import List, Optional

from core.contracts.models import (
    BigFiveTraits,
    CommunicationStyle,
    DialectMarkers,
    EvidenceQuote,
    GroupRole,
    SessionTranscript,
    TraitEvaluation,
    UserProfile,
)
from core.profiler.gemini_analyzer import GeminiSessionEvaluation
from core.profiler.metrics import ConversationalMetrics


def running_avg(prev_val: float, new_val: float, n_prev: int, min_alpha: float = 0.05) -> float:
    """
    Calcula el promedio ponderado continuo adaptativo para seguimiento longitudinal (> 1 mes).
    - Primeras sesiones (N < 20): peso proporcional 1/(N+1) para calibración rápida.
    - Sesiones avanzadas (N >= 20): peso acotado en min_alpha (5%) para mantener estabilidad
      sin congelar la capacidad de adaptación a evoluciones sutiles de conducta.
    """
    if n_prev <= 0:
        return new_val
    alpha = max(min_alpha, 1.0 / (n_prev + 1))
    return round((1.0 - alpha) * prev_val + alpha * new_val, 3)


def calculate_accumulated_confidence(prev_conf: float, new_conf: float, n_total: int) -> float:
    """
    Modela el incremento bayesiano de certeza conforme se acumulan sesiones (> 1 mes):
    Conf(N) satura asintóticamente hacia 0.99 conforme aumenta la muestra de datos observados.
    """
    if n_total <= 1:
        return round(new_conf, 3)
    base = ((prev_conf * (n_total - 1)) + new_conf) / n_total
    # Bonificación por saturación empírica en muestreo longitudinal
    saturation_boost = 0.12 * (1.0 - (0.90 ** (n_total - 1)))
    return round(min(0.99, base + saturation_boost), 3)


def merge_evidence_quotes(
    prev_quotes: List[EvidenceQuote],
    new_quotes_str: List[str],
    session_id: str,
    max_quotes: int = 10,
) -> List[EvidenceQuote]:
    """Combina citas previas con las nuevas citas de la sesión, evitando duplicados (hasta 10 citas)."""
    seen_texts = {q.quote.strip() for q in prev_quotes}
    merged = list(prev_quotes)

    for text in new_quotes_str:
        clean = text.strip()
        if clean and clean not in seen_texts:
            seen_texts.add(clean)
            merged.append(
                EvidenceQuote(
                    quote=clean,
                    session_id=session_id,
                    timestamp=session_id,
                )
            )

    return merged[:max_quotes]


class ProfileSynthesizer:
    def __init__(self, storage_dir: str):
        self.storage_dir = os.path.abspath(storage_dir)
        self.profiles_dir = os.path.join(self.storage_dir, "profiles")
        self.clean_samples_dir = os.path.join(self.storage_dir, "clean_samples")
        os.makedirs(self.profiles_dir, exist_ok=True)

    def load_existing_profile(self, user_id: str) -> Optional[UserProfile]:
        """Carga el perfil acumulado previo si existe en disco."""
        profile_path = os.path.join(self.profiles_dir, user_id, "profile.json")
        if not os.path.exists(profile_path):
            return None
        with open(profile_path, "r", encoding="utf-8") as f:
            return UserProfile.model_validate_json(f.read())

    def discover_clean_samples(self, user_id: str) -> List[str]:
        """Detecta muestras de voz limpias disponibles en storage/clean_samples/<user_id>/."""
        user_samples_dir = os.path.join(self.clean_samples_dir, user_id)
        if not os.path.exists(user_samples_dir):
            return []
        wav_files = glob.glob(os.path.join(user_samples_dir, "*.wav"))
        rel_paths = [os.path.relpath(p, self.storage_dir).replace("\\", "/") for p in wav_files]
        return sorted(rel_paths)

    def synthesize_profile(
        self,
        user_id: str,
        username: str,
        session_id: str,
        session_metrics: ConversationalMetrics,
        evaluation: GeminiSessionEvaluation,
    ) -> UserProfile:
        """
        Sintetiza la evaluación de una sesión con el historial acumulado del usuario.
        """
        existing = self.load_existing_profile(user_id)
        clean_samples = self.discover_clean_samples(user_id)
        now = datetime.now(timezone.utc)

        if existing is None:
            # Caso 1: Primera sesión analizada para este usuario (N = 0 -> N = 1)
            big_five = BigFiveTraits(
                openness=TraitEvaluation(
                    score=evaluation.openness_score,
                    confidence=evaluation.openness_confidence,
                    evidence_quotes=merge_evidence_quotes([], evaluation.openness_evidence, session_id),
                ),
                conscientiousness=TraitEvaluation(
                    score=evaluation.conscientiousness_score,
                    confidence=evaluation.conscientiousness_confidence,
                    evidence_quotes=merge_evidence_quotes([], evaluation.conscientiousness_evidence, session_id),
                ),
                extraversion=TraitEvaluation(
                    score=evaluation.extraversion_score,
                    confidence=evaluation.extraversion_confidence,
                    evidence_quotes=merge_evidence_quotes([], evaluation.extraversion_evidence, session_id),
                ),
                agreeableness=TraitEvaluation(
                    score=evaluation.agreeableness_score,
                    confidence=evaluation.agreeableness_confidence,
                    evidence_quotes=merge_evidence_quotes([], evaluation.agreeableness_evidence, session_id),
                ),
                neuroticism=TraitEvaluation(
                    score=evaluation.neuroticism_score,
                    confidence=evaluation.neuroticism_confidence,
                    evidence_quotes=merge_evidence_quotes([], evaluation.neuroticism_evidence, session_id),
                ),
            )

            comm_style = CommunicationStyle(
                avg_words_per_turn=session_metrics.avg_words_per_turn,
                cadence=session_metrics.cadence,
                interruption_ratio=session_metrics.interruption_ratio,
                humor_type=evaluation.humor_type,
            )

            group_role = GroupRole(
                primary_role=evaluation.primary_role,
                description=evaluation.role_description,
                conflict_style=evaluation.conflict_style,
            )

            dialect_markers = DialectMarkers(
                rioplatense_frequency=evaluation.rioplatense_frequency,
                favorite_slang=list(dict.fromkeys(evaluation.favorite_slang)),
                discourse_fillers=list(dict.fromkeys(evaluation.discourse_fillers)),
            )

            profile = UserProfile(
                version="1.0.0",
                user_id=user_id,
                username=username,
                last_updated=now,
                total_sessions_analyzed=1,
                total_speaking_seconds=round(session_metrics.total_speaking_seconds, 2),
                big_five=big_five,
                communication_style=comm_style,
                group_role=group_role,
                dialect_markers=dialect_markers,
                clean_voice_samples=clean_samples,
            )
        else:
            # Caso 2: Sesión N (actualización incremental continua)
            n_prev = existing.total_sessions_analyzed

            # 1. Big Five ponderado con bonificación de confianza por acumulación
            def update_trait(prev_t: TraitEvaluation, new_score: float, new_conf: float, new_quotes: List[str]):
                score = running_avg(prev_t.score, new_score, n_prev)
                conf = calculate_accumulated_confidence(prev_t.confidence, new_conf, n_prev + 1)
                quotes = merge_evidence_quotes(prev_t.evidence_quotes, new_quotes, session_id, max_quotes=10)
                return TraitEvaluation(score=score, confidence=conf, evidence_quotes=quotes)

            big_five = BigFiveTraits(
                openness=update_trait(
                    existing.big_five.openness,
                    evaluation.openness_score,
                    evaluation.openness_confidence,
                    evaluation.openness_evidence,
                ),
                conscientiousness=update_trait(
                    existing.big_five.conscientiousness,
                    evaluation.conscientiousness_score,
                    evaluation.conscientiousness_confidence,
                    evaluation.conscientiousness_evidence,
                ),
                extraversion=update_trait(
                    existing.big_five.extraversion,
                    evaluation.extraversion_score,
                    evaluation.extraversion_confidence,
                    evaluation.extraversion_evidence,
                ),
                agreeableness=update_trait(
                    existing.big_five.agreeableness,
                    evaluation.agreeableness_score,
                    evaluation.agreeableness_confidence,
                    evaluation.agreeableness_evidence,
                ),
                neuroticism=update_trait(
                    existing.big_five.neuroticism,
                    evaluation.neuroticism_score,
                    evaluation.neuroticism_confidence,
                    evaluation.neuroticism_evidence,
                ),
            )

            # 2. Métricas comunicativas ponderadas
            avg_words = running_avg(existing.communication_style.avg_words_per_turn, session_metrics.avg_words_per_turn, n_prev)
            interruption = running_avg(existing.communication_style.interruption_ratio, session_metrics.interruption_ratio, n_prev)

            comm_style = CommunicationStyle(
                avg_words_per_turn=avg_words,
                cadence=session_metrics.cadence,  # Cadencia observada recientemente
                interruption_ratio=interruption,
                humor_type=evaluation.humor_type,
            )

            # 3. Rol grupal
            group_role = GroupRole(
                primary_role=evaluation.primary_role,
                description=evaluation.role_description,
                conflict_style=evaluation.conflict_style,
            )

            # 4. Dialecto ponderado y unión de jergas
            rioplatense_freq = running_avg(existing.dialect_markers.rioplatense_frequency, evaluation.rioplatense_frequency, n_prev)
            merged_slang = list(dict.fromkeys(existing.dialect_markers.favorite_slang + evaluation.favorite_slang))
            merged_fillers = list(dict.fromkeys(existing.dialect_markers.discourse_fillers + evaluation.discourse_fillers))

            dialect_markers = DialectMarkers(
                rioplatense_frequency=rioplatense_freq,
                favorite_slang=merged_slang,
                discourse_fillers=merged_fillers,
            )

            # 5. Muestras combinadas
            all_samples = sorted(list(set(existing.clean_voice_samples + clean_samples)))

            profile = UserProfile(
                version="1.0.0",
                user_id=user_id,
                username=username,
                display_name=existing.display_name,
                nicknames=existing.nicknames,
                notes=existing.notes,
                last_updated=now,
                total_sessions_analyzed=n_prev + 1,
                total_speaking_seconds=round(existing.total_speaking_seconds + session_metrics.total_speaking_seconds, 2),
                big_five=big_five,
                communication_style=comm_style,
                group_role=group_role,
                dialect_markers=dialect_markers,
                clean_voice_samples=all_samples,
            )

        # Guardado atómico en storage/profiles/<user_id>/profile.json
        user_dir = os.path.join(self.profiles_dir, user_id)
        os.makedirs(user_dir, exist_ok=True)
        dest_file = os.path.join(user_dir, "profile.json")
        profile.save_atomic(dest_file)

        return profile
