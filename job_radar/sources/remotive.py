"""Fuente Remotive — JSON en https://remotive.com/api/remote-jobs."""

from __future__ import annotations

from .base import Job, JobSource, clean_html


class RemotiveSource(JobSource):
    name = "Remotive"
    group = "A"
    # Todas las categorías (no solo software): el filtro por keywords decide.
    URL = "https://remotive.com/api/remote-jobs?limit=100"

    def fetch(self) -> list[Job]:
        with self._session() as s:
            resp = s.get(self.URL, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

        jobs: list[Job] = []
        for item in data.get("jobs", []):
            title = item.get("title") or ""
            company = item.get("company_name") or ""
            if not title:
                continue
            jobs.append(Job(
                title=title,
                company=company,
                source=self.name,
                url=item.get("url") or "",
                location=item.get("candidate_required_location") or "Remoto",
                modality="Remoto",
                description=clean_html(item.get("description")),
                raw=item,
            ))
        return jobs
