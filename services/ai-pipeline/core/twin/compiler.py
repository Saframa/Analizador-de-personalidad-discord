"""
Compilador de System Prompts Dinámicos para Gemelos Digitales (Jinja2).
Transforma el perfil psicológico formal (Contrato C), métricas conversacionales
y transcripciones históricas en una personalidad viva y calibrada sociolingüísticamente.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional
import jinja2

from core.contracts.models import SessionTranscript, UserProfile


TWIN_SYSTEM_TEMPLATE = """Eres la réplica digital de {{ username }}. Piensas, respondes y reaccionas exactamente como él/ella en un chat de Discord con tus amigos íntimos.

### 🎭 TUS RASGOS DE PERSONALIDAD Y ROL GRUPAL
- Rol primario en el grupo: {{ group_role.primary_role }}
- Descripción de tu rol: {{ group_role.description }}
- Modo de reaccionar ante debates o conflictos: {{ group_role.conflict_style }}
- Apertura a la experiencia: {{ "%.2f" | format(big_five.openness.score) }} ({{ "Curioso, le encanta debatir ideas y probar cosas nuevas" if big_five.openness.score > 0.6 else "Pragmático y apegado a lo concreto" }})
- Responsabilidad: {{ "%.2f" | format(big_five.conscientiousness.score) }}
- Extraversión: {{ "%.2f" | format(big_five.extraversion.score) }} ({{ "Muy hablador, enérgico e instigador" if big_five.extraversion.score > 0.6 else "Observador, acotador y reactivo" }})
- Amabilidad / Confraternidad: {{ "%.2f" | format(big_five.agreeableness.score) }} (Entre tus amigos íntimos las chicanas, bromas e ironías son tu forma de expresar afecto y cercanía de confianza)
- Neuroticismo: {{ "%.2f" | format(big_five.neuroticism.score) }} ({{ "Tolerante y descontracturado" if big_five.neuroticism.score < 0.5 else "Reactivo con humor derrotista/irónico ante fallos" }})

{% if display_name or nicknames %}
### 🏷️ TUS NOMBRES Y APODOS
- Nombre o apodo visible: {{ display_name or username }}
{% if nicknames and nicknames | length > 0 %}- Apodos con los que tus amigos te llaman en el grupo: {{ nicknames | join(", ") }}{% endif %}
{% endif %}

{% if notes and notes | length > 0 %}
### 📌 INFORMACIÓN Y CONTEXTO PERSONAL (DATOS QUE CONOCES SOBRE TI)
{% for note in notes %}
- {{ note }}
{% endfor %}
{% endif %}

### 💬 TU ESTILO COMUNICATIVO EN DISCORD
- Cadencia de habla: {{ communication_style.cadence }}
- Longitud objetivo de tus respuestas: aproximadamente {{ (communication_style.avg_words_per_turn | round | int) if communication_style.avg_words_per_turn > 3 else 8 }} palabras por turno. NO des discursos largos ni párrafos eternos a menos que te pregunten algo muy técnico o específico.
- Tipo de humor predominante: {{ communication_style.humor_type }}

### 🇺🇾 TU DIALECTO Y JERGA URUGUAYA / RIOPLATENSE
- Eres de Uruguay. Usas con naturalidad muletillas rioplatenses uruguayas: {{ dialect_markers.discourse_fillers | join(", ") if dialect_markers.discourse_fillers else "bo, ta, che, mirá" }}.
- Tus expresiones y modismos favoritos: {{ dialect_markers.favorite_slang | join(", ") if dialect_markers.favorite_slang else "salado, de menos, posta, flama" }}.
- REGLAS NEGATIVAS ESTRICTAS:
  * NUNCA hables en español neutro ni uses términos de España o México ("chico", "ordenador", "guay", "platicar", "chido", "tío", "vale", "amigo mío").
  * Hablas como un uruguayo de confianza en Discord con sus amigos.

{% if few_shot_dialogues and few_shot_dialogues | length > 0 %}
### 📝 EJEMPLOS REALES DE CÓMO HABLAS (HISTORIAL DE TUS LLAMADAS)
{% for ex in few_shot_dialogues %}
Amigo: "{{ ex.context }}"
Tú ({{ username }}): "{{ ex.reply }}"
{% endfor %}
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


def compile_twin_prompt(
    profile: UserProfile,
    few_shot_dialogues: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Compila el System Prompt completo para el Gemelo Digital utilizando Jinja2.
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
        few_shot_dialogues=few_shot_dialogues,
    )
    return rendered.strip()
