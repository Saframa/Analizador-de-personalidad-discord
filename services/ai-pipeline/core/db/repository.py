"""
Capa de Acceso a Datos (Repository) sobre SQLite.
Provee consultas rápidas, tipadas y limpias para el servidor API y la GUI.
"""

import json
import os
from typing import Any, Dict, List, Optional

from core.db.database import get_connection, DEFAULT_DB_PATH


class ProfilerRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH

    def get_connection(self):
        return get_connection(self.db_path)

    def get_global_stats(self) -> Dict[str, Any]:
        """Calcula estadísticas consolidadas a partir de SQLite en <1ms."""
        conn = self.get_connection()
        try:
            # Conteo de sesiones físicas registradas
            sess_row = conn.execute("SELECT COUNT(*) as total_rec, SUM(duration_seconds) as total_dur FROM sessions").fetchone()
            total_sessions_recorded = sess_row["total_rec"] if sess_row else 0

            # Totales de locución y participantes
            user_agg = conn.execute("""
                SELECT 
                    COUNT(*) as participants_count,
                    COALESCE(SUM(total_speaking_seconds), 0.0) as total_seconds,
                    COALESCE(SUM(total_words_spoken), 0) as total_words,
                    COALESCE(MAX(total_sessions_analyzed), 0) as max_analyzed
                FROM users
            """).fetchone()

            total_speaking_seconds = float(user_agg["total_seconds"])
            total_words = int(user_agg["total_words"])
            participants_count = int(user_agg["participants_count"])
            total_sessions_analyzed = int(user_agg["max_analyzed"])

            # Leaderboard ordenado por locución
            users_cur = conn.execute("""
                SELECT 
                    user_id, username, display_name,
                    total_speaking_seconds, cadence, primary_role,
                    has_avatar, avatar_url, has_voice_sample, total_words_spoken, total_unique_words
                FROM users
                ORDER BY total_speaking_seconds DESC
            """).fetchall()

            leaderboard = []
            for u in users_cur:
                sec = float(u["total_speaking_seconds"])
                leaderboard.append({
                    "user_id": u["user_id"],
                    "username": u["username"],
                    "display_name": u["display_name"] or u["username"],
                    "total_speaking_seconds": sec,
                    "total_speaking_formatted": f"{int(sec // 60)}m {int(sec % 60)}s",
                    "cadence": u["cadence"] or "moderado",
                    "primary_role": u["primary_role"] or "Participante",
                    "has_avatar": bool(u["has_avatar"]),
                    "avatar_url": u["avatar_url"],
                    "has_voice_sample": bool(u["has_voice_sample"]),
                    "total_words_spoken": int(u["total_words_spoken"]),
                    "total_unique_words": int(u["total_unique_words"] or 0),
                })

            return {
                "total_sessions_analyzed": total_sessions_analyzed,
                "total_sessions_recorded": max(total_sessions_analyzed, total_sessions_recorded),
                "total_speaking_hours": round(total_speaking_seconds / 3600.0, 2),
                "total_speaking_minutes": round(total_speaking_seconds / 60.0, 1),
                "total_words_cataloged": total_words,
                "participants_count": participants_count,
                "leaderboard": leaderboard,
            }
        finally:
            conn.close()

    def list_users(self) -> List[Dict[str, Any]]:
        """Lista todos los perfiles registrados."""
        conn = self.get_connection()
        try:
            rows = conn.execute("""
                SELECT 
                    user_id, username, display_name, nicknames,
                    primary_role, humor_type, total_speaking_seconds,
                    total_sessions_analyzed, total_words_spoken,
                    has_avatar, avatar_url, has_voice_sample, total_unique_words
                FROM users
                ORDER BY total_speaking_seconds DESC
            """).fetchall()

            result = []
            for r in rows:
                nicks = json.loads(r["nicknames"] or "[]")
                sec = float(r["total_speaking_seconds"])
                result.append({
                    "user_id": r["user_id"],
                    "username": r["username"],
                    "display_name": r["display_name"] or r["username"],
                    "nicknames": nicks,
                    "primary_role": r["primary_role"] or "Participante",
                    "humor_type": r["humor_type"] or "conversacional",
                    "total_speaking_seconds": sec,
                    "speaking_formatted": f"{int(sec // 60)}m",
                    "words_count": int(r["total_words_spoken"]),
                    "unique_words_count": int(r["total_unique_words"] or 0),
                    "total_sessions_analyzed": int(r["total_sessions_analyzed"]),
                    "has_avatar": bool(r["has_avatar"]),
                    "avatar_url": r["avatar_url"],
                    "has_voice_sample": bool(r["has_voice_sample"]),
                })
            return result
        finally:
            conn.close()

    def get_user_detail(self, user_id_or_name: str) -> Optional[Dict[str, Any]]:
        """Obtiene la ficha completa de un usuario con rasgos Big Five y vocabulario."""
        conn = self.get_connection()
        try:
            target = user_id_or_name.lower().strip()
            # Búsqueda directa por ID o username
            u = conn.execute("""
                SELECT * FROM users 
                WHERE user_id = ? OR LOWER(username) = ? OR LOWER(display_name) = ?
            """, (user_id_or_name, target, target)).fetchone()

            if not u:
                # Buscar dentro del array JSON de apodos
                all_u = conn.execute("SELECT * FROM users").fetchall()
                for cand in all_u:
                    nicks = [n.lower() for n in json.loads(cand["nicknames"] or "[]")]
                    if target in nicks:
                        u = cand
                        break

            if not u:
                return None

            uid = u["user_id"]

            # Rasgos Big Five
            bf_rows = conn.execute("""
                SELECT trait, score, confidence, evidence_quotes
                FROM big_five_scores
                WHERE user_id = ?
            """, (uid,)).fetchall()

            big_five = {}
            for row in bf_rows:
                quotes = json.loads(row["evidence_quotes"] or "[]")
                big_five[row["trait"]] = {
                    "score": float(row["score"]),
                    "confidence": float(row["confidence"]),
                    "evidence_quotes": quotes,
                }

            # Si faltara algún rasgo, inicializarlo en neutro
            for t in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]:
                if t not in big_five:
                    big_five[t] = {"score": 0.5, "confidence": 0.5, "evidence_quotes": []}

            # Vocabulario ordenado por frecuencia
            vocab_rows = conn.execute("""
                SELECT word, frequency
                FROM vocabulary
                WHERE user_id = ?
                ORDER BY frequency DESC
                LIMIT 1000
            """, (uid,)).fetchall()

            top_words = [[r["word"], int(r["frequency"])] for r in vocab_rows]
            total_words = int(u["total_words_spoken"])

            # Idiomas / modismos
            idioms = json.loads(u["preferred_idioms"] or "[]")
            nicks = json.loads(u["nicknames"] or "[]")

            return {
                "user_id": uid,
                "username": u["username"],
                "display_name": u["display_name"] or u["username"],
                "nicknames": nicks,
                "total_speaking_seconds": float(u["total_speaking_seconds"]),
                "total_sessions_analyzed": int(u["total_sessions_analyzed"]),
                "speaking_formatted": f"{int(float(u['total_speaking_seconds']) // 60)}m",
                "has_avatar": bool(u["has_avatar"]),
                "avatar_url": u["avatar_url"],
                "has_voice_sample": bool(u["has_voice_sample"]),
                "big_five": big_five,
                "communication_style": {
                    "humor_type": u["humor_type"],
                    "cadence": u["cadence"],
                },
                "group_role": {
                    "primary_role": u["primary_role"],
                    "description": u["secondary_role"],
                    "conflict_style": u["conflict_style"],
                },
                "dialect_markers": {
                    "preferred_idioms": idioms,
                },
                "archetype": {
                    "primary_role": u["primary_role"] or "Participante",
                    "secondary_role": u["secondary_role"] or "",
                    "humor_style": u["humor_type"] or "Conversacional",
                    "dialogue_cadence": u["cadence"] or "Moderado",
                    "preferred_idioms": idioms,
                },
                "lexicon": {
                    "top_words": top_words,
                    "total_words": total_words,
                    "unique_words": len(top_words),
                    "total_unique_words": int(u["total_unique_words"] or 0),
                },
            }
        finally:
            conn.close()

    def update_user_metadata(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        nicknames: Optional[List[str]] = None,
        role: Optional[str] = None,
        humor: Optional[str] = None,
    ) -> bool:
        """Actualiza metadatos de un usuario en SQLite."""
        conn = self.get_connection()
        try:
            fields = []
            params = []
            if display_name is not None:
                fields.append("display_name = ?")
                params.append(display_name.strip())
            if nicknames is not None:
                fields.append("nicknames = ?")
                params.append(json.dumps([n.strip() for n in nicknames if n.strip()], ensure_ascii=False))
            if role is not None:
                fields.append("primary_role = ?")
                params.append(role.strip())
            if humor is not None:
                fields.append("humor_type = ?")
                params.append(humor.strip())

            if not fields:
                return False

            params.append(user_id)
            with conn:
                conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?", params)
            return True
        finally:
            conn.close()

    def update_avatar_status(self, user_id: str, has_avatar: bool, avatar_url: Optional[str]):
        conn = self.get_connection()
        try:
            with conn:
                conn.execute(
                    "UPDATE users SET has_avatar = ?, avatar_url = ? WHERE user_id = ?",
                    (1 if has_avatar else 0, avatar_url, user_id)
                )
        finally:
            conn.close()

    def save_chat_message(self, user_id: str, sender: str, message: str, model_used: Optional[str] = None):
        conn = self.get_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT INTO chat_logs (user_id, sender, message, model_used)
                    VALUES (?, ?, ?, ?)
                """, (user_id, sender, message, model_used))
        finally:
            conn.close()

    def clear_chat_history(self, user_id: str):
        conn = self.get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM chat_logs WHERE user_id = ?", (user_id,))
        finally:
            conn.close()

    def get_social_graph(self) -> Dict[str, Any]:
        """
        Retorna la red de interacciones, afinidad y conexiones sociales
        entre los participantes del servidor a partir de las sesiones compartidas.
        """
        conn = self.get_connection()
        try:
            user_rows = conn.execute("""
                SELECT user_id, username, display_name, primary_role, humor_type, 
                       cadence, total_speaking_seconds, total_sessions_analyzed, 
                       has_avatar, avatar_url
                FROM users
                ORDER BY total_speaking_seconds DESC
            """).fetchall()

            user_map = {}
            nodes = []
            max_sec = max([float(u["total_speaking_seconds"]) for u in user_rows], default=1.0)
            if max_sec <= 0:
                max_sec = 1.0

            for u in user_rows:
                sec = float(u["total_speaking_seconds"])
                user_map[u["user_id"]] = u
                nodes.append({
                    "id": u["user_id"],
                    "username": u["username"],
                    "display_name": u["display_name"] or u["username"],
                    "primary_role": u["primary_role"] or "Participante",
                    "humor_type": u["humor_type"] or "Conversacional",
                    "cadence": u["cadence"] or "moderado",
                    "total_speaking_seconds": sec,
                    "total_sessions_analyzed": int(u["total_sessions_analyzed"]),
                    "speaking_formatted": f"{int(sec // 60)}m",
                    "has_avatar": bool(u["has_avatar"]),
                    "avatar_url": u["avatar_url"],
                    "size_weight": max(0.25, min(1.0, sec / max_sec)),
                })

            pairs_cur = conn.execute("""
                SELECT 
                    sp1.user_id as u1,
                    sp2.user_id as u2,
                    COUNT(DISTINCT sp1.session_id) as sessions_together,
                    SUM(sp1.speaking_seconds + sp2.speaking_seconds) as shared_speaking_sec
                FROM session_participants sp1
                JOIN session_participants sp2 ON sp1.session_id = sp2.session_id AND sp1.user_id < sp2.user_id
                GROUP BY sp1.user_id, sp2.user_id
                ORDER BY sessions_together DESC
            """).fetchall()

            edges = []
            max_sessions = max([int(p["sessions_together"]) for p in pairs_cur], default=1)
            if max_sessions <= 0:
                max_sessions = 1

            for p in pairs_cur:
                u1_id = p["u1"]
                u2_id = p["u2"]
                if u1_id not in user_map or u2_id not in user_map:
                    continue

                together = int(p["sessions_together"])
                shared_sec = float(p["shared_speaking_sec"])
                affinity = round(max(0.1, min(1.0, together / max_sessions)), 3)

                edges.append({
                    "source": u1_id,
                    "target": u2_id,
                    "sessions_together": together,
                    "shared_speaking_seconds": shared_sec,
                    "shared_speaking_formatted": f"{int(shared_sec // 60)}m",
                    "affinity": affinity,
                    "weight": affinity,
                })

            top_pair = None
            if edges:
                top = edges[0]
                u1_obj = user_map[top["source"]]
                u2_obj = user_map[top["target"]]
                top_pair = {
                    "u1_id": top["source"],
                    "u2_id": top["target"],
                    "u1_name": u1_obj["display_name"] or u1_obj["username"],
                    "u2_name": u2_obj["display_name"] or u2_obj["username"],
                    "sessions_together": top["sessions_together"],
                    "shared_time": top["shared_speaking_formatted"],
                }

            return {
                "nodes": nodes,
                "edges": edges,
                "stats": {
                    "total_nodes": len(nodes),
                    "total_edges": len(edges),
                    "top_pair": top_pair,
                }
            }
        finally:
            conn.close()
