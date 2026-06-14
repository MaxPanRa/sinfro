"""Acceso a SQLite: esquema, conexión segura entre hilos y operaciones CRUD.

Una sola instancia de :class:`Database` se comparte en toda la app. La conexión
usa ``check_same_thread=False`` + un ``RLock`` para permitir escrituras desde los
workers de ``QThreadPool`` sin corromper la base. Se activa WAL para concurrencia.

Soporta **múltiples perfiles**: cada perfil tiene su propio inbox (jobs),
keywords, skills (technologies), resumen de CV y evaluaciones cacheadas. Las
operaciones de esos datos se acotan al perfil activo (``active_profile_id``).
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


#: DDL del esquema NUEVO (con perfiles). Idempotente vía IF NOT EXISTS.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    summary    TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    profile_id          INTEGER NOT NULL DEFAULT 1,
    uid                 TEXT NOT NULL,             -- hash sha1 (título + empresa)
    title               TEXT NOT NULL,
    company             TEXT,
    source              TEXT NOT NULL,
    url                 TEXT,
    location            TEXT,
    modality            TEXT,
    description         TEXT,
    raw_json            TEXT,
    detected_at         TEXT NOT NULL,
    seen                INTEGER NOT NULL DEFAULT 0,
    visited_site        INTEGER NOT NULL DEFAULT 0,
    applied             INTEGER NOT NULL DEFAULT 0,
    applied_at          TEXT,
    discarded           INTEGER NOT NULL DEFAULT 0,
    quick_score         INTEGER,
    classification_json TEXT,
    PRIMARY KEY (profile_id, uid)
);

CREATE TABLE IF NOT EXISTS evaluations (
    profile_id INTEGER NOT NULL DEFAULT 1,
    uid        TEXT NOT NULL,
    markdown   TEXT NOT NULL,
    model      TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (profile_id, uid)
);

CREATE TABLE IF NOT EXISTS keywords (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL DEFAULT 1,
    word       TEXT NOT NULL,
    UNIQUE (profile_id, word)
);

CREATE TABLE IF NOT EXISTS technologies (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL DEFAULT 1,
    name       TEXT NOT NULL,
    level      INTEGER NOT NULL DEFAULT 5,
    origin     TEXT NOT NULL DEFAULT 'manual',     -- 'manual' | 'cv'
    UNIQUE (profile_id, name)
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS quotas (
    period TEXT PRIMARY KEY,
    count  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name  TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT,
    message     TEXT,
    found_count INTEGER DEFAULT 0,
    day_key     TEXT
);
"""


