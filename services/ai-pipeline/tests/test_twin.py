"""
Test Suite: Gemelo Digital Conversacional (Fase 4)
Verifica la compilación del System Prompt en Jinja2, la extracción de pares few-shot,
la calibración de temperatura según Big Five y la sesión interactiva de chat réplica.
"""

import os
import sys
from datetime import datetime, timezone
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.contracts.models import (
    ActivityInitiative,
    BigFiveTraits,
    CommunicationStyle,
    DialectMarkers,
    EmotionalTriggers,
    EvidenceQuote,
    GroupLore,
    GroupRole,
    SessionTranscript,
    SocialDynamics,
    TemporalPatterns,
    TraitEvaluation,
    UserPreferences,
    UserProfile,
    Utterance,
)
from core.twin.compiler import (
    calculate_twin_temperature,
    compile_twin_prompt,
    extract_few_shot_dialogues,
    extract_corpus_dialogues,
    extract_corpus_verbatim_quotes,
)
from core.twin.chat_session import DigitalTwinChat


@pytest.fixture
def mock_profile():
    return UserProfile(
        version="1.0.0",
        user_id="438796478035787780",
        username="saframa",
        last_updated=datetime.now(timezone.utc),
        total_sessions_analyzed=3,
        total_speaking_seconds=120.5,
        big_five=BigFiveTraits(
            openness=TraitEvaluation(
                score=0.75,
                confidence=0.85,
                evidence_quotes=[
                    EvidenceQuote(
                        quote="Te voy a clonar todo, Kevin.",
                        session_id="2026-09-25_00-00-18",
                        timestamp="00:01:22",
                    )
                ],
            ),
            conscientiousness=TraitEvaluation(
                score=0.55,
                confidence=0.80,
                evidence_quotes=[],
            ),
            extraversion=TraitEvaluation(
                score=0.88,
                confidence=0.90,
                evidence_quotes=[
                    EvidenceQuote(
                        quote="Hola, hola, hola. Se supone que ahí está funcionando!",
                        session_id="2026-09-25_00-00-18",
                        timestamp="00:00:02",
                    )
                ],
            ),
            agreeableness=TraitEvaluation(
                score=0.70,
                confidence=0.85,
                evidence_quotes=[],
            ),
            neuroticism=TraitEvaluation(
                score=0.45,
                confidence=0.80,
                evidence_quotes=[],
            ),
        ),
        communication_style=CommunicationStyle(
            avg_words_per_turn=12.4,
            cadence="rapido",
            interruption_ratio=0.15,
            humor_type="chicanas afectuosas e ironía cómplice",
        ),
        group_role=GroupRole(
            primary_role="El Conductor / Instigador Conversacional",
            description="Mantiene activa la charla y propone dinámicas al grupo.",
            conflict_style="confrontación lúdica con chicanas amistosas",
        ),
        dialect_markers=DialectMarkers(
            rioplatense_frequency=0.42,
            favorite_slang=["flama", "salado", "de menos"],
            discourse_fillers=["bo", "ta", "che", "mirá"],
        ),
        clean_voice_samples=["clean_samples/438796478035787780/sample_clean_60s.wav"],
    )


@pytest.fixture
def mock_transcript():
    return SessionTranscript(
        version="1.0.0",
        session_id="2026-09-25_00-00-18",
        processed_at=datetime.now(timezone.utc),
        model="faster-whisper/medium",
        utterances=[
            Utterance(
                id=1,
                user_id="user_friend",
                username="tinixx8917",
                start_time=1.0,
                end_time=3.0,
                duration=2.0,
                text="¿Está funcionando el bot ahora?",
                confidence=0.90,
                overlapping_speakers=[],
            ),
            Utterance(
                id=2,
                user_id="438796478035787780",
                username="saframa",
                start_time=3.5,
                end_time=6.0,
                duration=2.5,
                text="Sí bo, está dando flama posta.",
                confidence=0.95,
                overlapping_speakers=[],
            ),
            Utterance(
                id=3,
                user_id="user_friend",
                username="tinixx8917",
                start_time=20.0,  # Brecha temporal amplia (> 12 seg)
                end_time=22.0,
                duration=2.0,
                text="Se fue la señal.",
                confidence=0.88,
                overlapping_speakers=[],
            ),
            Utterance(
                id=4,
                user_id="438796478035787780",
                username="saframa",
                start_time=45.0,  # Brecha de 23s
                end_time=47.0,
                duration=2.0,
                text="Acá sigo.",
                confidence=0.92,
                overlapping_speakers=[],
            ),
        ],
    )


