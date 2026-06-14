"""Fuente We Work Remotely — RSS de programación remota.

El título del feed viene como "Empresa: Puesto"; se separa por el primer ':'.
"""

from __future__ import annotations

import feedparser

from .base import Job, JobSource, USER_AGENT, clean_html


class WeWorkRemotelySource(JobSource):
    name = "WeWorkRemotely"
    group = "A"
    # Feed general (todas las categorías), no solo programación.
    URL = "https://weworkremotely.com/remote-jobs.rss"

    def fetch(self) -> list[Job]:
        # feedparser acepta un User-Agent para evitar respuestas vacías.
        feed = feedparser.parse(self.URL, agent=USER_AGENT)
        jobs: list[Job] = []
        for entry in feed.entries:
            raw_title = entry.get("title", "")
            if ":" in raw_title:
                company, _, title = raw_title.partition(":")
                company, title = company.strip(), title.strip()
            else:
                company, title = "", raw_title.strip()
            if not title:
                continue
            region = entry.get("region", "") or "Remoto"
            jobs.append(Job(
                title=title,
                company=company,
                source=self.name,
                url=entry.get("link", ""),
                location=region,
                modality="Remoto",
                description=clean_html(entry.get("summary", "")),
                raw={k: entry.get(k) for k in ("title", "link", "published", "region")},
            ))
        return jobs
