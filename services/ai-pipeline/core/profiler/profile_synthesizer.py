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
from typing import Dict, List, Optional

from core.contracts.models import (
    ActivityInitiative,
    BigFiveTraits,
    CommunicationStyle,
    DialectMarkers,
    EmotionalTriggers,
    EvidenceQuote,
    GroupLore,
    GroupRole,
    InterlocutorAffinity,
    SessionTranscript,
    SocialDynamics,
    TemporalPatterns,
    TraitEvaluation,
    UserProfile,
)
from core.profiler.gemini_analyzer import GeminiSessionEvaluation
from core.profiler.metrics import ConversationalMetrics, SessionSocialTemporalMetrics



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


def merge_unique_strings(existing_list: List[str], new_list: List[str], max_items: int = 15) -> List[str]:
    """Combina listas preservando orden y eliminando duplicados case-insensitive."""
    seen = set()
    result = []
    for item in existing_list + new_list:
        clean = item.strip()
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            result.append(clean)
    return result[:max_items]


def synthesize_social_dynamics(
    prev_dynamics: Optional[SocialDynamics],
    evaluation: GeminiSessionEvaluation,
    social_temporal_metrics: Optional[SessionSocialTemporalMetrics],
) -> SocialDynamics:
    """Sintetiza la matriz de afinidad con otros miembros y objetivos de chicanas."""
    affinities = dict(prev_dynamics.affinities) if prev_dynamics else {}

    if social_temporal_metrics:
        for p_id, p_info in social_temporal_metrics.peer_interactions.items():
            if p_id in affinities:
                aff = affinities[p_id]
                new_interactions = aff.interaction_count + p_info["interactions"]
                new_replies = aff.reply_count + p_info.get("replies_to", 0)
                score = round(min(0.98, max(0.40, 0.45 + (new_interactions * 0.05))), 2)
                affinities[p_id] = InterlocutorAffinity(
                    user_id=p_id,
                    username=p_info["username"],
                    interaction_count=new_interactions,
                    reply_count=new_replies,
                    affinity_score=score,
                    notes=aff.notes,
                )
            else:
                inter_count = p_info["interactions"]
                score = round(min(0.98, max(0.40, 0.45 + (inter_count * 0.05))), 2)
                affinities[p_id] = InterlocutorAffinity(
                    user_id=p_id,
                    username=p_info["username"],
                    interaction_count=inter_count,
                    reply_count=p_info.get("replies_to", 0),
                    affinity_score=score,
                )

    prev_closest = prev_dynamics.closest_friends if prev_dynamics else []
    prev_teasing = prev_dynamics.teasing_targets if prev_dynamics else []

    closest = merge_unique_strings(prev_closest, evaluation.closest_friends, max_items=6)
    teasing = merge_unique_strings(prev_teasing, evaluation.teasing_targets, max_items=6)

    return SocialDynamics(
        affinities=affinities,
        closest_friends=closest,
        teasing_targets=teasing,
    )


def synthesize_group_lore(
    prev_lore: Optional[GroupLore],
    evaluation: GeminiSessionEvaluation,
) -> GroupLore:
    """Sintetiza chistes internos, entidades externas y anécdotas compartidas."""
    prev_jokes = prev_lore.inside_jokes if prev_lore else []
    prev_entities = prev_lore.external_entities if prev_lore else []
    prev_anecdotes = prev_lore.notable_anecdotes if prev_lore else []

    return GroupLore(
        inside_jokes=merge_unique_strings(prev_jokes, evaluation.inside_jokes, max_items=15),
        external_entities=merge_unique_strings(prev_entities, evaluation.external_entities, max_items=15),
        notable_anecdotes=merge_unique_strings(prev_anecdotes, evaluation.notable_anecdotes, max_items=10),
    )


def synthesize_emotional_triggers(
    prev_triggers: Optional[EmotionalTriggers],
    evaluation: GeminiSessionEvaluation,
) -> EmotionalTriggers:
    """Sintetiza disparadores de quejas/tilteo y temas de hiperfoco apasionado."""
    prev_tilts = prev_triggers.tilts if prev_triggers else []
    prev_hyper = prev_triggers.hyperfocus_topics if prev_triggers else []

    return EmotionalTriggers(
        tilts=merge_unique_strings(prev_tilts, evaluation.tilts, max_items=10),
        hyperfocus_topics=merge_unique_strings(prev_hyper, evaluation.hyperfocus_topics, max_items=10),
    )


def synthesize_activity_initiative(
    prev_init: Optional[ActivityInitiative],
    evaluation: GeminiSessionEvaluation,
) -> ActivityInitiative:
    """Sintetiza nivel de iniciativa en juegos y permanencia en la llamada."""
    prev_proposals = prev_init.typical_proposals if prev_init else []
    proposals = merge_unique_strings(prev_proposals, evaluation.typical_proposals, max_items=8)

    is_initiator = (
        evaluation.initiative_level == "iniciador"
        or (prev_init is not None and prev_init.initiative_level == "iniciador")
    )
    init_level = "iniciador" if is_initiator else evaluation.initiative_level

    proposes = (prev_init.proposes_activities if prev_init else False) or evaluation.proposes_activities
    departure = prev_init.departure_pattern if prev_init else "variable"

    return ActivityInitiative(
        initiative_level=init_level,
        proposes_activities=proposes,
        departure_pattern=departure,
        typical_proposals=proposals,
    )


