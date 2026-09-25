"""
Test Suite: Validación Automatizada de Contratos de Datos (Fase 0)
Verifica la conformidad estricta entre JSON Schemas Draft-07, fixtures y modelos Pydantic v2.
"""

import json
import os
import sys
import pytest
import jsonschema
from pydantic import ValidationError

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.contracts.models import (
    SessionMetadata,
    SessionTranscript,
    UserProfile,
)

FIXTURES_DIR = os.path.join(BASE_DIR, "tests", "fixtures")
DOCS_SPECS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "docs", "specs"))


def load_json(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ==============================================================================
# 1. VERIFICACIÓN CONTRA JSON SCHEMAS FORMALES (Draft-07)
# ==============================================================================

class TestJsonSchemaValidation:
    """Verifica que los fixtures cumplan con los JSON Schemas formales en docs/specs/."""

    def test_session_metadata_schema_valid(self):
        schema = load_json(os.path.join(DOCS_SPECS_DIR, "session_metadata.schema.json"))
        data = load_json(os.path.join(FIXTURES_DIR, "sample_session_metadata.json"))
        # No debe lanzar jsonschema.exceptions.ValidationError
        jsonschema.validate(instance=data, schema=schema)

    def test_transcript_schema_valid(self):
        schema = load_json(os.path.join(DOCS_SPECS_DIR, "transcript.schema.json"))
        data = load_json(os.path.join(FIXTURES_DIR, "sample_transcript.json"))
        jsonschema.validate(instance=data, schema=schema)

    def test_user_profile_schema_valid(self):
        schema = load_json(os.path.join(DOCS_SPECS_DIR, "user_profile.schema.json"))
        data = load_json(os.path.join(FIXTURES_DIR, "sample_user_profile.json"))
        jsonschema.validate(instance=data, schema=schema)

    def test_multidimensional_user_profile_schema_valid(self):
        schema = load_json(os.path.join(DOCS_SPECS_DIR, "user_profile.schema.json"))
        data = load_json(os.path.join(FIXTURES_DIR, "sample_user_profile.json"))
        data["social_dynamics"] = {
            "affinities": {
                "222222222222222222": {
                    "user_id": "222222222222222222",
                    "username": "kevinjaffe",
                    "interaction_count": 5,
                    "reply_count": 3,
                    "affinity_score": 0.85,
                    "notes": "amigo cercano",
                }
            },
            "closest_friends": ["kevinjaffe"],
            "teasing_targets": ["kevinjaffe"],
        }
        data["group_lore"] = {
            "inside_jokes": ["dar flama", "el bot"],
            "external_entities": ["Discord", "Twitch"],
            "notable_anecdotes": ["la partida de lol"],
        }
        data["emotional_triggers"] = {
            "tilts": ["lag"],
            "hyperfocus_topics": ["programacion"],
        }
        data["activity_initiative"] = {
            "initiative_level": "iniciador",
            "proposes_activities": True,
            "departure_pattern": "variable",
            "typical_proposals": ["jugar lol"],
        }
        data["temporal_patterns"] = {
            "cronotype": "noctambulo",
            "peak_hours": ["noche (19:00 - 23:59)"],
            "late_night_attitude": "relajado",
        }
        jsonschema.validate(instance=data, schema=schema)
        profile = UserProfile.model_validate(data)
        assert profile.social_dynamics.closest_friends == ["kevinjaffe"]
        assert profile.group_lore.inside_jokes == ["dar flama", "el bot"]


# ==============================================================================
# 2. VERIFICACIÓN CON MODELOS PYDANTIC V2
# ==============================================================================

class TestPydanticModelValidation:
    """Verifica que los modelos Pydantic parseen y validen los contratos correctamente."""

    def test_pydantic_session_metadata(self):
        data = load_json(os.path.join(FIXTURES_DIR, "sample_session_metadata.json"))
        session = SessionMetadata.model_validate(data)
        assert session.version == "1.0.0"
        assert session.session_id == "2026-09-24_21-30-00"
        assert len(session.participants) == 2
        assert session.audio_files["111111111111111111"].sample_rate == 48000

    def test_pydantic_transcript(self):
        data = load_json(os.path.join(FIXTURES_DIR, "sample_transcript.json"))
        transcript = SessionTranscript.model_validate(data)
        assert transcript.model == "faster-whisper-large-v3"
        assert len(transcript.utterances) == 3
        assert "bo" in transcript.utterances[0].text.lower()

    def test_pydantic_user_profile(self):
        data = load_json(os.path.join(FIXTURES_DIR, "sample_user_profile.json"))
        profile = UserProfile.model_validate(data)
        assert profile.user_id == "111111111111111111"
        assert profile.big_five.extraversion.score == 0.85
        assert len(profile.big_five.extraversion.evidence_quotes) >= 1
        assert "salado" in profile.dialect_markers.favorite_slang


# ==============================================================================
# 3. VERIFICACIÓN DE RECHAZO DE DATOS INVÁLIDOS (LÍMITES Y CONDICIONES)
# ==============================================================================

class TestNegativeValidation:
    """Asegura que cualquier violación de contrato sea rechazada inmediatamente."""

    def test_invalid_session_id_format_rejected(self):
        data = load_json(os.path.join(FIXTURES_DIR, "sample_session_metadata.json"))
        data["session_id"] = "invalid_date_format_123"
        with pytest.raises(ValidationError):
            SessionMetadata.model_validate(data)

    def test_invalid_score_range_rejected(self):
        data = load_json(os.path.join(FIXTURES_DIR, "sample_user_profile.json"))
        # Un score mayor a 1.0 debe ser rechazado
        data["big_five"]["openness"]["score"] = 1.5
        with pytest.raises(ValidationError):
            UserProfile.model_validate(data)

    def test_atomic_save_and_reload(self, tmp_path):
        data = load_json(os.path.join(FIXTURES_DIR, "sample_user_profile.json"))
        profile = UserProfile.model_validate(data)

        target_file = str(tmp_path / "test_profile.json")
        profile.save_atomic(target_file)

        assert os.path.exists(target_file)
        reloaded = UserProfile.model_validate(load_json(target_file))
        assert reloaded.user_id == profile.user_id
