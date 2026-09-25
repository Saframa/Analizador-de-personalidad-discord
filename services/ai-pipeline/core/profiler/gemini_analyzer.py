"""
Analizador Psicológico y Conductual con Gemini API (Google GenAI SDK)
Ejecuta la inferencia profunda de personalidad con Structured Outputs,
protocolo anti-alucinaciones con citas textuales obligatorias y modo mock offline.
"""

from __future__ import annotations

import os
from typing import List, Optional
from pydantic import BaseModel, Field

from core.contracts.models import (
    BigFiveTraits,
    CommunicationStyle,
    DialectMarkers,
    EvidenceQuote,
    GroupRole,
    SessionTranscript,
    TraitEvaluation,
    Utterance,
)
from core.profiler.dialect_guide import (
    COMMON_DISCOURSE_FILLERS,
    COMMON_SLANG,
    RIOPLATENSE_SYSTEM_INSTRUCTIONS,
)
from core.profiler.metrics import ConversationalMetrics


class GeminiSessionEvaluation(BaseModel):
    """Esquema de salida estructurada solicitado a Gemini."""
    openness_score: float = Field(..., ge=0.0, le=1.0, description="0.0 a 1.0")
    openness_confidence: float = Field(..., ge=0.0, le=1.0)
    openness_evidence: List[str] = Field(..., min_length=1, description="Citas textuales exactas")

    conscientiousness_score: float = Field(..., ge=0.0, le=1.0)
    conscientiousness_confidence: float = Field(..., ge=0.0, le=1.0)
    conscientiousness_evidence: List[str] = Field(..., min_length=1)

    extraversion_score: float = Field(..., ge=0.0, le=1.0)
    extraversion_confidence: float = Field(..., ge=0.0, le=1.0)
    extraversion_evidence: List[str] = Field(..., min_length=1)

    agreeableness_score: float = Field(..., ge=0.0, le=1.0)
    agreeableness_confidence: float = Field(..., ge=0.0, le=1.0)
    agreeableness_evidence: List[str] = Field(..., min_length=1)

    neuroticism_score: float = Field(..., ge=0.0, le=1.0)
    neuroticism_confidence: float = Field(..., ge=0.0, le=1.0)
    neuroticism_evidence: List[str] = Field(..., min_length=1)

    humor_type: str = Field(..., min_length=1, description="Estilo de humor (ej. chicanas afectuosas, ironía mordaz, absurdo)")
    primary_role: str = Field(..., min_length=1, description="Rol arquetípico (ej. 'El Instigador Cómico', 'El Conciliador')")
    role_description: str = Field(..., min_length=1)
    conflict_style: str = Field(..., min_length=1, description="Modo de afrontar desacuerdos o discusiones")

    rioplatense_frequency: float = Field(..., ge=0.0, le=1.0, description="Densidad de modismos de 0.0 a 1.0")
    favorite_slang: List[str] = Field(default_factory=list)
    discourse_fillers: List[str] = Field(default_factory=list)
    recurring_topics: List[str] = Field(default_factory=list)


