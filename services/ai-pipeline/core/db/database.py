"""
Módulo de Base de Datos SQLite para Discord Profiler & Digital Twin.
Centraliza perfiles, evolución Big Five, vocabulario, sesiones y chat histórico.
"""

import os
import sqlite3
from typing import Optional

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_PIPELINE_DIR = os.path.dirname(os.path.dirname(CURRENT_DIR))
ROOT_DIR = os.path.abspath(os.path.join(AI_PIPELINE_DIR, "..", ".."))
DEFAULT_DB_PATH = os.path.join(ROOT_DIR, "storage", "profiler.db")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Obtiene una conexión a la base de datos SQLite con WAL y row_factory."""
    path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_database(db_path: Optional[str] = None) -> None:
    """Crea las tablas e índices si no existen."""
    conn = get_connection(db_path)
    try:
        with conn:
            conn.executescript("""
                -- Tabla de Usuarios y Perfiles
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    display_name TEXT,
                    nicknames TEXT, -- JSON array de strings
                    primary_role TEXT DEFAULT 'Participante',
                    secondary_role TEXT,
                    humor_type TEXT DEFAULT 'conversacional',
                    cadence TEXT DEFAULT 'moderado',
                    conflict_style TEXT,
                    preferred_idioms TEXT, -- JSON array de strings
                    total_speaking_seconds REAL DEFAULT 0.0,
                    total_sessions_analyzed INTEGER DEFAULT 0,
                    total_words_spoken INTEGER DEFAULT 0,
                    total_unique_words INTEGER DEFAULT 0,
                    has_voice_sample INTEGER DEFAULT 0,
                    has_avatar INTEGER DEFAULT 0,
                    avatar_url TEXT,
                    last_updated TEXT
                );

                -- Tabla de Rasgos Big Five
                CREATE TABLE IF NOT EXISTS big_five_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    trait TEXT NOT NULL, -- openness, conscientiousness, extraversion, agreeableness, neuroticism
                    score REAL NOT NULL,
                    confidence REAL NOT NULL,
                    evidence_quotes TEXT, -- JSON array de quotes (strings)
                    updated_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    UNIQUE (user_id, trait)
                );

                -- Tabla de Vocabulario Indexado
                CREATE TABLE IF NOT EXISTS vocabulary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    word TEXT NOT NULL,
                    frequency INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    UNIQUE (user_id, word)
                );

                CREATE INDEX IF NOT EXISTS idx_vocab_user_freq 
                ON vocabulary(user_id, frequency DESC);

                CREATE INDEX IF NOT EXISTS idx_vocab_word 
                ON vocabulary(word);

                -- Tabla de Sesiones de Discord
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    guild_id TEXT,
                    channel_id TEXT,
                    channel_name TEXT,
                    started_at TEXT,
                    ended_at TEXT,
                    duration_seconds REAL DEFAULT 0.0,
                    participants_count INTEGER DEFAULT 0,
                    processed INTEGER DEFAULT 0
                );

                -- Participación por Sesión
                CREATE TABLE IF NOT EXISTS session_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    speaking_seconds REAL DEFAULT 0.0,
                    words_count INTEGER DEFAULT 0,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    UNIQUE (session_id, user_id)
                );

                -- Historial de Conversación con Gemelos
                CREATE TABLE IF NOT EXISTS chat_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    sender TEXT NOT NULL, -- 'user' | 'assistant'
                    message TEXT NOT NULL,
                    model_used TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_chat_user 
                ON chat_logs(user_id, id ASC);
            """)
    finally:
        conn.close()

    # Migration: add total_unique_words column if DB already exists without it
    _conn2 = get_connection(db_path)
    try:
        _col_exists = _conn2.execute(
            "SELECT COUNT(*) FROM pragma_table_info('users') WHERE name='total_unique_words'"
        ).fetchone()[0]
        if not _col_exists:
            with _conn2:
                _conn2.execute("ALTER TABLE users ADD COLUMN total_unique_words INTEGER DEFAULT 0")
    finally:
        _conn2.close()
