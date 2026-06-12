"""Fuente RemoteOK — JSON público en https://remoteok.com/api.

El primer elemento del arreglo es metadata legal y se descarta.
"""

from __future__ import annotations

from .base import Job, JobSource, clean_html


class RemoteOKSource(JobSource):
    name = "RemoteOK"
    group = "A"
    URL = "https://remoteok.com/api"

    def fetch(self) -> list[Job]:
        with self._session() as s:
            resp = s.get(self.URL, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

        jobs: list[Job] = []
        # El primer elemento es metadata legal (tiene clave "legal").
        for item in data:
            if not isinstance(item, dict) or "legal" in item:
                continue
            title = item.get("position") or item.get("title") or ""
            company = item.get("company") or ""
            if not title:
                continue
            tags = item.get("tags") or []
            desc = clean_html(item.get("description"))
            if tags:
                desc = f"Tags: {', '.join(tags)}. {desc}"
            jobs.append(Job(
                title=title,
                company=company,
                source=self.name,
                url=item.get("url") or item.get("apply_url") or "",
                location=item.get("location") or "Remoto",
                modality="Remoto",
                description=desc,
                raw=item,
            ))
        return jobs