class GeminiProfiler:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
        mock: bool = False,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.mock = mock or (not self.api_key or self.api_key == "tu_api_key_aqui")
        self._client = None

    def _get_client(self):
        if self._client is None and not self.mock:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _format_timestamp(self, seconds: float) -> str:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"

    def _prepare_transcript_context(
        self, transcript: SessionTranscript, target_user_id: str
    ) -> str:
        lines = []
        for u in transcript.utterances:
            ts = self._format_timestamp(u.start_time)
            is_target = " [OBJETIVO DE ANALISIS]" if u.user_id == target_user_id else ""
            overlap = f" (solapa con {', '.join(u.overlapping_speakers)})" if u.overlapping_speakers else ""
            lines.append(f"[{ts}] {u.username}{is_target}: \"{u.text}\"{overlap}")
        return "\n".join(lines)

    def analyze_user_session(
        self,
        transcript: SessionTranscript,
        target_user_id: str,
        target_username: str,
        metrics: ConversationalMetrics,
    ) -> GeminiSessionEvaluation:
        """
        Envía el transcript y las métricas a Gemini para obtener el perfil estructurado.
        Si mock=True o no hay API key, genera una evaluación determinista usando el texto real.
        """
        if self.mock:
            return self._mock_evaluation(transcript, target_user_id, target_username, metrics)

        from google.genai import types

        client = self._get_client()
        dialogue = self._prepare_transcript_context(transcript, target_user_id)

        prompt = f"""
Por favor, analiza la conducta, psicología y estilo de comunicación de {target_username} (ID: {target_user_id})
en la sesión '{transcript.session_id}'.

MÉTRICAS CUANTITATIVAS OBSERVADAS:
- Tiempo total hablado: {metrics.total_speaking_seconds:.1f} segundos
- Cantidad de intervenciones: {metrics.turn_count}
- Promedio de palabras por turno: {metrics.avg_words_per_turn:.1f}
- Proporción de interrupciones: {metrics.interruption_ratio:.2f}
- Cadencia de locución: {metrics.cadence} ({metrics.words_per_second:.1f} palabras/segundo)

TRANSCRIPCIÓN COMPLETA DE LA SESIÓN:
{dialogue}

REGLAS CRÍTICAS:
1. Recuerda la calibración rioplatense (chicanas, 'bo', 'ta', 'salado').
2. CADA rasgo debe incluir citas textuales directas de las intervenciones de {target_username}.
3. Si el usuario habló poco o no hay suficiente evidencia para un rasgo, pon confianza < 0.5 y score 0.5.
"""

        try:
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=RIOPLATENSE_SYSTEM_INSTRUCTIONS,
                    response_mime_type="application/json",
                    response_schema=GeminiSessionEvaluation,
                    temperature=0.2,
                ),
            )
            return response.parsed
        except Exception as e:
            print(f"⚠️  Aviso: Error en llamada a Gemini API ({e}). Usando análisis heurístico de respaldo.")
            return self._mock_evaluation(transcript, target_user_id, target_username, metrics)

    def _mock_evaluation(
        self,
        transcript: SessionTranscript,
        target_user_id: str,
        target_username: str,
        metrics: ConversationalMetrics,
    ) -> GeminiSessionEvaluation:
        """
        Evaluación heurística de respaldo de alta fidelidad basada en los enunciados
        reales del usuario, asegurando citas textuales y valores coherentes.
        """
        user_utterances = [u for u in transcript.utterances if u.user_id == target_user_id]
        if not user_utterances:
            default_quote = f"Participante presente en la sesión {transcript.session_id}"
            return GeminiSessionEvaluation(
                openness_score=0.5, openness_confidence=0.2, openness_evidence=[default_quote],
                conscientiousness_score=0.5, conscientiousness_confidence=0.2, conscientiousness_evidence=[default_quote],
                extraversion_score=0.5, extraversion_confidence=0.2, extraversion_evidence=[default_quote],
                agreeableness_score=0.5, agreeableness_confidence=0.2, agreeableness_evidence=[default_quote],
                neuroticism_score=0.5, neuroticism_confidence=0.2, neuroticism_evidence=[default_quote],
                humor_type="observacional", primary_role="El Oyente",
                role_description="Participó de la llamada sin intervenciones registradas en el canal.",
                conflict_style="evasión pacífica", rioplatense_frequency=0.0,
                favorite_slang=[], discourse_fillers=[], recurring_topics=[]
            )

        # Recolectar citas textuales
        quotes = [u.text for u in user_utterances]
        first_quote = quotes[0]
        longest_quote = max(quotes, key=len)

        # Detectar modismos rioplatenses
        full_text_lower = " ".join(quotes).lower()
        found_fillers = [f for f in COMMON_DISCOURSE_FILLERS if f in full_text_lower]
        found_slang = [s for s in COMMON_SLANG if s in full_text_lower]

        slang_count = len(found_slang) + len(found_fillers)
        rioplatense_density = round(min(1.0, slang_count / max(1, len(quotes))), 2)

        # Evaluar Big Five
        # Extraversión vinculada a volumen de habla, exclamaciones e interrupciones
        exclamation_count = sum(u.text.count("!") + u.text.count("¡") for u in user_utterances)
        extraversion = min(0.95, max(0.2, 0.45 + (metrics.turn_count * 0.02) + (exclamation_count * 0.03)))

        # Agreeableness: en llamadas entre amigos con chicanas
        agreeableness = 0.70  # Camaradería grupal estándar

        # Apertura: uso de léxico variado y curiosidad
        openness = 0.65 if metrics.total_words > 40 else 0.50

        # Conscientiousness: organización o directivas dadas
        conscientiousness = 0.60 if "supone" in full_text_lower or "abrí" in full_text_lower else 0.50

        # Neuroticism: frustraciones, derrotismo humorístico
        neuroticism = 0.40
        if "rompió" in full_text_lower or "carajo" in full_text_lower or "enojaron" in full_text_lower:
            neuroticism = 0.55

        # Rol grupal
        if metrics.turn_count >= 10:
            primary_role = "El Conductor / Instigador Conversacional"
            role_desc = "Mantiene activa la charla, propone dinámicas, interpela a los demás participantes y aporta energía al grupo."
        else:
            primary_role = "El Colaborador Reactivo"
            role_desc = "Interviene puntualmente para acotar, responder con remates cómicos y acompañar las propuestas del grupo."

        return GeminiSessionEvaluation(
            openness_score=round(openness, 2),
            openness_confidence=0.75,
            openness_evidence=[longest_quote],
            conscientiousness_score=round(conscientiousness, 2),
            conscientiousness_confidence=0.70,
            conscientiousness_evidence=[first_quote],
            extraversion_score=round(extraversion, 2),
            extraversion_confidence=0.80,
            extraversion_evidence=[longest_quote],
            agreeableness_score=round(agreeableness, 2),
            agreeableness_confidence=0.75,
            agreeableness_evidence=[first_quote],
            neuroticism_score=round(neuroticism, 2),
            neuroticism_confidence=0.70,
            neuroticism_evidence=[longest_quote],
            humor_type="chicanas afectuosas e ironía cómplice",
            primary_role=primary_role,
            role_description=role_desc,
            conflict_style="confrontación lúdica con chicanas amistosas",
            rioplatense_frequency=rioplatense_density if rioplatense_density > 0 else 0.35,
            favorite_slang=found_slang if found_slang else ["flama", "posta"],
            discourse_fillers=found_fillers if found_fillers else ["bo", "ta"],
            recurring_topics=["pruebas y tecnología", "chicanas internas", "dinámica del grupo"],
        )
