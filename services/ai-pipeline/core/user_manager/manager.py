"""
Gestor Integral de Usuarios y Perfiles (UserManager).
Permite crear, consultar, listar y personalizar perfiles de amigos antes o después de las llamadas.
"""

from datetime import datetime, timezone
import glob
import json
import logging
import os
from typing import Any, Dict, List, Optional

from core.contracts.models import (
    BigFiveTraits,
    CommunicationStyle,
    DialectMarkers,
    GroupRole,
    TraitEvaluation,
    UserProfile,
)

logger = logging.getLogger(__name__)


class UserManager:
    def __init__(self, base_storage_dir: str):
        self.base_storage_dir = os.path.abspath(base_storage_dir)
        self.profiles_dir = os.path.join(self.base_storage_dir, "profiles")
        self.clean_samples_dir = os.path.join(self.base_storage_dir, "clean_samples")
        os.makedirs(self.profiles_dir, exist_ok=True)
        os.makedirs(self.clean_samples_dir, exist_ok=True)

    def list_users(self) -> List[UserProfile]:
        """Retorna todos los perfiles de usuario registrados en storage/profiles/."""
        users: List[UserProfile] = []
        for profile_file in glob.glob(os.path.join(self.profiles_dir, "*", "profile.json")):
            try:
                with open(profile_file, "r", encoding="utf-8") as f:
                    users.append(UserProfile.model_validate_json(f.read()))
            except Exception as e:
                logger.warning(f"No se pudo cargar {profile_file}: {e}")
        return sorted(users, key=lambda u: u.username.lower())

    def get_user(self, query: str) -> Optional[UserProfile]:
        """
        Busca un usuario por user_id, username, display_name o cualquiera de sus apodos/nicknames.
        La búsqueda no distingue mayúsculas de minúsculas.
        """
        query_norm = query.strip().lower()
        if not query_norm:
            return None

        # Intento de lectura directa por user_id
        direct_path = os.path.join(self.profiles_dir, query_norm, "profile.json")
        if os.path.exists(direct_path):
            try:
                with open(direct_path, "r", encoding="utf-8") as f:
                    return UserProfile.model_validate_json(f.read())
            except Exception:
                pass

        # Búsqueda en todos los perfiles
        for user in self.list_users():
            if user.user_id.lower() == query_norm:
                return user
            if user.username.lower() == query_norm:
                return user
            if user.display_name and user.display_name.lower() == query_norm:
                return user
            if any(nick.lower() == query_norm for nick in user.nicknames):
                return user

        return None

    def create_user(
        self,
        user_id: str,
        username: str,
        display_name: Optional[str] = None,
        nicknames: Optional[List[str]] = None,
        notes: Optional[List[str]] = None,
        primary_role: Optional[str] = None,
        humor_type: Optional[str] = None,
    ) -> UserProfile:
        """
        Crea un nuevo perfil base para un amigo.
        Si ya existe, actualiza los datos proporcionados.
        """
        existing = self.get_user(user_id)
        if existing:
            return self.update_user(
                user_id=existing.user_id,
                display_name=display_name,
                add_nicknames=nicknames,
                add_notes=notes,
                primary_role=primary_role,
                humor_type=humor_type,
            )

        now = datetime.now(timezone.utc)
        clean_nicks = [n.strip() for n in (nicknames or []) if n.strip()]
        clean_notes = [n.strip() for n in (notes or []) if n.strip()]

        default_trait = TraitEvaluation(score=0.5, confidence=0.2, evidence_quotes=[])

        profile = UserProfile(
            version="1.0.0",
            user_id=user_id.strip(),
            username=username.strip(),
            display_name=display_name.strip() if display_name else None,
            last_updated=now,
            total_sessions_analyzed=1,
            total_speaking_seconds=0.0,
            big_five=BigFiveTraits(
                openness=default_trait.model_copy(),
                conscientiousness=default_trait.model_copy(),
                extraversion=default_trait.model_copy(),
                agreeableness=default_trait.model_copy(),
                neuroticism=default_trait.model_copy(),
            ),
            communication_style=CommunicationStyle(
                avg_words_per_turn=12.0,
                cadence="moderado",
                interruption_ratio=0.1,
                humor_type=humor_type or "chicanas afectuosas e ironía cómplice",
            ),
            group_role=GroupRole(
                primary_role=primary_role or "El Participante",
                description="Perfil inicializado en el sistema",
                conflict_style="conciliador",
            ),
            dialect_markers=DialectMarkers(
                rioplatense_frequency=0.5,
                favorite_slang=["bo", "ta", "flama"],
                discourse_fillers=["bo", "ta", "mirá"],
            ),
            clean_voice_samples=[],
            nicknames=clean_nicks,
            notes=clean_notes,
        )

        user_dir = os.path.join(self.profiles_dir, profile.user_id)
        os.makedirs(user_dir, exist_ok=True)
        profile_path = os.path.join(user_dir, "profile.json")
        profile.save_atomic(profile_path)
        logger.info(f"Usuario {profile.username} (@{profile.user_id}) creado exitosamente en {profile_path}.")
        return profile

    def update_user(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        add_nicknames: Optional[List[str]] = None,
        add_notes: Optional[List[str]] = None,
        primary_role: Optional[str] = None,
        humor_type: Optional[str] = None,
    ) -> UserProfile:
        """Actualiza campos específicos y agrega apodos o notas sin duplicar."""
        profile = self.get_user(user_id)
        if not profile:
            raise FileNotFoundError(f"Usuario con identificador '{user_id}' no encontrado.")

        if display_name is not None and display_name.strip():
            profile.display_name = display_name.strip()

        if add_nicknames:
            current_nicks = set(n.lower() for n in profile.nicknames)
            for nick in add_nicknames:
                n_clean = nick.strip()
                if n_clean and n_clean.lower() not in current_nicks:
                    profile.nicknames.append(n_clean)
                    current_nicks.add(n_clean.lower())

        if add_notes:
            for note in add_notes:
                note_clean = note.strip()
                if note_clean and note_clean not in profile.notes:
                    profile.notes.append(note_clean)

        if primary_role is not None and primary_role.strip():
            profile.group_role.primary_role = primary_role.strip()

        if humor_type is not None and humor_type.strip():
            profile.communication_style.humor_type = humor_type.strip()

        profile.last_updated = datetime.now(timezone.utc)
        user_dir = os.path.join(self.profiles_dir, profile.user_id)
        profile_path = os.path.join(user_dir, "profile.json")
        profile.save_atomic(profile_path)
        return profile

    def has_clean_sample(self, user_id: str) -> bool:
        """Verifica si el usuario cuenta con una muestra de voz curada para clonación."""
        user_sample_dir = os.path.join(self.clean_samples_dir, user_id)
        return (
            os.path.exists(os.path.join(user_sample_dir, "sample_clean_60s.wav"))
            or os.path.exists(os.path.join(user_sample_dir, "sample_clean_prompt.wav"))
        )

    def get_summary_table(self) -> List[Dict[str, Any]]:
        """Genera un resumen tabular para la visualización en la terminal."""
        users = self.list_users()
        summary = []
        for u in users:
            has_voice = self.has_clean_sample(u.user_id)
            nicks_str = ", ".join(u.nicknames) if u.nicknames else "-"
            notes_count = len(u.notes)
            summary.append(
                {
                    "user_id": u.user_id,
                    "username": u.username,
                    "display_name": u.display_name or "-",
                    "role": u.group_role.primary_role,
                    "sessions": u.total_sessions_analyzed,
                    "speaking_sec": f"{u.total_speaking_seconds:.1f}s",
                    "nicknames": nicks_str,
                    "notes_count": notes_count,
                    "voice_ready": "✅ Sí" if has_voice else "⏳ Pendiente",
                }
            )
        return summary