class Database:
    """Fachada de acceso a datos. Thread-safe vía lock global y con perfiles."""

    def __init__(self, path: Path | str = DB_PATH) -> None:
        self._path = str(path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._init_schema()

    # -- Infraestructura ------------------------------------------------------

    def _table_exists(self, name: str) -> bool:
        return bool(self._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone())

    def _columns(self, table: str) -> set[str]:
        return {r["name"] for r in self._conn.execute(f"PRAGMA table_info({table})")}

    def _init_schema(self) -> None:
        with self._lock:
            necesita_migracion = (
                self._table_exists("jobs") and "profile_id" not in self._columns("jobs")
            )
            resumen_antiguo = ""
            if necesita_migracion and self._table_exists("profile"):
                fila = self._conn.execute(
                    "SELECT summary FROM profile WHERE id = 1"
                ).fetchone()
                resumen_antiguo = fila["summary"] if fila else ""

            self._conn.executescript(_SCHEMA)

            # Perfil por defecto (id=1) si no hay ninguno.
            hay_perfiles = self._conn.execute(
                "SELECT 1 FROM profiles LIMIT 1"
            ).fetchone()
            if not hay_perfiles:
                self._conn.execute(
                    "INSERT INTO profiles (id, name, summary, created_at) "
                    "VALUES (1, 'Principal', ?, ?)",
                    (resumen_antiguo, _now_iso()),
                )

            if necesita_migracion:
                self._migrate_to_profiles()

            # Settings por defecto + perfil activo.
            for key, value in DEFAULT_SETTINGS.items():
                self._conn.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (key, value),
                )
            self._conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES "
                "('active_profile_id', '1')"
            )
            # Índice (tras la posible migración, cuando jobs ya tiene profile_id).
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_profile "
                "ON jobs(profile_id, detected_at)"
            )
            self._conn.commit()

    def _migrate_to_profiles(self) -> None:
        """Migra el esquema antiguo (sin perfiles) llevando todo al perfil 1."""
        self._conn.executescript(
            "ALTER TABLE jobs RENAME TO _jobs_old;"
            "ALTER TABLE keywords RENAME TO _kw_old;"
            "ALTER TABLE technologies RENAME TO _tech_old;"
            "ALTER TABLE evaluations RENAME TO _eval_old;"
        )
        self._conn.executescript(_SCHEMA)  # recrea las tablas con perfil
        cols_jobs = self._columns("_jobs_old")
        visited = "visited_site" if "visited_site" in cols_jobs else "0"
        self._conn.executescript(
            "INSERT INTO jobs (profile_id, uid, title, company, source, url, "
            " location, modality, description, raw_json, detected_at, seen, "
            " visited_site, applied, applied_at, discarded, quick_score, "
            " classification_json) "
            f"SELECT 1, uid, title, company, source, url, location, modality, "
            f" description, raw_json, detected_at, seen, {visited}, applied, "
            f" applied_at, discarded, quick_score, classification_json FROM _jobs_old;"
            "INSERT INTO keywords (profile_id, word) SELECT 1, word FROM _kw_old;"
            "INSERT INTO technologies (profile_id, name, level, origin) "
            " SELECT 1, name, level, origin FROM _tech_old;"
            "INSERT INTO evaluations (profile_id, uid, markdown, model, created_at) "
            " SELECT 1, uid, markdown, model, created_at FROM _eval_old;"
            "DROP TABLE _jobs_old; DROP TABLE _kw_old; DROP TABLE _tech_old;"
            " DROP TABLE _eval_old;"
        )

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

    # -- Perfiles -------------------------------------------------------------

    def active_profile_id(self) -> int:
        try:
            pid = int(self.get_setting("active_profile_id", "1"))
        except ValueError:
            pid = 1
        # Si el perfil activo ya no existe, cae al primero disponible.
        if not self._query("SELECT 1 FROM profiles WHERE id = ?", (pid,)):
            rows = self._query("SELECT id FROM profiles ORDER BY id LIMIT 1")
            pid = rows[0]["id"] if rows else 1
            self.set_setting("active_profile_id", str(pid))
        return pid

    def set_active_profile(self, pid: int) -> None:
        self.set_setting("active_profile_id", str(int(pid)))

    def list_profiles(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._query(
            "SELECT id, name FROM profiles ORDER BY id"
        )]

    def create_profile(self, name: str) -> int:
        name = (name or "Perfil").strip() or "Perfil"
        cur = self._execute(
            "INSERT INTO profiles (name, summary, created_at) VALUES (?, '', ?)",
            (name, _now_iso()),
        )
        return int(cur.lastrowid)

    def rename_profile(self, pid: int, name: str) -> None:
        self._execute("UPDATE profiles SET name = ? WHERE id = ?",
                      ((name or "").strip() or "Perfil", pid))

    def delete_profile(self, pid: int) -> None:
        """Elimina un perfil y todos sus datos. No permite quedarse sin perfiles."""
        if len(self.list_profiles()) <= 1:
            raise ValueError("Debe existir al menos un perfil.")
        with self._lock:
            for tabla in ("jobs", "evaluations", "keywords", "technologies"):
                self._conn.execute(f"DELETE FROM {tabla} WHERE profile_id = ?", (pid,))
            self._conn.execute("DELETE FROM profiles WHERE id = ?", (pid,))
            self._conn.commit()

    # -- Resumen del perfil (CV) ----------------------------------------------

    def get_profile_summary(self) -> str:
        rows = self._query(
            "SELECT summary FROM profiles WHERE id = ?", (self.active_profile_id(),))
        return rows[0]["summary"] if rows else ""

    def set_profile_summary(self, summary: str) -> None:
        self._execute("UPDATE profiles SET summary = ? WHERE id = ?",
                      (summary, self.active_profile_id()))

    # -- Keywords (por perfil) ------------------------------------------------

    def get_keywords(self) -> list[str]:
        return [r["word"] for r in self._query(
            "SELECT word FROM keywords WHERE profile_id = ? ORDER BY word",
            (self.active_profile_id(),))]

    def add_keyword(self, word: str) -> None:
        word = word.strip().lower()
        if word:
            self._execute(
                "INSERT OR IGNORE INTO keywords (profile_id, word) VALUES (?, ?)",
                (self.active_profile_id(), word))

    def remove_keyword(self, word: str) -> None:
        self._execute(
            "DELETE FROM keywords WHERE profile_id = ? AND word = ?",
            (self.active_profile_id(), word.strip().lower()))

    def seed_keywords_if_empty(self, words: list[str]) -> None:
        if not self.get_keywords():
            for w in words:
                self.add_keyword(w)

    # -- Skills / tecnologías (por perfil) ------------------------------------

    def get_technologies(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._query(
            "SELECT id, name, level, origin FROM technologies "
            "WHERE profile_id = ? ORDER BY name", (self.active_profile_id(),))]

    def upsert_technology(self, name: str, level: int, origin: str = "manual") -> None:
        """Inserta o actualiza una skill sin duplicar dentro del perfil activo.

        Si ya existe una manual, no la pisa una detectada del CV (respeta lo manual).
        """
        name = name.strip()
        if not name:
            return
        pid = self.active_profile_id()
        existing = self._query(
            "SELECT origin FROM technologies WHERE profile_id = ? AND lower(name) = lower(?)",
            (pid, name))
        if existing:
            if origin == "manual":
                self._execute(
                    "UPDATE technologies SET level = ?, origin = 'manual' "
                    "WHERE profile_id = ? AND lower(name) = lower(?)",
                    (level, pid, name))
            return
        self._execute(
            "INSERT INTO technologies (profile_id, name, level, origin) "
            "VALUES (?, ?, ?, ?)", (pid, name, level, origin))

    def update_technology_level(self, tech_id: int, level: int) -> None:
        self._execute("UPDATE technologies SET level = ? WHERE id = ?",
                      (max(1, min(10, int(level))), tech_id))

    def remove_technology(self, tech_id: int) -> None:
        self._execute("DELETE FROM technologies WHERE id = ?", (tech_id,))

    # -- Jobs (por perfil) ----------------------------------------------------

    def job_exists(self, uid: str) -> bool:
        return bool(self._query(
            "SELECT 1 FROM jobs WHERE profile_id = ? AND uid = ?",
            (self.active_profile_id(), uid)))

    def insert_job(self, job: dict[str, Any]) -> bool:
        """Inserta una vacante nueva en el perfil activo. False si ya existía."""
        pid = self.active_profile_id()
        if self.job_exists(job["uid"]):
            return False
        self._execute(
            "INSERT INTO jobs (profile_id, uid, title, company, source, url, "
            " location, modality, description, raw_json, detected_at, seen, "
            " applied, discarded) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)",
            (
                pid, job["uid"], job.get("title", ""), job.get("company", ""),
                job.get("source", ""), job.get("url", ""), job.get("location", ""),
                job.get("modality", ""), job.get("description", ""),
                json.dumps(job.get("raw", {}), ensure_ascii=False), _now_iso(),
            ),
        )
        return True

    def update_job_description(self, uid: str, description: str) -> None:
        self._execute(
            "UPDATE jobs SET description = ? WHERE profile_id = ? AND uid = ?",
            (description, self.active_profile_id(), uid))

    def set_quick_classification(self, uid: str, score: int, data: dict[str, Any]) -> None:
        self._execute(
            "UPDATE jobs SET quick_score = ?, classification_json = ? "
            "WHERE profile_id = ? AND uid = ?",
            (score, json.dumps(data, ensure_ascii=False), self.active_profile_id(), uid))

    def mark_seen(self, uid: str) -> None:
        self._execute("UPDATE jobs SET seen = 1 WHERE profile_id = ? AND uid = ?",
                      (self.active_profile_id(), uid))

    def mark_visited_site(self, uid: str) -> None:
        self._execute(
            "UPDATE jobs SET visited_site = 1 WHERE profile_id = ? AND uid = ?",
            (self.active_profile_id(), uid))

    def mark_applied(self, uid: str) -> None:
        self._execute(
            "UPDATE jobs SET applied = 1, applied_at = ? "
            "WHERE profile_id = ? AND uid = ? AND applied = 0",
            (_now_iso(), self.active_profile_id(), uid))

    def mark_discarded(self, uid: str) -> None:
        self._execute("UPDATE jobs SET discarded = 1 WHERE profile_id = ? AND uid = ?",
                      (self.active_profile_id(), uid))

    def clear_current_inbox(self) -> None:
        """Borra el inbox (jobs + evaluaciones) SOLO del perfil activo."""
        pid = self.active_profile_id()
        with self._lock:
            self._conn.execute("DELETE FROM evaluations WHERE profile_id = ?", (pid,))
            self._conn.execute("DELETE FROM jobs WHERE profile_id = ?", (pid,))
            self._conn.commit()

    def clear_all_inboxes(self) -> None:
        """Borra los inboxes de TODOS los perfiles (y el historial de corridas)."""
        with self._lock:
            self._conn.execute("DELETE FROM evaluations")
            self._conn.execute("DELETE FROM jobs")
            self._conn.execute("DELETE FROM runs")
            self._conn.commit()

    # Compat: el diálogo de Ajustes llamaba a este nombre → limpia el perfil actual.
    def clear_jobs_and_search_history(self) -> None:
        self.clear_current_inbox()

    def get_job(self, uid: str) -> dict[str, Any] | None:
        rows = self._query(
            "SELECT * FROM jobs WHERE profile_id = ? AND uid = ?",
            (self.active_profile_id(), uid))
        return dict(rows[0]) if rows else None

    def list_jobs(
        self,
        *,
        filtro: str = "todas",
        show_duplicates: bool = False,
    ) -> list[dict[str, Any]]:
        """Lista vacantes del perfil activo, ordenadas por detección desc.

        filtro: 'todas' | 'no_vistas' | 'aplicadas' | 'descartadas'.
        En 'todas' las descartadas SÍ se muestran (la bandeja las colorea de rojo).
        """
        where = ["profile_id = ?"]
        params: list[Any] = [self.active_profile_id()]
        if filtro == "no_vistas":
            where.append("seen = 0 AND discarded = 0")
        elif filtro == "aplicadas":
            where.append("applied = 1")
        elif filtro == "descartadas":
            where.append("discarded = 1")
        sql = "SELECT * FROM jobs WHERE " + " AND ".join(where) + " ORDER BY detected_at DESC"
        return [dict(r) for r in self._query(sql, params)]

    # -- Evaluaciones (caché, por perfil) -------------------------------------

    def get_evaluation(self, uid: str) -> dict[str, Any] | None:
        rows = self._query(
            "SELECT * FROM evaluations WHERE profile_id = ? AND uid = ?",
            (self.active_profile_id(), uid))
        return dict(rows[0]) if rows else None

    def save_evaluation(self, uid: str, markdown: str, model: str) -> None:
        self._execute(
            "INSERT INTO evaluations (profile_id, uid, markdown, model, created_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(profile_id, uid) DO UPDATE SET markdown = excluded.markdown, "
            "model = excluded.model, created_at = excluded.created_at",
            (self.active_profile_id(), uid, markdown, model, _now_iso()))

    # -- Cuotas ---------------------------------------------------------------

    def get_quota_count(self, period: str) -> int:
        rows = self._query("SELECT count FROM quotas WHERE period = ?", (period,))
        return rows[0]["count"] if rows else 0

    def increment_quota(self, period: str, amount: int = 1) -> int:
        self._execute(
            "INSERT INTO quotas (period, count) VALUES (?, ?) "
            "ON CONFLICT(period) DO UPDATE SET count = count + ?",
            (period, amount, amount))
        return self.get_quota_count(period)

    # -- Runs -----------------------------------------------------------------

    def start_run(self, group_name: str, day_key: str) -> int:
        cur = self._execute(
            "INSERT INTO runs (group_name, started_at, status, day_key) "
            "VALUES (?, ?, 'running', ?)", (group_name, _now_iso(), day_key))
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, status: str, message: str, found: int) -> None:
        self._execute(
            "UPDATE runs SET finished_at = ?, status = ?, message = ?, "
            "found_count = ? WHERE id = ?",
            (_now_iso(), status, message, found, run_id))

    def group_b_ran_today(self, day_key: str) -> bool:
        return bool(self._query(
            "SELECT 1 FROM runs WHERE group_name = 'B' AND day_key = ? "
            "AND status != 'error'", (day_key,)))

    def last_run(self, group_name: str) -> dict[str, Any] | None:
        rows = self._query(
            "SELECT * FROM runs WHERE group_name = ? ORDER BY id DESC LIMIT 1",
            (group_name,))
        return dict(rows[0]) if rows else None