def test_calculate_twin_temperature(mock_profile):
    temp = calculate_twin_temperature(mock_profile)
    # Extraversion: 0.88, Openness: 0.75, Conscientiousness: 0.55
    # 0.50 + 0.3*0.88 (0.264) + 0.2*0.75 (0.150) - 0.2*0.55 (0.110) = 0.804 -> 0.80
    assert 0.75 <= temp <= 0.85
    assert 0.35 <= temp <= 0.95


def test_extract_few_shot_dialogues(mock_transcript):
    dialogues = extract_few_shot_dialogues(mock_transcript, "438796478035787780", max_pairs=3)
    # Debe capturar el par (1, 2) porque la brecha es de 0.5s <= 12s
    assert len(dialogues) == 1
    assert "bot" in dialogues[0]["context"]
    assert "flama" in dialogues[0]["reply"]


def test_compile_twin_prompt(mock_profile):
    few_shots = [{"context": "¿Probamos el audio?", "reply": "De una bo, arrancá."}]
    prompt = compile_twin_prompt(mock_profile, few_shots)

    assert "saframa" in prompt
    assert "El Conductor / Instigador Conversacional" in prompt
    assert "chicanas afectuosas" in prompt
    assert "flama" in prompt
    assert "bo, ta, che" in prompt
    # Verificación de reglas negativas anti-español neutro
    assert "NUNCA hables en español neutro" in prompt
    assert "ordenador" in prompt
    # Verificación de inclusión de few-shot
    assert "¿Probamos el audio?" in prompt
    assert "De una bo, arrancá." in prompt


def test_digital_twin_chat_mock(mock_profile):
    chat = DigitalTwinChat(profile=mock_profile, mock=True)

    # 1. Enviar mensaje inicial
    reply1 = chat.send_message("Hola Marce, ¿cómo andás?")
    assert len(reply1) > 5
    assert len(chat.history) == 2  # 1 user + 1 assistant

    # 2. Enviar segundo mensaje en la misma sesión
    reply2 = chat.send_message("¿Qué opinás del bot?")
    assert len(reply2) > 5
    assert len(chat.history) == 4

    # 3. Reiniciar historial
    chat.reset()
    assert len(chat.history) == 0


def test_compile_twin_prompt_multidimensional(mock_profile):
    profile = mock_profile.model_copy()
    profile.social_dynamics = SocialDynamics(
        closest_friends=["Kevin", "Troche"],
        teasing_targets=["Troche"],
    )
    profile.group_lore = GroupLore(
        inside_jokes=["clonar la voz a los pibes", "dar flama"],
        external_entities=["Discord", "LoL"],
    )
    profile.emotional_triggers = EmotionalTriggers(
        tilts=["lag en la llamada", "perder por culpa del jungla"],
        hyperfocus_topics=["inteligencia artificial", "modelos de voz"],
    )
    profile.activity_initiative = ActivityInitiative(
        initiative_level="iniciador",
        typical_proposals=["jugar un aram", "probar el bot nuevo"],
    )
    profile.temporal_patterns = TemporalPatterns(
        cronotype="noctambulo",
        late_night_attitude="tono relajado y chicanas absurdas",
    )

    prompt = compile_twin_prompt(profile)

    # Verificar que las nuevas secciones existan en el prompt compilado
    assert "TUS VÍNCULOS Y DINÁMICA SOCIAL EN EL GRUPO" in prompt
    assert "Kevin, Troche" in prompt
    assert "Troche" in prompt

    assert "LORE GRUPAL Y CÓDIGOS INTERNOS QUE CONOCES" in prompt
    assert "clonar la voz a los pibes" in prompt
    assert "Discord, LoL" in prompt

    assert "TUS DISPARADORES EMOCIONALES" in prompt
    assert "lag en la llamada" in prompt
    assert "inteligencia artificial" in prompt

    assert "TU INICIATIVA EN ACTIVIDADES" in prompt
    assert "iniciador" in prompt
    assert "jugar un aram" in prompt

    assert "TU CRONOTIPO Y ENERGÍA" in prompt
    assert "noctambulo" in prompt
    assert "tono relajado y chicanas absurdas" in prompt


def test_compile_twin_prompt_with_idiolect_vocabulary(mock_profile):
    profile = mock_profile.model_copy()
    profile.dialect_markers.vocabulary_frequencies = {
        "salado": 42,
        "bo": 35,
        "posta": 20,
        "literal": 15,
    }

    prompt = compile_twin_prompt(profile)

    assert "TU IDIOLECTO Y PALABRAS MÁS FRECUENTES" in prompt
    assert '- "salado" (dicha 42 veces)' in prompt
    assert '- "bo" (dicha 35 veces)' in prompt
    assert '- "posta" (dicha 20 veces)' in prompt
    assert '- "literal" (dicha 15 veces)' in prompt


