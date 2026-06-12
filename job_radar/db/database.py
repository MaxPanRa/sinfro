"""Acceso a SQLite: esquema, conexión segura entre hilos y operaciones CRUD.

Una sola instancia de :class:`Database` se comparte en toda la app. La conexión
usa ``check_same_thread=False`` + un ``RLock`` para permitir escrituras desde los
workers de ``QThreadPool`` sin corromper la base. Se activa WAL para concurrencia.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..config import DB_PATH, DEFAULT_SETTINGS


def _now_iso() -> str:
    """Fecha-hora actual en ISO-8601 UTC (para guardar timestamps)."""
    return datetime.now(timezone.utc).isoformat()


#: DDL completo. Se ejecuta con ``executescript`` de forma idempotente.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    uid                TEXT PRIMARY KEY,          -- hash sha1 de (título + empresa)
    title              TEXT NOT NULL,
    company            TEXT,
    source             TEXT NOT NULL,             -- nombre de la fuente
    url                TEXT,
    location           TEXT,
    modality           TEXT,                      -- Remoto/Híbrido/Presencial/?
    description        TEXT,
    raw_json           TEXT,                      -- payload original de la fuente
    detected_at        TEXT NOT NULL,
    seen               INTEGER NOT NULL DEFAULT 0,
    applied            INTEGER NOT NULL DEFAULT 0,
    applied_at         TEXT,
    discarded          INTEGER NOT NULL DEFAULT 0,
    quick_score        INTEGER,                   -- 0-100 de la clasificación
    classification_json TEXT                      -- JSON crudo de la clasificación
);

CREATE TABLE IF NOT EXISTS evaluations (
    uid         TEXT PRIMARY KEY REFERENCES jobs(uid) ON DELETE CASCADE,
    markdown    TEXT NOT NULL,
    model       TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS keywords (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS technologies (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT NOT NULL UNIQUE,
    level  INTEGER NOT NULL DEFAULT 5,            -- 1-10
    origin TEXT NOT NULL DEFAULT 'manual'         -- 'manual' | 'cv'
);

CREATE TABLE IF NOT EXISTS profile (
    id      INTEGER PRIMARY KEY CHECK (id = 1),   -- fila única
    summary TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS quotas (
    period TEXT PRIMARY KEY,                       -- ej. 'serpapi:2026-06'
    count  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name  TEXT NOT NULL,                     -- 'A' | 'B'
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT,                              -- 'ok' | 'error' | 'running'
    message     TEXT,
    found_count INTEGER DEFAULT 0,
    day_key     TEXT                               -- 'YYYY-MM-DD' (para Grupo B)
);

CREATE INDEX IF NOT EXISTS idx_jobs_detected ON jobs(detected_at);
CREATE INDEX IF NOT EXISTS idx_jobs_states ON jobs(seen, applied, discarded);
"""


