"""
Módulo de Reconciliación de Sesiones Huérfanas y Recuperación ante Fallos.
Detecta sesiones interrumpidas, vacías o sin metadatos, reconstruye contratos
formales (A y B) y previene bloqueos de estado en el Vigilante de IA y la GUI.
"""

from __future__ import annotations

import os
import re
import time
import wave
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from core.contracts.models import (
    SessionMetadata,
    ParticipantInfo,
    AudioFileInfo,
    SessionTranscript,
    Utterance,
)
from core.user_manager.manager import UserManager

logger = logging.getLogger("session_reconciler")


def _parse_session_timestamp(session_id: str) -> datetime:
    """Parsea el timestamp del ID de sesión (YYYY-MM-DD_HH-mm-ss) en UTC."""
    try:
        dt = datetime.strptime(session_id, "%Y-%m-%d_%H-%M-%S")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _is_wav_empty(file_path: str) -> bool:
    """Retorna True si un archivo WAV no contiene cuadros de audio válidos (0 frames)."""
    try:
        if os.path.getsize(file_path) < 44:
            return True
        with wave.open(file_path, "rb") as w:
            return w.getnframes() == 0
    except Exception:
        return True


def _is_ogg_empty(file_path: str) -> bool:
    """
    Retorna True si un archivo OGG Opus solo contiene cabeceras de contenedor
    sin paquetes de audio reales (típicamente <= 107 bytes de cabecera OpusHead+OpusTags).
    """
    try:
        size = os.path.getsize(file_path)
        return size <= 107
    except Exception:
        return True


def is_audio_file_empty(file_path: str) -> bool:
    """Verifica si un archivo de audio está vacío o solo contiene cabeceras."""
    if not os.path.exists(file_path):
        return True
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".wav":
        return _is_wav_empty(file_path)
    elif ext in (".ogg", ".opus"):
        return _is_ogg_empty(file_path)
    return os.path.getsize(file_path) <= 100


def is_session_active(session_dir: str, active_window_seconds: int = 45) -> bool:
    """
    Comprueba si una sesión está siendo escrita activamente en vivo por el bot de Discord.
    Si existe el archivo lock .recording o si los archivos de audio/directorio fueron
    modificados hace menos de active_window_seconds, se considera en vivo y NUNCA
    debe reconciliarse prematuramente.
    """
    if os.path.exists(os.path.join(session_dir, ".recording")):
        return True
    now = time.time()
    try:
        if (now - os.path.getmtime(session_dir)) < active_window_seconds:
            return True
        audio_dir = os.path.join(session_dir, "audio")
        if os.path.exists(audio_dir):
            if (now - os.path.getmtime(audio_dir)) < active_window_seconds:
                return True
            for f in os.listdir(audio_dir):
                fp = os.path.join(audio_dir, f)
                if os.path.isfile(fp) and (now - os.path.getmtime(fp)) < active_window_seconds:
                    return True
    except Exception:
        pass
    return False


