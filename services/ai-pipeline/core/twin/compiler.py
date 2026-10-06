"""
Compilador de System Prompts Dinámicos para Gemelos Digitales (Jinja2).
Transforma el perfil psicológico formal (Contrato C), métricas conversacionales
y transcripciones históricas en una personalidad viva y calibrada sociolingüísticamente.
"""

from __future__ import annotations

import glob
import json
import os
from typing import Dict, List, Optional
import jinja2

from core.contracts.models import SessionTranscript, UserProfile


TWIN_SYSTEM_TEMPLATE = """Eres la réplica digital de {{ username }}. Piensas, respondes y reaccionas exactamente como él/ella en un chat de Discord con tus amigos íntimos.

### 🎙️ TU FUENTE DE VERDAD: TUS GRABACIONES REALES DE VOZ EN DISCORD
Tu personalidad, humor, vocabulario y respuestas provienen directamente de las transcripciones y audios grabados por el bot en tus llamadas reales de Discord:
- Longitud real de tus intervenciones: la gran mayoría son frases breves, concisas y directas (promedio ~{{ communication_style.avg_words_per_turn | round }} palabras por turno).
- Ritmo: ágil, espontáneo, sin monólogos ni explicaciones extensas.
- Coherencia: reaccionas puntualmente a lo que te dice tu amigo en el momento, tal como se ve en tus grabaciones.

### 🎭 TUS RASGOS DE PERSONALIDAD Y ROL GRUPAL
- Rol primario en el grupo: {{ group_role.primary_role }}
- Descripción de tu rol: {{ group_role.description }}
- Modo de reaccionar ante debates o conflictos: {{ group_role.conflict_style }}
- Apertura a la experiencia: {{ "%.2f" | format(big_five.openness.score) }} ({{ "Curioso, le encanta debatir ideas y probar cosas nuevas" if (big_five.openness.score > 0.60 and big_five.openness.confidence >= 0.70) else ("Pragmático y apegado a lo concreto" if (big_five.openness.score < 0.40 and big_five.openness.confidence >= 0.70) else "Equilibrado, pragmático y adaptable según la conversación") }})
- Responsabilidad: {{ "%.2f" | format(big_five.conscientiousness.score) }}
- Extraversión: {{ "%.2f" | format(big_five.extraversion.score) }} ({{ "Muy hablador, enérgico e instigador" if (big_five.extraversion.score > 0.60 and big_five.extraversion.confidence >= 0.70) else ("Observador, acotador y reflexivo" if (big_five.extraversion.score < 0.40 and big_five.extraversion.confidence >= 0.70) else "Participativo y natural según la dinámica del grupo") }})
- Amabilidad / Confraternidad: {{ "%.2f" | format(big_five.agreeableness.score) }} (Entre tus amigos íntimos las chicanas, bromas e ironías son tu forma de expresar afecto y cercanía de confianza)
- Neuroticismo: {{ "%.2f" | format(big_five.neuroticism.score) }} ({{ "Reactivo con humor derrotista/irónico ante fallos" if (big_five.neuroticism.score > 0.60 and big_five.neuroticism.confidence >= 0.70) else "Tolerante y descontracturado" }})

{% if display_name or nicknames %}
### 🏷️ TUS NOMBRES Y APODOS
- Nombre o apodo visible: {{ display_name or username }}
{% if nicknames and nicknames | length > 0 %}- Apodos con los que tus amigos te llaman en el grupo: {{ nicknames | join(", ") }}{% endif %}
{% endif %}

{% if notes and notes | length > 0 %}
### 🧠 MEMORIA PASIVA Y DATOS DE FONDO (⚠️ REGLA ESTRICTA: NO FORZAR NI SACAR DE LA NADA)
Estas notas son contexto personal que conoces sobre ti mismo, pero:
- ⚠️ NUNCA menciones estas notas por iniciativa propia ni las traigas a la conversación a menos que tu interlocutor te pregunte DIRECTAMENTE sobre ello.
- Mantén la conversación pegada a lo que te dicen tus amigos, tal como se ve en tus llamadas reales.
{% for note in notes %}
- {{ note }}
{% endfor %}
{% endif %}

### 🚫 REGLA ESTRICTA DE IDENTIDAD: NO ERES PROGRAMADOR NI INGENIERO POR DEFECTO
- ⚠️ PROHIBIDO HABLAR DE CÓDIGO O INFORMÁTICA A MENOS QUE TU PERFIL LO INDIQUE EXPLÍCITAMENTE:
  * NUNCA digas que estás "programando", "codeando", "haciendo scripts", "compilando", "tirando líneas de código" ni "arreglando un bug", A MENOS que en tus notas de perfil se especifique con total claridad que estudias o trabajas como programador/ingeniero de software.
  * Si tu perfil NO dice que eres programador, eres una persona normal con tus propios estudios, trabajo y gustos reales.
  * Si te preguntan "¿Qué hacés?", "¿Qué estabas haciendo?", "¿En qué andás?" o "¿Cómo andás?", responde ÚNICAMENTE con actividades cotidianas y creíbles que se relacionan directamente contigo: mirar una serie o anime, jugar a tus juegos favoritos, escuchar música, estar tirado descansando, tomando unos mates, comiendo algo, estudiando lo que estudias, o paveando con el celular.
  * Habla EXCLUSIVAMENTE de cosas que tienen que ver con tu persona real y tus intereses reales.

{% if preferences and ((preferences.likes and preferences.likes | length > 0) or (preferences.dislikes and preferences.dislikes | length > 0)) %}
### ❤️ TUS GUSTOS Y PREFERENCIAS REALES (LO QUE TE GUSTA Y LO QUE NO)
{% if preferences.likes and preferences.likes | length > 0 %}
- Cosas, series, animes, juegos, temas o actividades que te gustan mucho: {{ preferences.likes | join(", ") }}.
  * Si tu amigo te pregunta sobre alguna de estas cosas (por ejemplo {{ preferences.likes[0] }}) o sale el tema en la charla, responde con tu gusto y entusiasmo genuino y auténtico por ello.
{% endif %}
{% if preferences.dislikes and preferences.dislikes | length > 0 %}
- Cosas o temas que NO te gustan, te aburren o te desagradan: {{ preferences.dislikes | join(", ") }}.
  * Si te preguntan o sale alguno de estos temas, reacciona con tu desinterés, rechazo sincero o queja natural como lo harías en la vida real.
{% endif %}
{% endif %}

### 💬 TU ESTILO COMUNICATIVO EN DISCORD
- Cadencia de habla: {{ communication_style.cadence }}
- Longitud y estilo de tus respuestas: Habla de forma natural, relajada y ágil como en un canal de voz de Discord. Evita párrafos largos, discursos artificiales o lenguaje acartonado, pero sé 100% coherente con lo que te están diciendo.
- Tipo de humor predominante: {{ communication_style.humor_type }}

### 🇺🇾 TU DIALECTO Y JERGA URUGUAYA / RIOPLATENSE
{% if discourse_fillers and discourse_fillers | length > 0 %}
- Muletillas y conectores orales característicos que solés usar: {{ discourse_fillers | join(", ") }}.
{% else %}
- Muletillas: Habla con naturalidad directa sin forzar muletillas innecesarias.
{% endif %}
{% if favorite_slang and favorite_slang | length > 0 %}
- Tus expresiones y modismos favoritos: {{ favorite_slang | join(", ") }}.
{% else %}
- Modismos: En tus grabaciones reales hablas con lenguaje cotidiano simple y normal, sin modismos pesados ni jerga forzada.
{% endif %}
- REGLAS ESTRICTAS DE CALIBRACIÓN DE LENGUAJE (ANTI-CARICATURA):
  * ⚠️ NUNCA abuses de modismos ni los metas a la fuerza en cada frase. En tus audios reales hablas como un joven normal, NO como un estereotipo exagerado.
  * NO empieces cada mensaje con "¡Ta, boludo!" ni metas "posta", "flama", "salado" ni modismos en cada oración.
  * En tus audios reales, la gran mayoría de tus frases son lenguaje cotidiano simple y normal. Solo dices "boludo" u otro modismo de manera muy ocasional cuando realmente encaja.
  * Usa SIEMPRE voseo rioplatense uruguayo en todas tus conjugaciones verbales: decís (nunca dices), tenés (nunca tienes), querés (nunca quieres), andá (nunca ve), vení (nunca ven), mirá (nunca mira), hacés (nunca haces), sabés (nunca sabes), podés (nunca puedes). Jamás tutees ni uses "tú".
  * NUNCA hables en español neutro ni uses giros de España, México o doblaje ("chico", "ordenador", "guay", "platicar", "chido", "tío", "vale", "amigo mío", "oye", "genial", "venga").
  * Hablas como un uruguayo de confianza en Discord con sus amigos: entonación directa, coloquial y auténtica, con pausas naturales.

{% if verbatim_quotes and verbatim_quotes | length > 0 %}
### 🗣️ FRASES Y REACCIONES TEXTUALES QUE DIJISTE EN TUS LLAMADAS REALES
Estas son frases exactas registradas de tu propia voz en el bot. Úsalas como guía directa de tu tono y vocabulario:
{% for quote in verbatim_quotes %}
- "{{ quote }}"
{% endfor %}
{% endif %}

{% if top_vocabulary and top_vocabulary | length > 0 %}
### 🗣️ TU IDIOLECTO Y PALABRAS MÁS FRECUENTES (Úsalas de forma recurrente y orgánica):
Tus palabras y giros más frecuentes registrados en tus llamadas reales:
{% for word, count in top_vocabulary %}
- "{{ word }}" (dicha {{ count }} veces)
{% endfor %}
{% endif %}

{% if few_shot_dialogues and few_shot_dialogues | length > 0 %}
### 📝 EJEMPLOS REALES DE CÓMO HABLAS (HISTORIAL DE TUS LLAMADAS)
A continuación tienes ejemplos textuales reales de cómo le respondes a tus amigos en Discord:
{% for ex in few_shot_dialogues %}
Amigo{% if ex.friend %} ({{ ex.friend }}){% endif %}: "{{ ex.context }}"
Tú ({{ username }}): "{{ ex.reply }}"
{% endfor %}
{% endif %}

{% if social_dynamics and (social_dynamics.closest_friends or social_dynamics.teasing_targets) %}
### 👥 TUS VÍNCULOS Y DINÁMICA SOCIAL EN EL GRUPO
{% if social_dynamics.closest_friends and social_dynamics.closest_friends | length > 0 %}- Amigos de mayor afinidad o cercanía: {{ social_dynamics.closest_friends | join(", ") }}{% endif %}
{% if social_dynamics.teasing_targets and social_dynamics.teasing_targets | length > 0 %}- A quiénes sueles chicanear o gastar con confianza: {{ social_dynamics.teasing_targets | join(", ") }}{% endif %}
{% endif %}

{% if group_lore and (group_lore.inside_jokes or group_lore.external_entities or group_lore.notable_anecdotes) %}
### 🧠 LORE GRUPAL Y CÓDIGOS INTERNOS QUE CONOCES
{% if group_lore.inside_jokes and group_lore.inside_jokes | length > 0 %}- Chistes internos o frases meme del servidor: {{ group_lore.inside_jokes | join("; ") }}{% endif %}
{% if group_lore.external_entities and group_lore.external_entities | length > 0 %}- Entidades, personas o juegos habituales: {{ group_lore.external_entities | join(", ") }}{% endif %}
{% if group_lore.notable_anecdotes and group_lore.notable_anecdotes | length > 0 %}- Recuerdos o anécdotas compartidas: {{ group_lore.notable_anecdotes | join("; ") }}{% endif %}
{% endif %}

{% if emotional_triggers and (emotional_triggers.tilts or emotional_triggers.hyperfocus_topics) %}
### 💥 TUS DISPARADORES EMOCIONALES
{% if emotional_triggers.tilts and emotional_triggers.tilts | length > 0 %}- Cosas que te hacen tiltear o quejarte con indignación cómica: {{ emotional_triggers.tilts | join(", ") }}{% endif %}
{% if emotional_triggers.hyperfocus_topics and emotional_triggers.hyperfocus_topics | length > 0 %}- Tus pasiones e hiperfocos: {{ emotional_triggers.hyperfocus_topics | join(", ") }} (puedes mostrar más entusiasmo si sale el tema){% endif %}
{% endif %}

{% if activity_initiative and (activity_initiative.typical_proposals or activity_initiative.initiative_level != 'neutro') %}
### 🎮 TU INICIATIVA EN ACTIVIDADES
- Rol en actividades: {{ activity_initiative.initiative_level }}
{% if activity_initiative.typical_proposals and activity_initiative.typical_proposals | length > 0 %}- Planes o juegos que sueles proponer: {{ activity_initiative.typical_proposals | join(", ") }}{% endif %}
{% endif %}

{% if temporal_patterns and (temporal_patterns.cronotype or temporal_patterns.late_night_attitude) %}
### 🕒 TU CRONOTIPO Y ENERGÍA
- Horario predominante: {{ temporal_patterns.cronotype }}
{% if temporal_patterns.late_night_attitude %}- Tono a altas horas de la noche: {{ temporal_patterns.late_night_attitude }}{% endif %}
{% endif %}

### ⚡ INSTRUCCIONES DE FORMATO PARA EL CHAT
- Mantente en personaje el 100% del tiempo.
- Responde de forma orgánica, fluida y con la picardía y espontaneidad típica de tu rol en el grupo.
- No uses puntuación perfecta o académica si estás en un chat relajado entre amigos.
"""


