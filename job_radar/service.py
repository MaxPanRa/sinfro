"""Servicio de aplicación: orquesta DB, fuentes e IA. Sin dependencias de Qt.

Los workers de la UI (QRunnable) llaman a estos métodos en hilos de fondo.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .ai.classifier import classify_job
from .ai.evaluator import evaluate_job
from .ai.opencode_client import OpenCodeClient
from .config import (
    OPENCODE_TIMEOUT_DEEP, OPENCODE_TIMEOUT_FAST, PERFIL_BASE,
)
from .db.database import Database
from .sources.base import Job


class AppService:
    """Fachada de lógica de negocio compartida por la UI y el scheduler."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # -- Cliente IA construido desde settings ---------------------------------

    def build_client(self) -> OpenCodeClient:
        s = self.db.get_all_settings()
        return OpenCodeClient(
            api_key=s.get("opencode_api_key", ""),
            fast_model=s.get("fast_model") or "opencode-go/deepseek-v4-flash",
            deep_model=s.get("deep_model") or "opencode-go/kimi-k2.6",
            free_model=s.get("free_model") or "opencode/deepseek-v4-flash-free",
            use_free_fallback=s.get("use_free_fallback", "0") == "1",
        )

    def proxies(self) -> dict[str, str] | None:
        """Devuelve dict de proxies si el toggle VPS está activo, si no None."""
        s = self.db.get_all_settings()
        if s.get("proxy_enabled") == "1" and s.get("proxy_host"):
            host = s["proxy_host"]
            return {"http": f"http://{host}", "https": f"http://{host}"}
        return None

    def salario_objetivo_str(self) -> str:
        s = self.db.get_all_settings()
        return f"{s.get('salario_monto','25')} {s.get('salario_moneda','USD')}/{s.get('salario_periodo','hora')}"

    # -- Pre-filtro por keywords ----------------------------------------------

    @staticmethod
    def keyword_match(job: Job, keywords: list[str]) -> bool:
        """True si el título o descripción contiene alguna keyword (case-insensitive).

        Sin keywords configuradas, deja pasar todo.
        """
        if not keywords:
            return True
        blob = f"{job.title} {job.description}".lower()
        return any(kw.lower() in blob for kw in keywords)

    # -- Ingesta --------------------------------------------------------------

    def ingest_jobs(self, jobs: list[Job]) -> list[str]:
        """Inserta vacantes nuevas que pasen el pre-filtro. Devuelve uids nuevos.

        La deduplicación por uid (título+empresa) la maneja la DB.
        """
        keywords = self.db.get_keywords()
        nuevos: list[str] = []
        for job in jobs:
            if not self.keyword_match(job, keywords):
                continue
            if self.db.insert_job(job.to_dict()):
                nuevos.append(job.uid)
        return nuevos

    # -- Clasificación rápida -------------------------------------------------

    def classify_uid(self, client: OpenCodeClient, uid: str) -> dict[str, Any] | None:
        """Clasifica una vacante por uid y persiste el resultado."""
        job = self.db.get_job(uid)
        if not job:
            return None
        data = classify_job(client, job, timeout=OPENCODE_TIMEOUT_FAST)
        self.db.set_quick_classification(uid, data["match_score"], data)
        return data

    def pending_classification(self) -> list[str]:
        """uids de vacantes sin score (no clasificadas todavía)."""
        rows = self.db.list_jobs(filtro="todas")
        return [r["uid"] for r in rows if r.get("quick_score") is None]

    # -- Evaluación profunda (cacheada) ---------------------------------------

    def get_or_create_evaluation(
        self, client: OpenCodeClient, uid: str, *, force: bool = False
    ) -> str:
        """Devuelve la evaluación cacheada o la genera si no existe / se fuerza."""
        if not force:
            cached = self.db.get_evaluation(uid)
            if cached:
                return cached["markdown"]
        job = self.db.get_job(uid)
        if not job:
            raise ValueError("Vacante no encontrada")
        s = self.db.get_all_settings()
        markdown = evaluate_job(
            client, job,
            profile_summary=self.db.get_profile_summary(),
            technologies=self.db.get_technologies(),
            nivel_ingles=s.get("nivel_ingles", "B2"),
            salario_objetivo=self.salario_objetivo_str(),
            timeout=OPENCODE_TIMEOUT_DEEP,
        )
        self.db.save_evaluation(uid, markdown, client.deep_model)
        return markdown

    # -- Grupo B: query, ubicación y cuota SerpAPI ----------------------------

    def build_group_b_query(self) -> str:
        """Construye el término de búsqueda a partir de las keywords (máx 4)."""
        kws = self.db.get_keywords()[:4]
        return " ".join(kws) if kws else "desarrollador"

    def group_b_location(self) -> str:
        """Ubicación legible para JobSpy/SerpAPI según la selección del usuario."""
        ub = self.db.get_setting("ubicacion", "")
        if not ub or ub == "Toda la República":
            return "México"
        if ub == "Solo remoto internacional":
            return "Remote"
        return f"{ub}, México"

    def serpapi_period(self) -> str:
        return "serpapi:" + datetime.now().strftime("%Y-%m")

    def serpapi_remaining(self) -> int:
        from .config import SERPAPI_MONTHLY_QUOTA
        usadas = self.db.get_quota_count(self.serpapi_period())
        return max(0, SERPAPI_MONTHLY_QUOTA - usadas)

    # -- Utilidades de estado -------------------------------------------------

    def today_key(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")