class Database:
    """Fachada de acceso a datos. Thread-safe vía lock global."""

    def __init__(self, path: Path | str = DB_PATH) -> None:
        self._path = str(path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._init_schema()

    # -- Infraestructura ------------------------------------------------------

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)
            # Fila única de perfil.
            self._conn.execute(
                "INSERT OR IGNORE INTO profile (id, summary) VALUES (1, '')"
            )
            # Settings por defecto (sin pisar lo ya guardado).
            for key, value in DEFAULT_SETTINGS.items():
                self._conn.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (key, value),
                )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            self._conn.commit()
            return cur

    def _query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, tuple(params)).fetchall()

    # -- Settings -------------------------------------------------------------

    def get_setting(self, key: str, default: str = "") -> str:
        rows = self._query("SELECT value FROM settings WHERE key = ?", (key,))
        return rows[0]["value"] if rows else default

    def get_all_settings(self) -> dict[str, str]:
        rows = self._query("SELECT key, value FROM settings")
        return {r["key"]: (r["value"] or "") for r in rows}

    def set_setting(self, key: str, value: str) -> None:
        self._execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    # -- Perfil ---------------------------------------------------------------

    def get_profile_summary(self) -> str:
        rows = self._query("SELECT summary FROM profile WHERE id = 1")
        return rows[0]["summary"] if rows else ""

    def set_profile_summary(self, summary: str) -> None:
        self._execute("UPDATE profile SET summary = ? WHERE id = 1", (summary,))

    # -- Keywords -------------------------------------------------------------

    def get_keywords(self) -> list[str]:
        return [r["word"] for r in self._query("SELECT word FROM keywords ORDER BY word")]

    def add_keyword(self, word: str) -> None:
        word = word.strip().lower()
        if word:
            self._execute("INSERT OR IGNORE INTO keywords (word) VALUES (?)", (word,))

    def remove_keyword(self, word: str) -> None:
        self._execute("DELETE FROM keywords WHERE word = ?", (word.strip().lower(),))

    def seed_keywords_if_empty(self, words: list[str]) -> None:
        if not self.get_keywords():
            for w in words:
                self.add_keyword(w)

    # -- Tecnologías ----------------------------------------------------------

    def get_technologies(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._query(
            "SELECT id, name, level, origin FROM technologies ORDER BY name"
        )]

    def upsert_technology(self, name: str, level: int, origin: str = "manual") -> None:
        """Inserta o actualiza una tecnología sin duplicar (clave = nombre).

        Si ya existe una manual, no la pisa una detectada del CV (respeta lo manual).
        """
        name = name.strip()
        if not name:
            return
        existing = self._query(
            "SELECT origin FROM technologies WHERE lower(name) = lower(?)", (name,)
        )
        if existing:
            # No degradar una manual a 'cv'; sí permitir actualizar nivel manual.
            if origin == "manual":
                self._execute(
                    "UPDATE technologies SET level = ?, origin = 'manual' "
                    "WHERE lower(name) = lower(?)",
                    (level, name),
                )
            return
        self._execute(
            "INSERT INTO technologies (name, level, origin) VALUES (?, ?, ?)",
            (name, level, origin),
        )

    def remove_technology(self, tech_id: int) -> None:
        self._execute("DELETE FROM technologies WHERE id = ?", (tech_id,))

    # -- Jobs -----------------------------------------------------------------

    def job_exists(self, uid: str) -> bool:
        return bool(self._query("SELECT 1 FROM jobs WHERE uid = ?", (uid,)))

    def insert_job(self, job: dict[str, Any]) -> bool:
        """Inserta una vacante nueva. Devuelve False si el uid ya existía."""
        if self.job_exists(job["uid"]):
            return False
        self._execute(
            """INSERT INTO jobs
               (uid, title, company, source, url, location, modality,
                description, raw_json, detected_at, seen, applied, discarded)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)""",
            (
                job["uid"], job.get("title", ""), job.get("company", ""),
                job.get("source", ""), job.get("url", ""), job.get("location", ""),
                job.get("modality", ""), job.get("description", ""),
                json.dumps(job.get("raw", {}), ensure_ascii=False), _now_iso(),
            ),
        )
        return True

    def set_quick_classification(self, uid: str, score: int, data: dict[str, Any]) -> None:
        self._execute(
            "UPDATE jobs SET quick_score = ?, classification_json = ? WHERE uid = ?",
            (score, json.dumps(data, ensure_ascii=False), uid),
        )

    def mark_seen(self, uid: str) -> None:
        self._execute("UPDATE jobs SET seen = 1 WHERE uid = ?", (uid,))

    def mark_applied(self, uid: str) -> None:
        self._execute(
            "UPDATE jobs SET applied = 1, applied_at = ? WHERE uid = ? AND applied = 0",
            (_now_iso(), uid),
        )

    def mark_discarded(self, uid: str) -> None:
        self._execute("UPDATE jobs SET discarded = 1 WHERE uid = ?", (uid,))

    def get_job(self, uid: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM jobs WHERE uid = ?", (uid,))
        return dict(rows[0]) if rows else None

    def list_jobs(
        self,
        *,
        filtro: str = "todas",
        show_duplicates: bool = False,
    ) -> list[dict[str, Any]]:
        """Lista vacantes para la bandeja, ordenadas por fecha de detección desc.

        filtro: 'todas' | 'no_vistas' | 'aplicadas' | 'descartadas'.
        Si ``show_duplicates`` es False, las descartadas se ocultan (salvo en su
        propio filtro). Los duplicados por uid ya no existen (uid es PK).
        """
        where = []
        if filtro == "no_vistas":
            where.append("seen = 0 AND discarded = 0")
        elif filtro == "aplicadas":
            where.append("applied = 1")
        elif filtro == "descartadas":
            where.append("discarded = 1")
        else:  # todas
            where.append("discarded = 0")
        sql = "SELECT * FROM jobs"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY detected_at DESC"
        return [dict(r) for r in self._query(sql)]

    # -- Evaluaciones (caché) -------------------------------------------------

    def get_evaluation(self, uid: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM evaluations WHERE uid = ?", (uid,))
        return dict(rows[0]) if rows else None

    def save_evaluation(self, uid: str, markdown: str, model: str) -> None:
        self._execute(
            "INSERT INTO evaluations (uid, markdown, model, created_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(uid) DO UPDATE SET markdown = excluded.markdown, "
            "model = excluded.model, created_at = excluded.created_at",
            (uid, markdown, model, _now_iso()),
        )

    # -- Cuotas (SerpAPI) -----------------------------------------------------

    def get_quota_count(self, period: str) -> int:
        rows = self._query("SELECT count FROM quotas WHERE period = ?", (period,))
        return rows[0]["count"] if rows else 0

    def increment_quota(self, period: str, amount: int = 1) -> int:
        self._execute(
            "INSERT INTO quotas (period, count) VALUES (?, ?) "
            "ON CONFLICT(period) DO UPDATE SET count = count + ?",
            (period, amount, amount),
        )
        return self.get_quota_count(period)

    # -- Runs (log de corridas) ----------------------------------------------

    def start_run(self, group_name: str, day_key: str) -> int:
        cur = self._execute(
            "INSERT INTO runs (group_name, started_at, status, day_key) "
            "VALUES (?, ?, 'running', ?)",
            (group_name, _now_iso(), day_key),
        )
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, status: str, message: str, found: int) -> None:
        self._execute(
            "UPDATE runs SET finished_at = ?, status = ?, message = ?, "
            "found_count = ? WHERE id = ?",
            (_now_iso(), status, message, found, run_id),
        )

    def group_b_ran_today(self, day_key: str) -> bool:
        return bool(self._query(
            "SELECT 1 FROM runs WHERE group_name = 'B' AND day_key = ? "
            "AND status != 'error'",
            (day_key,),
        ))

    def last_run(self, group_name: str) -> dict[str, Any] | None:
        rows = self._query(
            "SELECT * FROM runs WHERE group_name = ? ORDER BY id DESC LIMIT 1",
            (group_name,),
        )
        return dict(rows[0]) if rows else None
