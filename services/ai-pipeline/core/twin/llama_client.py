"""
Cliente de Respaldo para Modelos LLaMA (LlamaClient).
Proporciona inferencia gratuita cuando la cuota de Gemini API se agota o falla.
Soporta:
1. Groq Cloud (API oficial ultrarrápida gratuita para LLaMA 3.3 70B / 3.1 8B).
2. OpenRouter Free (meta-llama/llama-3.3-70b-instruct:free).
3. Servidor Local Ollama (http://localhost:11434/v1).
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional
import requests

logger = logging.getLogger(__name__)

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
DEFAULT_OLLAMA_MODEL = "llama3.1"


class LlamaClient:
    """Cliente unificado para invocar modelos LLaMA cuando Gemini agota su cuota."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        # 1. Groq API Key (GROQ_API_KEY o LLAMA_API_KEY)
        self.groq_key = (
            api_key
            or os.getenv("GROQ_API_KEY")
            or os.getenv("LLAMA_API_KEY")
            or ""
        ).strip()

        # 2. OpenRouter API Key
        self.openrouter_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()

        # 3. Ollama Host
        self.ollama_host = (os.getenv("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")

        self.custom_model = model
        self.provider = provider  # "groq", "openrouter", "ollama", o auto

        self._groq_client = None
        if self.groq_key and (not self.provider or self.provider == "groq"):
            try:
                from groq import Groq

                self._groq_client = Groq(api_key=self.groq_key)
            except Exception as e:
                logger.warning(f"No se pudo inicializar cliente Groq: {e}")

    def is_available(self) -> bool:
        """Determina si existe al menos un proveedor de LLaMA configurado y listo."""
        if self._groq_client is not None or bool(self.groq_key):
            return True
        if bool(self.openrouter_key):
            return True
        return self._check_ollama_alive()

    def _check_ollama_alive(self) -> bool:
        """Verifica rápidamente si hay una instancia de Ollama activa en local."""
        try:
            r = requests.get(f"{self.ollama_host}/api/version", timeout=0.8)
            return r.status_code == 200
        except Exception:
            return False

    def chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 400,
    ) -> str:
        """
        Envía la conversación a LLaMA y retorna la respuesta en personaje.
        messages debe ser una lista de dicts con 'role' ('user' o 'assistant') y 'text' (o 'content').
        """
        formatted_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            role = m.get("role", "user")
            content = m.get("text") or m.get("content") or ""
            if content.strip():
                formatted_messages.append({"role": role, "content": content})

        # Intento 1: Groq Cloud (Ultra rápido y gratuito)
        if self.groq_key:
            try:
                return self._call_groq(formatted_messages, temperature, max_tokens)
            except Exception as e:
                logger.warning(f"Fallo en Groq LLaMA: {e}. Probando proveedores alternativos...")

        # Intento 2: OpenRouter Free
        if self.openrouter_key:
            try:
                return self._call_openrouter(formatted_messages, temperature, max_tokens)
            except Exception as e:
                logger.warning(f"Fallo en OpenRouter LLaMA: {e}")

        # Intento 3: Ollama Local
        if self._check_ollama_alive():
            try:
                return self._call_ollama(formatted_messages, temperature, max_tokens)
            except Exception as e:
                logger.warning(f"Fallo en Ollama local: {e}")

        raise RuntimeError(
            "No hay ningún proveedor de LLaMA disponible o configurado. "
            "Para activar LLaMA gratuito, agrega GROQ_API_KEY a tu archivo .env "
            "(consíguela en 1 minuto en https://console.groq.com/keys)."
        )

    def _call_groq(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Ejecuta inferencia con la API oficial de Groq."""
        from groq import Groq

        client = self._groq_client or Groq(api_key=self.groq_key)
        model_name = self.custom_model or os.getenv("LLAMA_MODEL") or DEFAULT_GROQ_MODEL

        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return completion.choices[0].message.content.strip()

    def _call_openrouter(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Ejecuta inferencia a través de OpenRouter Free API."""
        model_name = self.custom_model or os.getenv("LLAMA_MODEL") or DEFAULT_OPENROUTER_MODEL
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Saframa/Analizador-de-personalidad-discord",
            "X-Title": "Discord AI Digital Twin",
        }
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=25,
        )
        res.raise_for_status()
        data = res.json()
        return data["choices"][0]["message"]["content"].strip()

    def _call_ollama(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Ejecuta inferencia en una instancia local de Ollama."""
        model_name = self.custom_model or os.getenv("LLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        res = requests.post(
            f"{self.ollama_host}/api/chat",
            json=payload,
            timeout=30,
        )
        res.raise_for_status()
        data = res.json()
        return data.get("message", {}).get("content", "").strip()
