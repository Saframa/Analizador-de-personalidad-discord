"""
Gestor Organizado del Léxico e Idiolecto (LexiconManager).
Mantiene un registro permanente, ordenado y persistente de todas las palabras
utilizadas por cada usuario a través de todas las sesiones de Discord.
Evita pérdidas de datos o truncamientos arbitrarios.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("lexicon_manager")

WORD_REGEX = re.compile(r"\b[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ]+\b")


class LexiconManager:
    def __init__(self, storage_dir: str):
        self.storage_dir = os.path.abspath(storage_dir)
        self.profiles_dir = os.path.join(self.storage_dir, "profiles")
        self.raw_sessions_dir = os.path.join(self.storage_dir, "raw_sessions")
        os.makedirs(self.profiles_dir, exist_ok=True)

    def get_lexicon_path(self, user_id: str) -> str:
        """Ruta al archivo lexicon.json del usuario."""
        user_dir = os.path.join(self.profiles_dir, user_id)
        os.makedirs(user_dir, exist_ok=True)
        return os.path.join(user_dir, "lexicon.json")

    def load_lexicon(self, user_id: str) -> Dict[str, Any]:
        """Carga el registro de léxico del usuario o inicializa uno vacío."""
        path = self.get_lexicon_path(user_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error leyendo {path}: {e}")

        return {
            "user_id": user_id,
            "username": "",
            "total_words_spoken": 0,
            "total_unique_words": 0,
            "last_updated": None,
            "vocabulary": {},
        }

    def save_lexicon(self, user_id: str, data: Dict[str, Any]) -> None:
        """Guarda el registro de léxico estructurado en disco de forma atómica."""
        path = self.get_lexicon_path(user_id)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        if os.path.exists(path):
            os.replace(tmp_path, path)
        else:
            os.rename(tmp_path, path)

    def extract_words_from_text(self, text: str) -> List[str]:
        """Extrae palabras normalizadas en minúsculas preservando acentos en español."""
        if not text:
            return []
        return [w.lower() for w in WORD_REGEX.findall(text)]

    def record_session_utterances(
        self,
        user_id: str,
        username: str,
        utterances: List[Any],
    ) -> Tuple[int, int, Dict[str, int]]:
        """
        Incorpora los enunciados de una nueva sesión al registro acumulado.
        Retorna (total_words_spoken, total_unique_words, vocabulary_ordenado).
        """
        data = self.load_lexicon(user_id)
        data["username"] = username or data.get("username", "")

        vocab = dict(data.get("vocabulary", {}))

        # Acumular palabras de la sesión
        for u in utterances:
            text = getattr(u, "text", "") if hasattr(u, "text") else (u.get("text", "") if isinstance(u, dict) else str(u))
            words = self.extract_words_from_text(text)
            for w in words:
                vocab[w] = vocab.get(w, 0) + 1

        # Ordenar vocabulario por frecuencia descendente
        sorted_vocab = dict(sorted(vocab.items(), key=lambda item: item[1], reverse=True))

        total_words = sum(sorted_vocab.values())
        total_unique = len(sorted_vocab)

        data["total_words_spoken"] = total_words
        data["total_unique_words"] = total_unique
        data["last_updated"] = datetime.now(timezone.utc).isoformat()
        data["vocabulary"] = sorted_vocab

        self.save_lexicon(user_id, data)
        return total_words, total_unique, sorted_vocab

    def rebuild_all_from_transcripts(self) -> Dict[str, Dict[str, int]]:
        """
        Escanea todas las sesiones en raw_sessions y reconstruye el registro
        organizado de léxico para cada usuario, sin truncamientos ni pérdidas.
        """
        user_words = defaultdict(Counter)
        user_names = {}

        if not os.path.exists(self.raw_sessions_dir):
            return {}

        session_dirs = sorted(os.listdir(self.raw_sessions_dir))
        for s_id in session_dirs:
            s_path = os.path.join(self.raw_sessions_dir, s_id)
            if not os.path.isdir(s_path):
                continue

            tf = os.path.join(s_path, "transcript.json")
            if not os.path.exists(tf):
                continue

            try:
                with open(tf, "r", encoding="utf-8") as f:
                    tdata = json.load(f)
                for u in tdata.get("utterances", []):
                    uid = str(u.get("user_id", "")).strip()
                    if not uid:
                        continue
                    uname = u.get("username")
                    if uname and uid not in user_names:
                        user_names[uid] = uname

                    text = u.get("text", "")
                    words = self.extract_words_from_text(text)
                    for w in words:
                        user_words[uid][w] += 1
            except Exception as e:
                logger.warning(f"Error procesando transcripción {tf}: {e}")

        results = {}
        for uid, counter in user_words.items():
            sorted_vocab = dict(counter.most_common())
            uname = user_names.get(uid, "")
            total_words = sum(sorted_vocab.values())
            total_unique = len(sorted_vocab)

            data = {
                "user_id": uid,
                "username": uname,
                "total_words_spoken": total_words,
                "total_unique_words": total_unique,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "vocabulary": sorted_vocab,
            }
            self.save_lexicon(uid, data)

            # Sincronizar en profile.json si existe
            profile_path = os.path.join(self.profiles_dir, uid, "profile.json")
            if os.path.exists(profile_path):
                try:
                    with open(profile_path, "r", encoding="utf-8") as pf:
                        pdata = json.load(pf)
                    pdata["total_unique_words"] = total_unique
                    if "dialect_markers" not in pdata:
                        pdata["dialect_markers"] = {}
                    pdata["dialect_markers"]["vocabulary_frequencies"] = sorted_vocab
                    with open(profile_path, "w", encoding="utf-8") as pf:
                        json.dump(pdata, pf, indent=2, ensure_ascii=False)
                except Exception as pe:
                    logger.warning(f"Error actualizando profile.json para {uid}: {pe}")

            results[uid] = {
                "total_words": total_words,
                "total_unique": total_unique,
            }

        return results