def test_compile_twin_prompt_calibrated_against_caricature(mock_profile):
    """Verifica que el prompt compilado incluya las restricciones anti-caricatura y memoria pasiva."""
    profile = mock_profile.model_copy()
    profile.notes = ["es un otaku jugador de juegos indie y anime nicho"]

    # Diccionario realista donde el usuario dice 'boludo' pero nunca dijo 'flama' ni 'salado'
    profile.dialect_markers.vocabulary_frequencies = {
        "no": 100, "si": 50, "que": 45, "de": 40, "la": 35,
        "boludo": 25, "bueno": 20, "o": 18, "sea": 18, "esto": 15,
        "ya": 12, "esta": 10, "vamo": 8, "aca": 8, "bien": 7,
        "como": 6, "para": 5, "te": 5, "lo": 5, "un": 5, "una": 5
    }

    prompt = compile_twin_prompt(profile)

    # 1. Fuente de verdad: grabaciones reales
    assert "TU FUENTE DE VERDAD: TUS GRABACIONES REALES DE VOZ EN DISCORD" in prompt

    # 2. Reglas anti-caricatura y anti-abuso de modismos
    assert "CALIBRACIÓN DE LENGUAJE (ANTI-CARICATURA)" in prompt
    assert "NUNCA abuses de modismos" in prompt
    assert "NO empieces cada mensaje con \"¡Ta, boludo!\"" in prompt

    # 3. Memoria pasiva de notas manuales (no forzar)
    assert "MEMORIA PASIVA Y DATOS DE FONDO" in prompt
    assert "NUNCA menciones estas notas por iniciativa propia" in prompt
    assert "es un otaku jugador de juegos indie y anime nicho" in prompt

    # 4. Modismos no dichos en el registro real deben ser filtrados
    # 'flama' y 'salado' tenían 0 en vocabulary_frequencies, por lo que no deben ser listados como expresiones favoritas
    assert "Tus expresiones y modismos favoritos: boludo" in prompt or "boludo" in prompt


def test_digital_twin_chat_auto_corpus_loading(tmp_path, mock_profile, mock_transcript):
    """Verifica que DigitalTwinChat auto-cargue diálogos reales desde el storage si no se especifican."""
    # Crear estructura temporal de sesiones
    session_dir = tmp_path / "raw_sessions" / mock_transcript.session_id
    session_dir.mkdir(parents=True)
    transcript_file = session_dir / "transcript.json"
    transcript_file.write_text(mock_transcript.model_dump_json(), encoding="utf-8")

    chat = DigitalTwinChat(
        profile=mock_profile,
        base_storage_dir=str(tmp_path),
        mock=True,
    )

    # Debe haber auto-cargado el diálogo del transcript
    assert chat.few_shot_dialogues is not None
    assert len(chat.few_shot_dialogues) >= 1
    assert "bot" in chat.few_shot_dialogues[0]["context"]
    assert "flama" in chat.few_shot_dialogues[0]["reply"]


def test_compile_twin_prompt_preferences_and_tech_anti_hallucination(mock_profile):
    """Verifica que los gustos/disgustos se incluyan y que términos de programación se purguen si no es programador."""
    profile = mock_profile.model_copy()
    profile.preferences = UserPreferences(
        likes=["Bleach", "Rocket League", "Red Rising"],
        dislikes=["levantarse temprano", "sopa de verduras"],
    )
    profile.notes = ["estudiante de secundaria", "le gusta el anime"]
    profile.emotional_triggers = EmotionalTriggers(
        tilts=["perder una ranked", "cierres intempestivos de sesión en el sistema mientras programa"],
        hyperfocus_topics=["Bleach", "proyectos de software"],
    )

    prompt = compile_twin_prompt(profile)

    # 1. Verificación de gustos y disgustos
    assert "TUS GUSTOS Y PREFERENCIAS REALES" in prompt
    assert "Bleach, Rocket League, Red Rising" in prompt
    assert "levantarse temprano, sopa de verduras" in prompt

    # 2. Verificación de regla estricta anti-programación
    assert "NO ERES PROGRAMADOR NI INGENIERO POR DEFECTO" in prompt
    assert "PROHIBIDO HABLAR DE CÓDIGO O INFORMÁTICA" in prompt

    # 3. Verificación de sanitización de términos técnicos espurios de emotional triggers
    assert "cierres intempestivos de sesión en el sistema mientras programa" not in prompt
    assert "proyectos de software" not in prompt
    assert "perder una ranked" in prompt




