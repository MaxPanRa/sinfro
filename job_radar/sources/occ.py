"""Fuente OCC Mundial — parsing del HTML server-rendered. Grupo B.

Descubrimiento (2026-06-12): aunque los endpoints /api/ responden 403 (anti-bot)
y la página NO embebe __NEXT_DATA__, la página de RESULTADOS sí renderiza las
vacantes en el HTML como tarjetas ``<div id="jobcard-<ID>">``. Se parsean con
BeautifulSoup. La URL de la vacante se construye desde el id:
``https://www.occ.com.mx/empleo/oferta/<ID>/`` (abre bien en navegador).

URL de búsqueda:
    https://www.occ.com.mx/empleos/de-<query-slug>/en-<location-slug>
"""

from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup

from .base import Job, JobSource

#: Ruidos a ignorar dentro de la tarjeta (estados/etiquetas, no datos de la vacante).
_RUIDO_RE = re.compile(
    r"^(Hace\b|Ayer|Hoy|Vista recientemente\.?|Nuevo\.?|Ya estás postulado\.?|"
    r"Sé de los primeros\.?|Postúlate)", re.IGNORECASE)
_SALARIO_RE = re.compile(r"\$|Sueldo", re.IGNORECASE)


def _slug(texto: str) -> str:
    """Convierte a slug OCC: minúsculas, sin acentos, espacios→guiones."""
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9\s-]", "", t).strip().lower()
    return re.sub(r"\s+", "-", t)


class OCCSource(JobSource):
    name = "OCCMundial"
    group = "B"
    enabled = True  # ← ACTIVADA: parsing del HTML de resultados (sin navegador)

    def __init__(
        self,
        query: str = "desarrollador frontend",
        location: str = "México",
        max_pages: int = 1,
        timeout: int = 30,
        proxies: dict[str, str] | None = None,
    ) -> None:
        super().__init__(timeout=timeout, proxies=proxies)
        self.query = query
        self.location = location
        self.max_pages = max_pages

    def _build_url(self, page: int) -> str:
        q = _slug(self.query) or "desarrollador"
        loc = _slug(self.location) or "mexico"
        base = f"https://www.occ.com.mx/empleos/de-{q}/en-{loc}"
        return f"{base}?page={page}" if page > 1 else base

    def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        with self._session() as s:
            # Headers extra para parecer navegador y evitar 403.
            s.headers.update({
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "es-MX,es;q=0.9",
                "Referer": "https://www.occ.com.mx/",
            })
            for page in range(1, self.max_pages + 1):
                resp = s.get(self._build_url(page), timeout=self.timeout)
                resp.raise_for_status()
                jobs.extend(self._parse(resp.text))
        return jobs

    def _parse(self, html: str) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        out: list[Job] = []
        for card in soup.select('[id^="jobcard"]'):
            job_id = card.get("id", "").replace("jobcard-", "").strip()
            if not job_id:
                continue

            # Título: el <h2> de la tarjeta.
            h2 = card.find("h2")
            title = h2.get_text(strip=True) if h2 else ""
            if not title:
                continue

            # Empresa: span.line-clamp-title o el enlace a bolsa-de-trabajo.
            comp_el = (card.select_one("span.line-clamp-title")
                       or card.find("a", href=re.compile("bolsa-de-trabajo")))
            company = comp_el.get_text(strip=True) if comp_el else ""

            # Recolecta strings limpias para salario/ubicación.
            strings = [t.strip() for t in card.stripped_strings if t.strip()]
            salario = next((t for t in strings if _SALARIO_RE.search(t)), "")
            # Ubicación: última string que no sea ruido/título/salario/empresa.
            ubicacion = ""
            for t in reversed(strings):
                if (t and t not in (title, company, salario)
                        and not _RUIDO_RE.match(t) and "," in t):
                    ubicacion = t
                    break

            modalidad = "Remoto" if re.search(r"remoto", title, re.I) else ""
            descripcion = " · ".join(filter(None, [salario, ubicacion]))
            out.append(Job(
                title=title,
                company=company,
                source=self.name,
                url=f"https://www.occ.com.mx/empleo/oferta/{job_id}/",
                location=ubicacion,
                modality=modalidad,
                description=descripcion or title,
                raw={"id": job_id, "salario": salario},
            ))
        return out
