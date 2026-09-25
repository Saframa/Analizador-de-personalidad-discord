"""
Modelos de Datos y Contratos Formales (Pydantic v2)
Correspondientes a los JSON Schemas Draft-07 de docs/specs/
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


# ==============================================================================
# CONTRATO A: session_metadata.schema.json
# ==============================================================================

class ParticipantInfo(BaseModel):
    user_id: str = Field(..., min_length=1, description="ID único de usuario de Discord")
    username: str = Field(..., min_length=1, description="Nombre de usuario de Discord")
    display_name: str = Field(..., min_length=1, description="Apodo o nombre visible en el servidor")
    joined_at: datetime = Field(..., description="Timestamp ISO 8601 de ingreso al canal")
    left_at: Optional[datetime] = Field(None, description="Timestamp ISO 8601 de salida o None")


class AudioFileInfo(BaseModel):
    filename: str = Field(..., min_length=1, description="Ruta relativa del archivo de audio")
    sample_rate: Literal[48000] = Field(48000, description="Frecuencia de muestreo estándar de Discord")
    channels: Literal[1, 2] = Field(..., description="1 para Mono, 2 para Estéreo")
    format: Literal["pcm_s16le", "wav", "ogg_opus"] = Field(..., description="Formato de codificación")
    size_bytes: int = Field(..., ge=0, description="Tamaño del archivo en bytes")


class SessionMetadata(BaseModel):
    version: Literal["1.0.0"] = Field("1.0.0", description="Versión semántica del contrato")
    session_id: str = Field(..., description="Formato YYYY-MM-DD_HH-mm-ss")
    guild_id: str = Field(..., min_length=1)
    channel_id: str = Field(..., min_length=1)
    channel_name: str = Field(..., min_length=1)
    started_at: datetime
    ended_at: datetime
    duration_seconds: float = Field(..., ge=0.0)
    participants: List[ParticipantInfo] = Field(..., min_length=1)
    audio_files: Dict[str, AudioFileInfo]

    @field_validator("session_id")
    @classmethod
    def validate_session_id_format(cls, v: str) -> str:
        pattern = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}$"
        if not re.match(pattern, v):
            raise ValueError(f"session_id '{v}' no cumple el patrón YYYY-MM-DD_HH-mm-ss")
        return v

    def save_atomic(self, file_path: str) -> None:
        """Guarda el archivo JSON de forma atómica usando un archivo temporal (.tmp)."""
        temp_path = f"{file_path}.tmp"
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))
        os.replace(temp_path, file_path)


# ==============================================================================
# CONTRATO B: transcript.schema.json
# ==============================================================================

class Utterance(BaseModel):
    id: int = Field(..., ge=1, description="ID incremental en la sesión")
    user_id: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    start_time: float = Field(..., ge=0.0, description="Segundos desde el inicio de la sesión")
    end_time: float = Field(..., ge=0.0, description="Segundos desde el inicio de la sesión")
    duration: float = Field(..., ge=0.0)
    text: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    audio_segment_path: Optional[str] = None
    overlapping_speakers: List[str] = Field(default_factory=list)


class SessionTranscript(BaseModel):
    version: Literal["1.0.0"] = Field("1.0.0")
    session_id: str = Field(..., min_length=1)
    processed_at: datetime
    model: str = Field(..., min_length=1, description="Modelo STT utilizado")
    utterances: List[Utterance] = Field(default_factory=list)

    def save_atomic(self, file_path: str) -> None:
        temp_path = f"{file_path}.tmp"
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))
        os.replace(temp_path, file_path)


# ==============================================================================
# CONTRATO C: user_profile.schema.json
# ==============================================================================

class EvidenceQuote(BaseModel):
    quote: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    timestamp: str = Field(..., min_length=1)


class TraitEvaluation(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_quotes: List[EvidenceQuote] = Field(default_factory=list)


class BigFiveTraits(BaseModel):
    openness: TraitEvaluation
    conscientiousness: TraitEvaluation
    extraversion: TraitEvaluation
    agreeableness: TraitEvaluation
    neuroticism: TraitEvaluation


class CommunicationStyle(BaseModel):
    avg_words_per_turn: float = Field(..., ge=0.0)
    cadence: Literal["rapido", "pausado", "irregular", "moderado"]
    interruption_ratio: float = Field(..., ge=0.0, le=1.0)
    humor_type: str = Field(..., min_length=1)


class GroupRole(BaseModel):
    primary_role: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    conflict_style: str = Field(..., min_length=1)


class DialectMarkers(BaseModel):
    rioplatense_frequency: float = Field(..., ge=0.0, le=1.0)
    favorite_slang: List[str] = Field(default_factory=list)
    discourse_fillers: List[str] = Field(default_factory=list)
    vocabulary_frequencies: Dict[str, int] = Field(
        default_factory=dict,
        description="Diccionario acumulativo de frecuencia de palabras (Idiolecto ponderado)",
    )


class InterlocutorAffinity(BaseModel):
    user_id: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    interaction_count: int = Field(default=0, ge=0)
    reply_count: int = Field(default=0, ge=0)
    affinity_score: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: Optional[str] = None


class SocialDynamics(BaseModel):
    affinities: Dict[str, InterlocutorAffinity] = Field(default_factory=dict)
    closest_friends: List[str] = Field(default_factory=list)
    teasing_targets: List[str] = Field(default_factory=list)


class GroupLore(BaseModel):
    inside_jokes: List[str] = Field(default_factory=list)
    external_entities: List[str] = Field(default_factory=list)
    notable_anecdotes: List[str] = Field(default_factory=list)


class EmotionalTriggers(BaseModel):
    tilts: List[str] = Field(default_factory=list)
    hyperfocus_topics: List[str] = Field(default_factory=list)


class ActivityInitiative(BaseModel):
    initiative_level: Literal["iniciador", "seguidor", "neutro"] = "neutro"
    proposes_activities: bool = False
    departure_pattern: Literal["tempranero", "noctambulo_extremo", "variable"] = "variable"
    typical_proposals: List[str] = Field(default_factory=list)


class TemporalPatterns(BaseModel):
    cronotype: Literal["madrugador", "vespertino", "noctambulo"] = "vespertino"
    peak_hours: List[str] = Field(default_factory=list)
    late_night_attitude: Optional[str] = None


class UserProfile(BaseModel):
    version: Literal["1.0.0"] = Field("1.0.0")
    user_id: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    last_updated: datetime
    total_sessions_analyzed: int = Field(..., ge=1)
    total_speaking_seconds: float = Field(..., ge=0.0)
    big_five: BigFiveTraits
    communication_style: CommunicationStyle
    group_role: GroupRole
    dialect_markers: DialectMarkers
    clean_voice_samples: List[str] = Field(default_factory=list)
    display_name: Optional[str] = None
    nicknames: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    social_dynamics: SocialDynamics = Field(default_factory=SocialDynamics)
    group_lore: GroupLore = Field(default_factory=GroupLore)
    emotional_triggers: EmotionalTriggers = Field(default_factory=EmotionalTriggers)
    activity_initiative: ActivityInitiative = Field(default_factory=ActivityInitiative)
    temporal_patterns: TemporalPatterns = Field(default_factory=TemporalPatterns)

    def save_atomic(self, file_path: str) -> None:
        temp_path = f"{file_path}.tmp"
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))
        os.replace(temp_path, file_path)

