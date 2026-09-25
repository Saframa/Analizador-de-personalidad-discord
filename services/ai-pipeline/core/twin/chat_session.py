"""
Sesión Conversacional Interactiva del Gemelo Digital (Digital Twin Chat Session).
Mantiene el contexto, procesa réplicas en tiempo real con Gemini API
y reproduce fielmente la personalidad, rol y dialecto del usuario perfilado.
"""

from __future__ import annotations

import os
import random
import time
from typing import Dict, List, Optional

from core.contracts.models import UserProfile
from core.twin.compiler import calculate_twin_temperature, compile_twin_prompt


class DigitalTwinChat:
    def __init__(
        self,
        profile: UserProfile,
        system_prompt: Optional[str] = None,
        few_shot_dialogues: Optional[List[Dict[str, str]]] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        mock: bool = False,
    ):
        self.profile = profile
        self.system_prompt = system_prompt or compile_twin_prompt(profile, few_shot_dialogues)
        self.temperature = calculate_twin_temperature(profile)
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-flash-latest")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.mock = mock or (not self.api_key or self.api_key == "tu_api_key_aqui")

        self.history: List[Dict[str, str]] = []
        self._client = None
        self._chat = None

        if not self.mock:
            self._init_chat()

    def _init_chat(self) -> None:
        try:
            from google import genai
            from google.genai import types

            self._client = genai.Client(api_key=self.api_key)
            self._chat = self._client.chats.create(
                model=self.model_name,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                    temperature=self.temperature,
                ),
            )
        except Exception as e:
            print(f"⚠️  Aviso: No se pudo conectar a Gemini API ({e}). Activando modo mock local.")
            self.mock = True

    def send_message(self, user_message: str, max_retries: int = 3) -> str:
        """
        Envía un mensaje al Gemelo Digital y retorna su respuesta en personaje.
        """
        clean_input = user_message.strip()
        if not clean_input:
            return ""

        self.history.append({"role": "user", "text": clean_input})

        if self.mock:
            reply = self._mock_response(clean_input)
            self.history.append({"role": "assistant", "text": reply})
            return reply

        last_error = None
        for attempt in range(max_retries):
            try:
                response = self._chat.send_message(clean_input)
                reply = response.text.strip()
                self.history.append({"role": "assistant", "text": reply})
                return reply
            except Exception as e:
                last_error = e
                # Espera con retroceso exponencial breve ante picos de demanda (503/429)
                time.sleep(1.5 * (attempt + 1))

        # Si agotó reintentos, generar respuesta de respaldo en personaje
        fallback = self._mock_response(clean_input)
        self.history.append({"role": "assistant", "text": fallback})
        return fallback

    def _mock_response(self, user_message: str) -> str:
        """
        Generador heurístico de réplicas en personaje para pruebas offline.
        """
        username = self.profile.username
        role = self.profile.group_role.primary_role
        slang = self.profile.dialect_markers.favorite_slang or ["salado", "flama", "posta"]
        fillers = self.profile.dialect_markers.discourse_fillers or ["bo", "ta"]

        chosen_slang = random.choice(slang)
        chosen_filler = random.choice(fillers)

        templates = [
            f"¡Qué hacés {chosen_filler}! Sí, totalmente, está {chosen_slang} lo que decís.",
            f"Pará un cacho {chosen_filler}... ¿en serio me estás diciendo eso? Ni ahí.",
            f"Jajaja sos un perro {chosen_filler}, dejá quieto que esto está {chosen_slang}.",
            f"Ta, mirá, como siempre te digo: está todo {chosen_slang}, tranqui.",
            f"¡Of! Te juro que se me rompió todo recién. Pero bueno {chosen_filler}, andamos en esa.",
        ]

        if "cómo estás" in user_message.lower() or "como andas" in user_message.lower():
            return f"¡Buenas {chosen_filler}! Acá andamos, tirando para no aflojar. ¿Vos qué onda?"

        return random.choice(templates)

    def reset(self) -> None:
        """Reinicia el historial de la conversación."""
        self.history.clear()
        if not self.mock:
            self._init_chat()