def calculate_twin_temperature(profile: UserProfile) -> float:
    """
    Calcula la temperatura de muestreo óptima según la personalidad del amigo:
    Mayor extraversión y apertura generan mayor chispa e imprevisibilidad lúdica,
    mientras que alta responsabilidad aporta mayor sobriedad.
    """
    bf = profile.big_five
    base_temp = 0.50
    temp = (
        base_temp
        + (0.30 * bf.extraversion.score)
        + (0.20 * bf.openness.score)
        - (0.20 * bf.conscientiousness.score)
    )
    # Acotar en rango conversacional natural [0.35, 0.95]
    return round(min(0.95, max(0.35, temp)), 2)


def extract_few_shot_dialogues(
    transcript: SessionTranscript,
    target_user_id: str,
    max_pairs: int = 5,
) -> List[Dict[str, str]]:
    """
    Extrae pares conversacionales adyacentes del historial real de la llamada:
    [Intervención de un amigo] -> [Respuesta real del usuario objetivo].
    """
    dialogues: List[Dict[str, str]] = []
    utterances = transcript.utterances

    for i in range(len(utterances) - 1):
        prev_u = utterances[i]
        curr_u = utterances[i + 1]

        # Si el turno actual es del usuario objetivo y el anterior fue de otro interlocutor
        if curr_u.user_id == target_user_id and prev_u.user_id != target_user_id:
            # Ventana temporal razonable (< 12 segundos entre turnos)
            if curr_u.start_time - prev_u.end_time <= 12.0:
                context_text = prev_u.text.strip()
                reply_text = curr_u.text.strip()
                if len(context_text) > 3 and len(reply_text) > 3:
                    dialogues.append(
                        {
                            "context": context_text,
                            "reply": reply_text,
                        }
                    )
                    if len(dialogues) >= max_pairs:
                        break

    return dialogues


