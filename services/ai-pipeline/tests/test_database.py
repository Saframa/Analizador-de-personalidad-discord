"""
Pruebas unitarias para el módulo de base de datos SQLite (core.db).
"""

import os
import tempfile
import pytest

from core.db.database import init_database, get_connection
from core.db.repository import ProfilerRepository
from core.db.sync import sync_all


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_database(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_sqlite_init_and_repository(temp_db):
    repo = ProfilerRepository(temp_db)
    conn = repo.get_connection()
    try:
        # Insertar un usuario de prueba
        with conn:
            conn.execute("""
                INSERT INTO users (
                    user_id, username, display_name, total_speaking_seconds, total_words_spoken
                ) VALUES (?, ?, ?, ?, ?)
            """, ("test_user_1", "testuser", "Usuario Test", 120.5, 350))

            conn.execute("""
                INSERT INTO big_five_scores (user_id, trait, score, confidence, evidence_quotes)
                VALUES (?, ?, ?, ?, ?)
            """, ("test_user_1", "openness", 0.75, 0.9, '["Cita de prueba"]'))

            conn.execute("""
                INSERT INTO vocabulary (user_id, word, frequency)
                VALUES (?, ?, ?)
            """, ("test_user_1", "flama", 15))
    finally:
        conn.close()

    # Probar list_users
    users = repo.list_users()
    assert len(users) == 1
    assert users[0]["user_id"] == "test_user_1"
    assert users[0]["display_name"] == "Usuario Test"
    assert users[0]["words_count"] == 350

    # Probar get_user_detail
    detail = repo.get_user_detail("test_user_1")
    assert detail is not None
    assert detail["user_id"] == "test_user_1"
    assert detail["big_five"]["openness"]["score"] == 0.75
    assert detail["big_five"]["openness"]["evidence_quotes"] == ["Cita de prueba"]
    assert detail["lexicon"]["top_words"] == [["flama", 15]]

    # Probar get_global_stats
    stats = repo.get_global_stats()
    assert stats["participants_count"] == 1
    assert stats["total_words_cataloged"] == 350
    assert len(stats["leaderboard"]) == 1


def test_sqlite_sync(temp_db):
    # Sincronizar storage real hacia temp_db
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    storage_dir = os.path.join(root_dir, "storage")
    if os.path.exists(storage_dir):
        res = sync_all(storage_dir, temp_db)
        assert res["profiles_synced"] >= 1
        repo = ProfilerRepository(temp_db)
        users = repo.list_users()
        assert len(users) >= 1
