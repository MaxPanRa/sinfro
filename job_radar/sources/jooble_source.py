"""Fuente Jooble REST API para Mexico. Grupo B."""

from __future__ import annotations

from .base import Job, JobSource, clean_html


class JoobleSource(JobSource):
    name = "Jooble MX"
    group = "B"
    #: IMPORTANTE: la API key de Jooble está atada al subdominio del PAÍS.
    #: Para México es ``mx.jooble.org`` — usar ``jooble.org`` devuelve 403.
    URL = "https://{host}/api/{api_key}"

    def __init__(
        self,
        api_key: str,
        keywords: str = "frontend remote",
        location: str = "Mexico",
        *,
        host: str = "mx.jooble.org",
        companysearch: bool = False,
        page: int = 1,
        result_on_page: int = 25,
        timeout: int = 30,
        proxies: dict[str, str] | None = None,
    ) -> None:
        super().__init__(timeout=timeout, proxies=proxies)
        self.api_key = api_key
        self.keywords = keywords
        self.location = location
        self.host = host
        self.companysearch = companysearch
        self.page = page
        self.result_on_page = result_on_page

    def fetch(self) -> list[Job]:
        if not self.api_key:
            raise RuntimeError("Falta la API key de Jooble (configurala en Ajustes).")

        payload = {
            "keywords": self.keywords,
            "location": self.location,
            "radius": "80",
            "page": str(self.page),
            "ResultOnPage": str(self.result_on_page),
            "companysearch": "true" if self.companysearch else "false",
        }
        with self._session() as s:
            resp = s.post(
                self.URL.format(host=self.host, api_key=self.api_key),
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

        jobs: list[Job] = []
        for item in data.get("jobs", []):
            title = item.get("title") or ""
            company = item.get("company") or item.get("source") or "Jooble"
            if not title:
                continue
            description = clean_html(item.get("snippet") or item.get("description"))
            salary = item.get("salary") or ""
            if salary:
                description = f"{description}\nSalario: {salary}".strip()
            modality = "Remoto" if "remot" in f"{title} {description}".lower() else ""
            jobs.append(Job(
                title=title,
                company=company,
                source=self.name,
                url=item.get("link") or "",
                location=item.get("location") or self.location,
                modality=modality,
                description=description,
                raw={
                    "id": item.get("id"),
                    "type": item.get("type"),
                    "salary": salary,
                    "updated": item.get("updated"),
                    "source": item.get("source"),
                },
            ))
        return jobs