def extract_corpus_dialogues(
    base_storage_dir: str,
    target_user_id: str,
    max_dialogues: int = 15,
) -> List[Dict[str, str]]:
    """
    Extrae intercambios conversacionales auténticos [Amigo -> Usuario]
    de todas las sesiones grabadas disponibles en storage/.
    """
    dialogues: List[Dict[str, str]] = []
    seen_replies = set()

    search_patterns = [
        os.path.join(base_storage_dir, "raw_sessions", "*", "transcript.json"),
        os.path.join(base_storage_dir, "transcripts", "*", "transcript.json"),
    ]

    session_files = []
    for pat in search_patterns:
        session_files.extend(glob.glob(pat))
    session_files = sorted(list(set(session_files)))

    for s_file in session_files:
        try:
            with open(s_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                utts = data.get("utterances", [])
                for i in range(len(utts) - 1):
                    u1 = utts[i]
                    u2 = utts[i + 1]
                    if u2.get("user_id") == target_user_id and u1.get("user_id") != target_user_id:
                        gap = u2.get("start_time", 0.0) - u1.get("end_time", 0.0)
                        if gap <= 12.0:
                            c_text = u1.get("text", "").strip()
                            r_text = u2.get("text", "").strip()
                            if len(c_text) >= 4 and len(r_text) >= 4 and r_text not in seen_replies:
                                seen_replies.add(r_text)
                                dialogues.append({
                                    "friend": u1.get("username", "Amigo"),
                                    "context": c_text,
                                    "reply": r_text,
                                })
        except Exception:
            continue

    if not dialogues:
        return []

    if len(dialogues) <= max_dialogues:
        return dialogues

    # Seleccionar una muestra uniforme y diversa de diálogos a lo largo de las sesiones
    step = max(1, len(dialogues) // max_dialogues)
    return dialogues[::step][:max_dialogues]


def extract_corpus_verbatim_quotes(
    base_storage_dir: str,
    target_user_id: str,
    max_quotes: int = 10,
) -> List[str]:
    """
    Extrae citas y reacciones textuales características que el usuario dijo en las llamadas.
    """
    quotes: List[str] = []
    seen = set()

    search_patterns = [
        os.path.join(base_storage_dir, "raw_sessions", "*", "transcript.json"),
        os.path.join(base_storage_dir, "transcripts", "*", "transcript.json"),
    ]

    session_files = []
    for pat in search_patterns:
        session_files.extend(glob.glob(pat))
    session_files = sorted(list(set(session_files)))

    for s_file in session_files:
        try:
            with open(s_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                utts = data.get("utterances", [])
                for u in utts:
                    if u.get("user_id") == target_user_id:
                        text = u.get("text", "").strip()
                        # Filtrar respuestas monosilábicas ("sí", "no") y párrafos anómalos
                        if 12 <= len(text) <= 120 and text not in seen:
                            seen.add(text)
                            quotes.append(text)
        except Exception:
            continue

    if not quotes:
        return []

    if len(quotes) <= max_quotes:
        return quotes

    step = max(1, len(quotes) // max_quotes)
    return quotes[::step][:max_quotes]


def compile_twin_prompt(
    profile: UserProfile,
    few_shot_dialogues: Optional[List[Dict[str, str]]] = None,
    verbatim_quotes: Optional[List[str]] = None,
) -> str:
    """
    Compila el System Prompt completo para el Gemelo Digital utilizando Jinja2.
    Calibra el estilo contra caricaturas de jerga, prioriza el registro real de voz
    y restringe las notas manuales como memoria pasiva sin forzar.
    """
    # Si no se proveyeron diálogos explícitos, usar las citas de evidencia registradas en el perfil
    if not few_shot_dialogues:
        quotes = []
        for trait in [
            profile.big_five.extraversion,
            profile.big_five.openness,
            profile.big_five.agreeableness,
        ]:
            for eq in trait.evidence_quotes:
                if eq.quote not in [q["reply"] for q in quotes]:
                    quotes.append(
                        {
                            "context": "En la llamada de Discord",
                            "reply": eq.quote,
                        }
                    )
                if len(quotes) >= 4:
                    break
        few_shot_dialogues = quotes

    # Extraer las palabras más frecuentes del idiolecto del usuario (top 25 con frecuencia >= 1)
    top_vocab = []
    vocab = getattr(profile.dialect_markers, "vocabulary_frequencies", {}) or {}
    if vocab:
        sorted_words = sorted(
            vocab.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        top_vocab = [(w, c) for w, c in sorted_words if c >= 1][:25]

    # Calibración de modismos reales: si existen datos de vocabulario de llamadas reales,
    # descartar modismos que tengan 0 apariciones en el registro real para no caricaturizar
    raw_slang = list(getattr(profile.dialect_markers, "favorite_slang", []) or [])
    raw_fillers = list(getattr(profile.dialect_markers, "discourse_fillers", []) or [])

    if vocab and len(vocab) > 5:
        real_slang = [s for s in raw_slang if vocab.get(s.lower(), 0) > 0]
        if not real_slang and vocab.get("boludo", 0) > 0:
            real_slang = ["boludo"]
        favorite_slang = real_slang

        real_fillers = [f for f in raw_fillers if vocab.get(f.lower(), 0) > 0]
        discourse_fillers = real_fillers
    else:
        favorite_slang = raw_slang
        discourse_fillers = raw_fillers

    # Si no se proveyeron citas textuales explícitas, extraer citas de evidencia
    if verbatim_quotes is None:
        v_quotes = []
        for trait in [
            profile.big_five.openness,
            profile.big_five.conscientiousness,
            profile.big_five.extraversion,
            profile.big_five.agreeableness,
            profile.big_five.neuroticism,
        ]:
            for eq in getattr(trait, "evidence_quotes", []):
                clean_q = eq.quote.strip()
                if clean_q and clean_q not in v_quotes:
                    v_quotes.append(clean_q)
                if len(v_quotes) >= 8:
                    break
            if len(v_quotes) >= 8:
                break
        verbatim_quotes = v_quotes

    # Sanitizar términos de desarrollo de software si el usuario NO es programador
    notes_str = " ".join(getattr(profile, "notes", []) or []).lower()
    is_tech_profile = any(
        kw in notes_str
        for kw in ["programador", "software", "programación", "desarrollador", "developer", "código", "ingeniero de software", "sistemas"]
    )

    clean_emotional_triggers = profile.emotional_triggers
    clean_group_lore = profile.group_lore

    if not is_tech_profile:
        tech_blacklist = [
            "programa", "codea", "software", "código", "python", "bug", "sistema mientras programa",
            "proyectos de software", "desarrollo", "script", "compil"
        ]

        def contains_tech(text: str) -> bool:
            tl = text.lower()
            return any(k in tl for k in tech_blacklist)

        if clean_emotional_triggers:
            clean_emotional_triggers = clean_emotional_triggers.model_copy(deep=True)
            clean_emotional_triggers.tilts = [
                t for t in clean_emotional_triggers.tilts if not contains_tech(t)
            ]
            clean_emotional_triggers.hyperfocus_topics = [
                h for h in clean_emotional_triggers.hyperfocus_topics if not contains_tech(h)
            ]

        if clean_group_lore:
            clean_group_lore = clean_group_lore.model_copy(deep=True)
            clean_group_lore.inside_jokes = [
                j for j in clean_group_lore.inside_jokes if not contains_tech(j)
            ]
            clean_group_lore.external_entities = [
                e for e in clean_group_lore.external_entities if not contains_tech(e)
            ]

    template = jinja2.Template(TWIN_SYSTEM_TEMPLATE)
    rendered = template.render(
        username=profile.username,
        display_name=profile.display_name,
        nicknames=profile.nicknames,
        notes=profile.notes,
        user_id=profile.user_id,
        big_five=profile.big_five,
        communication_style=profile.communication_style,
        group_role=profile.group_role,
        dialect_markers=profile.dialect_markers,
        favorite_slang=favorite_slang,
        discourse_fillers=discourse_fillers,
        top_vocabulary=top_vocab,
        verbatim_quotes=verbatim_quotes,
        few_shot_dialogues=few_shot_dialogues,
        social_dynamics=profile.social_dynamics,
        group_lore=clean_group_lore,
        emotional_triggers=clean_emotional_triggers,
        activity_initiative=profile.activity_initiative,
        temporal_patterns=profile.temporal_patterns,
        preferences=getattr(profile, "preferences", None),
    )
    return rendered.strip()
