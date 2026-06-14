"""Fuente Jobicy — API pública y gratuita de empleos remotos. Grupo A.

Sin API key. Cubre cualquier profesión (marketing, ventas, soporte, escritura,
diseño, etc.), no solo tecnología. https://jobicy.com/api/v2/remote-jobs
"""

from __future__ import annotations

from .base import Job, JobSource, clean_html


class JobicySource(JobSource):
    name = "Jobicy"
    group = "A"
    URL = "https://jobicy.com/api/v2/remote-jobs"

    def __init__(self, count: int = 50, timeout: int = 25,
                 proxies: dict[str, str] | None = None) -> None:
        super().__init__(timeout=timeout, proxies=proxies)
        self.count = count

    def fetch(self) -> list[Job]:
        with self._session() as s:
            resp = s.get(self.URL, params={"count": self.count}, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

        jobs: list[Job] = []
        for item in data.get("jobs", []):
            title = item.get("jobTitle") or ""
            company = item.get("companyName") or ""
            if not title:
                continue
            desc = clean_html(item.get("jobDescription") or item.get("jobExcerpt"))
            geo = item.get("jobGeo") or "Remoto"
            jobs.append(Job(
                title=title,
                company=company,
                source=self.name,
                url=item.get("url") or "",
                location=geo,
                modality="Remoto",
                description=desc,
                raw={
                    "id": item.get("id"),
                    "pubDate": item.get("pubDate"),
                    "jobIndustry": item.get("jobIndustry"),
                    "jobLevel": item.get("jobLevel"),
                },
            ))
        return jobs
