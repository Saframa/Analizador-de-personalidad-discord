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
from core.twin.compiler import (
    calculate_twin_temperature,
    compile_twin_prompt,
    extract_corpus_dialogues,
    extract_corpus_verbatim_quotes,
)
from core.twin.llama_client import LlamaClient


class DigitalTwinChat:
    def __init__(
        self,
        profile: UserProfile,
        system_prompt: Optional[str] = None,
        few_shot_dialogues: Optional[List[Dict[str, str]]] = None,
        verbatim_quotes: Optional[List[str]] = None,
        base_storage_dir: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        mock: bool = False,
        backend: str = "auto",
        llama_client: Optional[LlamaClient] = None,
    ):
        self.profile = profile
        self.base_storage_dir = base_storage_dir

        # Si no se proveyeron diálogos explícitos pero sí directorio de storage,
        # extraer automáticamente el corpus completo de audios grabados por el bot
        if few_shot_dialogues is None and self.base_storage_dir:
            few_shot_dialogues = extract_corpus_dialogues(
                self.base_storage_dir, self.profile.user_id, max_dialogues=15
            )

        if verbatim_quotes is None and self.base_storage_dir:
            verbatim_quotes = extract_corpus_verbatim_quotes(
                self.base_storage_dir, self.profile.user_id, max_quotes=10
            )

        self.few_shot_dialogues = few_shot_dialogues
        self.verbatim_quotes = verbatim_quotes
        self.system_prompt = system_prompt or compile_twin_prompt(
            profile, few_shot_dialogues=few_shot_dialogues, verbatim_quotes=verbatim_quotes
        )
        self.temperature = calculate_twin_temperature(profile)
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-flash-latest")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.backend = backend  # "auto", "gemini", o "llama"
        self.llama_client = llama_client or LlamaClient()
        self.mock = mock or (not self.api_key or self.api_key == "tu_api_key_aqui")

        self.history: List[Dict[str, str]] = []
        self._client = None
        self._chat = None

        # Si el modelo pedido es explícitamente LLaMA o backend='llama', forzar LLaMA
        if self.backend == "llama" or "llama" in self.model_name.lower():
            self.backend = "llama"
        elif not self.mock and self.backend in ("auto", "gemini"):
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

        # 1. Si el backend seleccionado es LLaMA directamente
        if self.backend == "llama":
            if self.llama_client and self.llama_client.is_available():
                try:
                    reply = self.llama_client.chat(
                        system_prompt=self.system_prompt,
                        messages=self.history,
                        temperature=self.temperature,
                    )
                    if reply:
                        self.history.append({"role": "assistant", "text": reply})
                        return reply
                except Exception as e:
                    print(f"⚠️  [Error en LLaMA API: {e}]")

        # 2. Si no es mock y tenemos conexión Gemini
        last_error = None
        if not self.mock and self._chat:
            for attempt in range(max_retries):
                try:
                    response = self._chat.send_message(clean_input)
                    reply = response.text.strip()
                    self.history.append({"role": "assistant", "text": reply})
                    return reply
                except Exception as e:
                    last_error = e

        # 3. Fallback a LLaMA cuando Gemini falla o agota su cuota (429)
        if self.llama_client and self.llama_client.is_available():
            try:
                print("\n🦙 [Gemini sin solicitudes: delegando respuesta a la API de LLaMA]...")
                llama_reply = self.llama_client.chat(
                    system_prompt=self.system_prompt,
                    messages=self.history,
                    temperature=self.temperature,
                )
                if llama_reply:
                    self.history.append({"role": "assistant", "text": llama_reply})
                    return llama_reply
            except Exception as llama_err:
                print(f"⚠️  [Error en fallback LLaMA: {llama_err}]")

        # 4. Último recurso: modo offline preprogramado
        if last_error:
            if "RESOURCE_EXHAUSTED" in str(last_error):
                print("\n⚠️  [Límite de API de Gemini alcanzado (429 Quota Exceeded)]")
                print("   Configura tu GROQ_API_KEY gratuita en el archivo .env para usar LLaMA 3.3.")
                print("   Usando réplica estática offline de respaldo temporalmente.")
            else:
                print(f"\n⚠️  [Error de Gemini API: {last_error}] Usando réplica estática de respaldo.")
        elif self.mock:
            print("\n⚠️  [Modo Mock: Sin API Key de Gemini ni LLaMA configurada. Usando réplica estática.]")

        fallback = self._mock_response(clean_input)
        self.history.append({"role": "assistant", "text": fallback})
        return fallback

    def _mock_response(self, user_message: str) -> str:
        """
        Generador heurístico de réplicas en personaje para pruebas offline.
        """
        username = self.profile.username
        role = self.profile.group_role.primary_role
        slang = self.profile.dialect_markers.favorite_slang or ["bien", "tranqui"]
        fillers = self.profile.dialect_markers.discourse_fillers or ["che", "bueno"]

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
