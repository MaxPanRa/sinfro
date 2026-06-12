"""Fuente JobSpy — LinkedIn (modo invitado) e Indeed. Grupo B.

Pocas páginas por corrida, manejo de errores silencioso. El parámetro de proxy
está listo pero desactivado por defecto (se activará apuntando a un VPS).
"""

from __future__ import annotations

from .base import Job, JobSource, clean_html


class JobSpySource(JobSource):
    name = "JobSpy"
    group = "B"

    def __init__(
        self,
        search_term: str = "desarrollador",
        location: str = "Ciudad de México, México",
        results_wanted: int = 20,
        timeout: int = 60,
        proxies: dict[str, str] | None = None,
    ) -> None:
        super().__init__(timeout=timeout, proxies=proxies)
        self.search_term = search_term
        self.location = location
        self.results_wanted = results_wanted

    def fetch(self) -> list[Job]:
        # Import diferido: jobspy es pesado y opcional.
        try:
            from jobspy import scrape_jobs
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"python-jobspy no disponible: {exc}") from exc

        # JobSpy acepta una lista de proxies "host:port" (capa lista para VPS).
        proxies_list = None
        if self.proxies:
            host = self.proxies.get("http", "").replace("http://", "")
            if host:
                proxies_list = [host]

        df = scrape_jobs(
            site_name=["linkedin", "indeed"],
            search_term=self.search_term,
            location=self.location,
            results_wanted=self.results_wanted,   # pocas por corrida
            hours_old=72,
            country_indeed="mexico",
            linkedin_fetch_description=False,      # más rápido y menos bloqueos
            proxies=proxies_list,
            verbose=0,
        )

        jobs: list[Job] = []
        if df is None or len(df) == 0:
            return jobs
        for rec in df.to_dict("records"):
            title = str(rec.get("title") or "").strip()
            company = str(rec.get("company") or "").strip()
            if not title:
                continue
            modalidad = "Remoto" if rec.get("is_remote") else ""
            jobs.append(Job(
                title=title,
                company=company,
                source=f"{self.name}/{rec.get('site', '')}",
                url=str(rec.get("job_url") or ""),
                location=str(rec.get("location") or ""),
                modality=modalidad,
                description=clean_html(str(rec.get("description") or "")),
                raw={k: str(rec.get(k)) for k in ("site", "job_type", "date_posted")},
            ))
        return jobs
