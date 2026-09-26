"""
Módulo de Sincronización entre archivos de storage (JSON) y SQLite.
Permite poblar y mantener actualizada la base de datos a partir del disco.
"""

import json
import logging
import os
import glob
from typing import Dict, Any, Optional

from core.db.database import get_connection, init_database, DEFAULT_DB_PATH
from core.session_reconciler import reconcile_orphan_sessions

logger = logging.getLogger("db_sync")


def sync_all(storage_dir: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Sincroniza todos los perfiles y sesiones hacia SQLite."""
    target_db = db_path or DEFAULT_DB_PATH
    init_database(target_db)

    # Reconciliar sesiones huérfanas o interrumpidas antes de sincronizar
    try:
        reconcile_orphan_sessions(storage_dir)
    except Exception as e:
        logger.warning(f"Advertencia al reconciliar sesiones huérfanas: {e}")

    conn = get_connection(target_db)

    profiles_synced = 0
    words_synced = 0
    sessions_synced = 0

    try:
        # 1. Sincronizar perfiles de usuario
        profiles_dir = os.path.join(storage_dir, "profiles")
        avatars_dir = os.path.join(profiles_dir, "avatars")
        clean_samples_dir = os.path.join(storage_dir, "clean_samples")

        profile_files = []
        if os.path.exists(profiles_dir):
            for entry in os.listdir(profiles_dir):
                full_p = os.path.join(profiles_dir, entry)
                if os.path.isdir(full_p) and entry != "avatars":
                    sub_pf = os.path.join(full_p, "profile.json")
                    if os.path.exists(sub_pf):
                        profile_files.append(sub_pf)
                elif entry.endswith(".json") and not entry.startswith("."):
                    profile_files.append(full_p)

        for pf in profile_files:
            try:
                with open(pf, "r", encoding="utf-8") as f:
                    pdata = json.load(f)

                uid = str(pdata.get("user_id", "")).strip()
                if not uid:
                    continue

                username = pdata.get("username", uid)
                display_name = pdata.get("display_name") or username
                nicknames = json.dumps(pdata.get("nicknames", []) or [], ensure_ascii=False)

                group_role = pdata.get("group_role", {}) or {}
                comm_style = pdata.get("communication_style", {}) or {}
                dialect = pdata.get("dialect_markers", {}) or {}

                primary_role = group_role.get("primary_role", "Participante")
                secondary_role = group_role.get("description", "")
                conflict_style = group_role.get("conflict_style", "")
                humor_type = comm_style.get("humor_type", "conversacional")
                cadence = comm_style.get("cadence", "moderado")

                slang = dialect.get("favorite_slang", []) or []
                fillers = dialect.get("discourse_fillers", []) or []
                preferred_idioms = json.dumps(slang + fillers, ensure_ascii=False)

                speaking_sec = float(pdata.get("total_speaking_seconds", 0.0))
                sessions_count = int(pdata.get("total_sessions_analyzed", 0))

                has_avatar = 1 if os.path.exists(os.path.join(avatars_dir, f"{uid}.png")) else 0
                avatar_url = f"/api/users/{uid}/avatar" if has_avatar else None
                has_voice = 1 if os.path.exists(os.path.join(clean_samples_dir, uid, "sample_clean_prompt.wav")) else 0

                vocab_dict = dialect.get("vocabulary_frequencies", {}) or pdata.get("lexicon_frequency", {}) or {}
                total_words = sum(vocab_dict.values())

                last_updated = pdata.get("last_updated")

                with conn:
                    # Upsert User
                    conn.execute("""
                        INSERT INTO users (
                            user_id, username, display_name, nicknames,
                            primary_role, secondary_role, humor_type, cadence,
                            conflict_style, preferred_idioms, total_speaking_seconds,
                            total_sessions_analyzed, total_words_spoken,
                            has_voice_sample, has_avatar, avatar_url, last_updated
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(user_id) DO UPDATE SET
                            username=excluded.username,
                            display_name=excluded.display_name,
                            nicknames=excluded.nicknames,
                            primary_role=excluded.primary_role,
                            secondary_role=excluded.secondary_role,
                            humor_type=excluded.humor_type,
                            cadence=excluded.cadence,
                            conflict_style=excluded.conflict_style,
                            preferred_idioms=excluded.preferred_idioms,
                            total_speaking_seconds=excluded.total_speaking_seconds,
                            total_sessions_analyzed=excluded.total_sessions_analyzed,
                            total_words_spoken=excluded.total_words_spoken,
                            has_voice_sample=excluded.has_voice_sample,
                            has_avatar=excluded.has_avatar,
                            avatar_url=excluded.avatar_url,
                            last_updated=excluded.last_updated;
                    """, (
                        uid, username, display_name, nicknames,
                        primary_role, secondary_role, humor_type, cadence,
                        conflict_style, preferred_idioms, speaking_sec,
                        sessions_count, total_words,
                        has_voice, has_avatar, avatar_url, last_updated
                    ))

                    # Upsert Big Five
                    big_five = pdata.get("big_five", {}) or {}
                    for trait, tdata in big_five.items():
                        if isinstance(tdata, dict):
                            score = float(tdata.get("score", 0.5))
                            conf = float(tdata.get("confidence", 0.5))
                            quotes = tdata.get("evidence_quotes", []) or []
                            clean_quotes = []
                            for q in quotes:
                                if isinstance(q, dict):
                                    clean_quotes.append(q.get("quote", str(q)))
                                elif isinstance(q, str):
                                    clean_quotes.append(q)
                            quotes_json = json.dumps(clean_quotes, ensure_ascii=False)

                            conn.execute("""
                                INSERT INTO big_five_scores (user_id, trait, score, confidence, evidence_quotes, updated_at)
                                VALUES (?, ?, ?, ?, ?, datetime('now'))
                                ON CONFLICT(user_id, trait) DO UPDATE SET
                                    score=excluded.score,
                                    confidence=excluded.confidence,
                                    evidence_quotes=excluded.evidence_quotes,
                                    updated_at=excluded.updated_at;
                            """, (uid, trait, score, conf, quotes_json))

                    # Upsert Vocabulary
                    for word, freq in vocab_dict.items():
                        w = word.strip().lower()
                        if w:
                            conn.execute("""
                                INSERT INTO vocabulary (user_id, word, frequency)
                                VALUES (?, ?, ?)
                                ON CONFLICT(user_id, word) DO UPDATE SET
                                    frequency=excluded.frequency;
                            """, (uid, w, int(freq)))
                            words_synced += 1

                profiles_synced += 1
            except Exception as e:
                logger.error(f"Error sincronizando perfil {pf}: {e}")

        # 2. Sincronizar sesiones físicas en raw_sessions
        raw_sessions_dir = os.path.join(storage_dir, "raw_sessions")
        if os.path.exists(raw_sessions_dir):
            for s_id in os.listdir(raw_sessions_dir):
                s_path = os.path.join(raw_sessions_dir, s_id)
                if not os.path.isdir(s_path):
                    continue

                meta_file = os.path.join(s_path, "session_metadata.json")
                meta = {}
                if os.path.exists(meta_file):
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                    except Exception:
                        pass

                duration = float(meta.get("duration_seconds", 0.0))
                p_count = len(meta.get("participants", []))

                # Verificar si ya está procesada (tiene transcript.json)
                processed = 1 if os.path.exists(os.path.join(s_path, "transcript.json")) else 0

                with conn:
                    conn.execute("""
                        INSERT INTO sessions (
                            session_id, guild_id, channel_id, channel_name,
                            started_at, ended_at, duration_seconds, participants_count, processed
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(session_id) DO UPDATE SET
                            duration_seconds=excluded.duration_seconds,
                            participants_count=excluded.participants_count,
                            processed=excluded.processed;
                    """, (
                        s_id,
                        meta.get("guild_id"),
                        meta.get("channel_id"),
                        meta.get("channel_name", "General"),
                        meta.get("started_at"),
                        meta.get("ended_at"),
                        duration,
                        p_count,
                        processed
                    ))
                sessions_synced += 1

    finally:
        conn.close()

    return {
        "profiles_synced": profiles_synced,
        "words_synced": words_synced,
        "sessions_synced": sessions_synced,
    }
