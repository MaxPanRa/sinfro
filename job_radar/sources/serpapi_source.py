"""Fuente Google for Jobs vía SerpAPI (engine google_jobs). Grupo B.

La cuota gratuita (~100 búsquedas/mes) la controla el caller (service/scheduler)
mediante la tabla ``quotas``: esta clase solo realiza la llamada. La API key se
ingresa en Ajustes.
"""

from __future__ import annotations

from .base import Job, JobSource, clean_html


class SerpApiSource(JobSource):
    name = "SerpAPI"
    group = "B"
    URL = "https://serpapi.com/search.json"

    def __init__(
        self,
        api_key: str,
        query: str = "desarrollador frontend",
        location: str = "Mexico",
        timeout: int = 30,
        proxies: dict[str, str] | None = None,
    ) -> None:
        super().__init__(timeout=timeout, proxies=proxies)
        self.api_key = api_key
        self.query = query
        self.location = location

    def fetch(self) -> list[Job]:
        if not self.api_key:
            raise RuntimeError("Falta la API key de SerpAPI (configúrala en Ajustes).")

        params = {
            "engine": "google_jobs",
            "q": self.query,
            "location": self.location,
            "hl": "es",
            "gl": "mx",
            "api_key": self.api_key,
        }
        with self._session() as s:
            resp = s.get(self.URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

        if "error" in data:
            raise RuntimeError(f"SerpAPI: {data['error']}")

        jobs: list[Job] = []
        for item in data.get("jobs_results", []):
            title = item.get("title") or ""
            company = item.get("company_name") or ""
            if not title:
                continue
            ext = item.get("detected_extensions", {}) or {}
            modalidad = "Remoto" if ext.get("work_from_home") else ""
            # Primer enlace de aplicación disponible.
            url = ""
            apply_opts = item.get("apply_options") or []
            if apply_opts:
                url = apply_opts[0].get("link", "")
            jobs.append(Job(
                title=title,
                company=company,
                source=self.name,
                url=url or item.get("share_link", ""),
                location=item.get("location") or self.location,
                modality=modalidad,
                description=clean_html(item.get("description")),
                raw={"via": item.get("via"), "schedule": ext.get("schedule_type")},
            ))
        return jobs