def synthesize_temporal_patterns(
    prev_temporal: Optional[TemporalPatterns],
    evaluation: GeminiSessionEvaluation,
    social_temporal_metrics: Optional[SessionSocialTemporalMetrics],
) -> TemporalPatterns:
    """Sintetiza cronotipo, horarios pico y comportamiento de madrugada."""
    prev_peaks = prev_temporal.peak_hours if prev_temporal else []
    new_peaks = [social_temporal_metrics.hour_category] if social_temporal_metrics else []
    peaks = merge_unique_strings(prev_peaks, new_peaks, max_items=4)

    cronotype = prev_temporal.cronotype if prev_temporal else "vespertino"
    if social_temporal_metrics:
        h = social_temporal_metrics.session_hour
        if 0 <= h < 6:
            cronotype = "noctambulo"
        elif 6 <= h < 14:
            cronotype = "madrugador"
        else:
            cronotype = "vespertino"

    attitude = evaluation.late_night_attitude or (prev_temporal.late_night_attitude if prev_temporal else None)

    return TemporalPatterns(
        cronotype=cronotype,
        peak_hours=peaks,
        late_night_attitude=attitude,
    )


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
        social_temporal_metrics: Optional[SessionSocialTemporalMetrics] = None,
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

            session_vocab = getattr(session_metrics, "session_vocabulary", {}) or {}
            sorted_vocab = dict(sorted(session_vocab.items(), key=lambda x: x[1], reverse=True)[:500])

            dialect_markers = DialectMarkers(
                rioplatense_frequency=evaluation.rioplatense_frequency,
                favorite_slang=list(dict.fromkeys(evaluation.favorite_slang)),
                discourse_fillers=list(dict.fromkeys(evaluation.discourse_fillers)),
                vocabulary_frequencies=sorted_vocab,
            )

            social_dyn = synthesize_social_dynamics(None, evaluation, social_temporal_metrics)
            group_lore = synthesize_group_lore(None, evaluation)
            emot_triggers = synthesize_emotional_triggers(None, evaluation)
            activity_init = synthesize_activity_initiative(None, evaluation)
            temp_patterns = synthesize_temporal_patterns(None, evaluation, social_temporal_metrics)

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
                social_dynamics=social_dyn,
                group_lore=group_lore,
                emotional_triggers=emot_triggers,
                activity_initiative=activity_init,
                temporal_patterns=temp_patterns,
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

            # 4. Dialecto ponderado, unión de jergas y acumulación de idiolecto
            rioplatense_freq = running_avg(existing.dialect_markers.rioplatense_frequency, evaluation.rioplatense_frequency, n_prev)
            merged_slang = list(dict.fromkeys(existing.dialect_markers.favorite_slang + evaluation.favorite_slang))
            merged_fillers = list(dict.fromkeys(existing.dialect_markers.discourse_fillers + evaluation.discourse_fillers))

            session_vocab = getattr(session_metrics, "session_vocabulary", {}) or {}
            total_vocab = dict(existing.dialect_markers.vocabulary_frequencies or {})
            for word, count in session_vocab.items():
                total_vocab[word] = total_vocab.get(word, 0) + count

            sorted_vocab = dict(sorted(total_vocab.items(), key=lambda x: x[1], reverse=True)[:500])

            dialect_markers = DialectMarkers(
                rioplatense_frequency=rioplatense_freq,
                favorite_slang=merged_slang,
                discourse_fillers=merged_fillers,
                vocabulary_frequencies=sorted_vocab,
            )

            # 5. Muestras combinadas
            all_samples = sorted(list(set(existing.clean_voice_samples + clean_samples)))

            # 6. Nuevas dimensiones comportamentales
            social_dyn = synthesize_social_dynamics(existing.social_dynamics, evaluation, social_temporal_metrics)
            group_lore = synthesize_group_lore(existing.group_lore, evaluation)
            emot_triggers = synthesize_emotional_triggers(existing.emotional_triggers, evaluation)
            activity_init = synthesize_activity_initiative(existing.activity_initiative, evaluation)
            temp_patterns = synthesize_temporal_patterns(existing.temporal_patterns, evaluation, social_temporal_metrics)

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
                social_dynamics=social_dyn,
                group_lore=group_lore,
                emotional_triggers=emot_triggers,
                activity_initiative=activity_init,
                temporal_patterns=temp_patterns,
            )

        # Guardado atómico en storage/profiles/<user_id>/profile.json
        user_dir = os.path.join(self.profiles_dir, user_id)
        os.makedirs(user_dir, exist_ok=True)
        dest_file = os.path.join(user_dir, "profile.json")
        profile.save_atomic(dest_file)

        return profile
