"""
Tests unitarios para el Gestor de Usuarios (UserManager).
"""

import os
import tempfile
import pytest

from core.user_manager.manager import UserManager


def test_create_and_get_user():
    with tempfile.TemporaryDirectory() as tmp_dir:
        manager = UserManager(tmp_dir)
        user = manager.create_user(
            user_id="123456789",
            username="nacho",
            display_name="El Nacho",
            nicknames=["nachito", "nacho_fiera"],
            notes=["Le gusta jugar support", "Hincha de Peñarol"],
        )

        assert user.user_id == "123456789"
        assert user.username == "nacho"
        assert user.display_name == "El Nacho"
        assert "nachito" in user.nicknames
        assert len(user.notes) == 2

        # Búsqueda por ID
        by_id = manager.get_user("123456789")
        assert by_id is not None
        assert by_id.username == "nacho"

        # Búsqueda por username (case insensitive)
        by_name = manager.get_user("NACHO")
        assert by_name is not None
        assert by_name.user_id == "123456789"

        # Búsqueda por apodo
        by_nick = manager.get_user("nacho_fiera")
        assert by_nick is not None
        assert by_nick.user_id == "123456789"


def test_update_user_nicknames_and_notes():
    with tempfile.TemporaryDirectory() as tmp_dir:
        manager = UserManager(tmp_dir)
        manager.create_user(user_id="999", username="pedro", nicknames=["pepe"])

        updated = manager.update_user(
            user_id="999",
            display_name="Don Pedro",
            add_nicknames=["pepito", "pepe"],  # 'pepe' ya existe, no debe duplicar
            add_notes=["Siempre se va a cenar a las 21hs"],
            primary_role="El Estratega",
        )

        assert updated.display_name == "Don Pedro"
        assert updated.group_role.primary_role == "El Estratega"
        assert len(updated.nicknames) == 2  # pepe, pepito
        assert len(updated.notes) == 1


def test_list_users():
    with tempfile.TemporaryDirectory() as tmp_dir:
        manager = UserManager(tmp_dir)
        manager.create_user(user_id="1", username="alberto")
        manager.create_user(user_id="2", username="beatriz")

        users = manager.list_users()
        assert len(users) == 2
        assert users[0].username == "alberto"
        assert users[1].username == "beatriz"


def test_summary_table():
    with tempfile.TemporaryDirectory() as tmp_dir:
        manager = UserManager(tmp_dir)
        manager.create_user(user_id="438796478035787780", username="marce", nicknames=["fiera"])

        table = manager.get_summary_table()
        assert len(table) == 1
        assert table[0]["username"] == "marce"
        assert "fiera" in table[0]["nicknames"]
        assert "voice_ready" in table[0]
