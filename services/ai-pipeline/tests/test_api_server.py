"""
Tests unitarios para la API local de FastAPI (servidor para Electron GUI).
"""

import os
import sys

# Asegurar importación de api.server independientemente del directorio de ejecución
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from fastapi.testclient import TestClient
import pytest

from api.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_api_status(client):
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert "hardware" in data
    assert "cpu_percent" in data["hardware"]
    assert "gpu" in data["hardware"]
    assert "daemons" in data
    assert "recorder" in data["daemons"]
    assert "watcher" in data["daemons"]


def test_api_global_stats(client):
    res = client.get("/api/stats/global")
    assert res.status_code == 200
    data = res.json()
    assert "total_sessions_analyzed" in data
    assert "total_speaking_hours" in data
    assert "leaderboard" in data
    assert isinstance(data["leaderboard"], list)


def test_api_users_list(client):
    res = client.get("/api/users")
    assert res.status_code == 200
    users = res.json()
    assert isinstance(users, list)
    if len(users) > 0:
        u = users[0]
        assert "user_id" in u
        assert "username" in u
        assert "display_name" in u


def test_api_user_detail(client):
    res_list = client.get("/api/users")
    users = res_list.json()
    if users:
        target_id = users[0]["user_id"]
        res = client.get(f"/api/users/{target_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == target_id
        assert "big_five" in data
        assert "communication_style" in data
