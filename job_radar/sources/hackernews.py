"""Fuente Hacker News "Who is hiring?" vía la API de Algolia.

Estrategia:
1. Buscar el story más reciente cuyo título contenga "Who is hiring".
2. Tomar sus comentarios top-level (cada uno es, en la práctica, una vacante).
"""

from __future__ import annotations

from .base import Job, JobSource, clean_html

_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
_ITEM_URL = "https://hn.algolia.com/api/v1/items/{id}"


class HackerNewsSource(JobSource):
    name = "HackerNews"
    group = "A"
    #: Máximo de comentarios a procesar por corrida (el hilo puede tener cientos).
    MAX_COMMENTS = 120

    def fetch(self) -> list[Job]:
        with self._session() as s:
            # 1) Story más reciente de "Ask HN: Who is hiring?".
            r = s.get(
                _SEARCH_URL,
                params={
                    "query": "Ask HN: Who is hiring?",
                    "tags": "story,author_whoishiring",
                    "hitsPerPage": 1,
                },
                timeout=self.timeout,
            )
            r.raise_for_status()
            hits = r.json().get("hits", [])
            if not hits:
                return []
            story_id = hits[0].get("objectID")
            story_title = hits[0].get("title", "Who is hiring")

            # 2) Comentarios top-level del story.
            r2 = s.get(_ITEM_URL.format(id=story_id), timeout=self.timeout)
            r2.raise_for_status()
            children = r2.json().get("children", [])

        jobs: list[Job] = []
        for c in children[: self.MAX_COMMENTS]:
            text = clean_html(c.get("text"))
            author = c.get("author") or ""
            if not text or len(text) < 40:
                continue
            # La primera línea/segmento suele traer "Empresa | Puesto | ...".
            first = text.split(".")[0][:140]
            company = first.split("|")[0].strip()[:80] or author
            title = first if "|" not in first else " | ".join(
                p.strip() for p in first.split("|")[1:3]
            )
            jobs.append(Job(
                title=(title or first)[:160],
                company=company,
                source=self.name,
                url=f"https://news.ycombinator.com/item?id={c.get('id')}",
                location="",
                modality="",
                description=text,
                raw={"author": author, "story": story_title, "id": c.get("id")},
            ))
        return jobs