def reconcile_orphan_sessions(
    storage_dir: str,
    skip_active: bool = False,
    active_window_seconds: int = 45,
) -> Dict[str, Any]:
    """
    Escanea storage/raw_sessions y reconcilia sesiones huérfanas o interrumpidas:
    1. Si no tiene session_metadata.json y todos sus audios están vacíos (0 frames/<=107B):
       Crea metadata 0s, transcript vacío y marca .purged (cierre limpio).
    2. Si no tiene session_metadata.json pero tiene audio real grabado (>107B):
       Reconstruye session_metadata.json con participantes y timestamps para que el
       pipeline de IA la transcriba sin perder voz del usuario.
    3. Si tiene session_metadata.json pero ended_at es nulo o ausente:
       Calcula ended_at a partir de la última modificación de los audios y actualiza metadata.
    4. Si tiene transcript.json pero el audio sin procesar quedó sin purgar:
       Elimina audios residuales y deja .purged.
    """
    raw_sessions_dir = os.path.join(storage_dir, "raw_sessions")
    if not os.path.exists(raw_sessions_dir):
        return {"reconciled_empty": 0, "reconstructed_active": 0, "fixed_metadata": 0}

    user_mgr = UserManager(storage_dir)
    reconciled_empty = 0
    reconstructed_active = 0
    fixed_metadata = 0

    candidates = sorted(os.listdir(raw_sessions_dir))
    for s_id in candidates:
        session_dir = os.path.join(raw_sessions_dir, s_id)
        if not os.path.isdir(session_dir) or s_id.startswith("."):
            continue

        # Si se solicita omitir sesiones activas y se detecta escritura en vivo, no tocarla
        if skip_active and is_session_active(session_dir, active_window_seconds):
            continue

        meta_path = os.path.join(session_dir, "session_metadata.json")
        audio_dir = os.path.join(session_dir, "audio")
        transcript_path = os.path.join(session_dir, "transcript.json")
        purged_path = os.path.join(audio_dir, ".purged") if os.path.exists(audio_dir) else None

        # ----------------------------------------------------------------------
        # CASO 1 & 2: Falta session_metadata.json
        # ----------------------------------------------------------------------
        if not os.path.exists(meta_path):
            audio_files_list = []
            if os.path.exists(audio_dir):
                audio_files_list = [
                    f for f in os.listdir(audio_dir)
                    if os.path.isfile(os.path.join(audio_dir, f)) and not f.startswith(".")
                ]

            if not audio_files_list:
                # Directorio sin archivos de audio
                started_at = _parse_session_timestamp(s_id)
                meta = SessionMetadata(
                    version="1.0.0",
                    session_id=s_id,
                    guild_id="1475942148393140305",
                    channel_id="1475942151895388262",
                    channel_name="General",
                    started_at=started_at,
                    ended_at=started_at,
                    duration_seconds=0.0,
                    participants=[
                        ParticipantInfo(
                            user_id="unknown",
                            username="unknown",
                            display_name="Unknown",
                            joined_at=started_at,
                            left_at=started_at,
                        )
                    ],
                    audio_files={},
                )
                meta.save_atomic(meta_path)

                if not os.path.exists(transcript_path):
                    transcript = SessionTranscript(
                        version="1.0.0",
                        session_id=s_id,
                        processed_at=datetime.now(timezone.utc),
                        model="faster-whisper-large-v3",
                        utterances=[],
                    )
                    transcript.save_atomic(transcript_path)

                if os.path.exists(audio_dir):
                    receipt = os.path.join(audio_dir, ".purged")
                    with open(receipt, "w", encoding="utf-8") as f:
                        f.write(f"Sesión vacía sin audio purgada el {datetime.now(timezone.utc).isoformat()}.\n")
                reconciled_empty += 1
                logger.info(f"Sesión vacía {s_id} reconciliada como completada (0s).")
                continue

            # Evaluar si todos los archivos de audio están vacíos
            all_empty = True
            for af in audio_files_list:
                af_path = os.path.join(audio_dir, af)
                if not is_audio_file_empty(af_path):
                    all_empty = False
                    break

            started_at = _parse_session_timestamp(s_id)
            participants: List[ParticipantInfo] = []
            audio_files_dict: Dict[str, AudioFileInfo] = {}

            for af in audio_files_list:
                af_path = os.path.join(audio_dir, af)
                user_id = os.path.splitext(af)[0]
                user_obj = user_mgr.get_user(user_id)
                uname = user_obj.username if user_obj else f"user_{user_id[-4:]}"
                dname = (user_obj.display_name if user_obj and user_obj.display_name else uname) or uname

                participants.append(
                    ParticipantInfo(
                        user_id=user_id,
                        username=uname,
                        display_name=dname,
                        joined_at=started_at,
                        left_at=started_at,
                    )
                )

                ext = os.path.splitext(af)[1].lower().replace(".", "")
                fmt = "ogg_opus" if ext in ("ogg", "opus") else "wav"
                size = os.path.getsize(af_path)

                audio_files_dict[user_id] = AudioFileInfo(
                    filename=f"audio/{af}",
                    sample_rate=48000,
                    channels=1,
                    format=fmt,
                    size_bytes=size,
                )

            if not participants:
                participants = [
                    ParticipantInfo(
                        user_id="unknown",
                        username="unknown",
                        display_name="Unknown",
                        joined_at=started_at,
                        left_at=started_at,
                    )
                ]

            if all_empty:
                # Todos los audios tienen 0 frames / <=107B -> Abortada sin voz
                meta = SessionMetadata(
                    version="1.0.0",
                    session_id=s_id,
                    guild_id="1475942148393140305",
                    channel_id="1475942151895388262",
                    channel_name="General",
                    started_at=started_at,
                    ended_at=started_at,
                    duration_seconds=0.0,
                    participants=participants,
                    audio_files=audio_files_dict,
                )
                meta.save_atomic(meta_path)

                # Generar transcript vacío válido
                if not os.path.exists(transcript_path):
                    transcript = SessionTranscript(
                        version="1.0.0",
                        session_id=s_id,
                        processed_at=datetime.now(timezone.utc),
                        model="faster-whisper-large-v3",
                        utterances=[],
                    )
                    transcript.save_atomic(transcript_path)

                # Purgar archivos de audio vacíos
                for af in audio_files_list:
                    try:
                        os.remove(os.path.join(audio_dir, af))
                    except Exception:
                        pass

                receipt = os.path.join(audio_dir, ".purged")
                with open(receipt, "w", encoding="utf-8") as f:
                    f.write(
                        f"Sesión vacía/abortada sin locución (0 cuadros) purgada el {datetime.now(timezone.utc).isoformat()}.\n"
                    )
                reconciled_empty += 1
                logger.info(f"Sesión abortada sin locución {s_id} reconciliada y purgada limpiamente.")

            else:
                # Contiene audio real pero faltaba session_metadata.json
                # Determinar duración a partir del mtime más reciente
                latest_mtime = max(os.path.getmtime(os.path.join(audio_dir, af)) for af in audio_files_list)
                ended_at = datetime.fromtimestamp(latest_mtime, tz=timezone.utc)
                duration_sec = max(1.0, (ended_at - started_at).total_seconds())

                for p in participants:
                    p.left_at = ended_at

                meta = SessionMetadata(
                    version="1.0.0",
                    session_id=s_id,
                    guild_id="1475942148393140305",
                    channel_id="1475942151895388262",
                    channel_name="General",
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_seconds=round(duration_sec, 2),
                    participants=participants,
                    audio_files=audio_files_dict,
                )
                meta.save_atomic(meta_path)
                reconstructed_active += 1
                logger.info(
                    f"Sesión activa huérfana {s_id} recuperada con metadata reconstruida ({duration_sec:.1f}s)."
                )

        # ----------------------------------------------------------------------
        # CASO 3: session_metadata.json existe pero ended_at es nulo o ausente
        # ----------------------------------------------------------------------
        elif os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta_dict = SessionMetadata.model_validate_json(f.read())
            except Exception:
                # Metadata corrupto o formato viejo sin ended_at
                meta_dict = None

            if meta_dict is None:
                # Si falló la validación por ended_at faltante en dict crudo
                try:
                    import json
                    with open(meta_path, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)
                    if not raw_data.get("ended_at"):
                        s_at = raw_data.get("started_at")
                        st = datetime.fromisoformat(s_at) if s_at else _parse_session_timestamp(s_id)
                        raw_data["ended_at"] = (st + timedelta(seconds=raw_data.get("duration_seconds", 0.0))).isoformat()
                        with open(meta_path, "w", encoding="utf-8") as f:
                            json.dump(raw_data, f, indent=2)
                        fixed_metadata += 1
                        logger.info(f"Metadatos de sesión {s_id} reparados con ended_at válido.")
                except Exception as e:
                    logger.warning(f"No se pudo reparar metadata de {s_id}: {e}")

        # ----------------------------------------------------------------------
        # CASO 4: Tiene transcript.json pero audio/ no tiene .purged
        # ----------------------------------------------------------------------
        if os.path.exists(transcript_path) and os.path.exists(audio_dir):
            purged_marker = os.path.join(audio_dir, ".purged")
            if not os.path.exists(purged_marker):
                # Verificar si los audios ya fueron eliminados o si quedan audios vacíos
                audio_remaining = [
                    f for f in os.listdir(audio_dir)
                    if os.path.isfile(os.path.join(audio_dir, f)) and not f.startswith(".")
                ]
                if not audio_remaining or all(is_audio_file_empty(os.path.join(audio_dir, f)) for f in audio_remaining):
                    for f in audio_remaining:
                        try:
                            os.remove(os.path.join(audio_dir, f))
                        except Exception:
                            pass
                    with open(purged_marker, "w", encoding="utf-8") as pf:
                        pf.write(f"Audio purgado automáticamente el {datetime.now(timezone.utc).isoformat()}.\n")
                    logger.info(f"Marca .purged creada para sesión transcripta {s_id}.")

    return {
        "reconciled_empty": reconciled_empty,
        "reconstructed_active": reconstructed_active,
        "fixed_metadata": fixed_metadata,
    }
