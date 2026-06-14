"""Fuente Adzuna — agregador con cobertura de México y TODAS las profesiones.

API gratuita previo registro (app_id + app_key) en https://developer.adzuna.com.
Endpoint: https://api.adzuna.com/v1/api/jobs/{country}/search/{page}
Cubre abogacía, administración, finanzas, salud, etc., incluyendo empleos LOCALES
(no solo remotos). Grupo B (usa key).
"""

from __future__ import annotations

from .base import Job, JobSource, clean_html


class AdzunaSource(JobSource):
    name = "Adzuna"
    group = "B"
    URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

    def __init__(
        self,
        app_id: str,
        app_key: str,
        query: str = "",
        location: str = "",
        country: str = "mx",
        results: int = 50,
        timeout: int = 30,
        proxies: dict[str, str] | None = None,
    ) -> None:
        super().__init__(timeout=timeout, proxies=proxies)
        self.app_id = app_id
        self.app_key = app_key
        self.query = query
        self.location = location
        self.country = country or "mx"
        self.results = results

    def fetch(self) -> list[Job]:
        if not self.app_id or not self.app_key:
            raise RuntimeError("Faltan app_id/app_key de Adzuna (configúralos en Ajustes).")

        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": self.results,
            "content-type": "application/json",
        }
        if self.query:
            params["what"] = self.query
        if self.location and self.location.lower() not in ("méxico", "mexico"):
            params["where"] = self.location

        url = self.URL.format(country=self.country, page=1)
        with self._session() as s:
            resp = s.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

        jobs: list[Job] = []
        for item in data.get("results", []):
            title = item.get("title") or ""
            company = (item.get("company") or {}).get("display_name", "")
            if not title:
                continue
            location = (item.get("location") or {}).get("display_name", "")
            desc = clean_html(item.get("description"))
            salary = ""
            if item.get("salary_min"):
                salary = f"Salario aprox: {int(item['salary_min'])}-{int(item.get('salary_max', item['salary_min']))}"
                desc = f"{desc}\n{salary}".strip()
            modality = "Remoto" if "remot" in f"{title} {desc}".lower() else ""
            jobs.append(Job(
                title=clean_html(title),
                company=company,
                source=self.name,
                url=item.get("redirect_url") or "",
                location=location,
                modality=modality,
                description=desc,
                raw={
                    "id": item.get("id"),
                    "created": item.get("created"),
                    "category": (item.get("category") or {}).get("label"),
                    "salary": salary,
                },
            ))
        return jobs
