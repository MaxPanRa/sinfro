"""Interfaz común de fuentes de vacantes y el modelo de datos ``Job``.

Toda fuente hereda de :class:`JobSource` e implementa ``fetch()`` devolviendo una
lista de :class:`Job`. Los errores se capturan arriba (el scheduler): una fuente
que falla no debe tumbar a las demás.
"""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import requests

#: User-Agent realista para evitar bloqueos triviales.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def make_uid(title: str, company: str) -> str:
    """UID determinista (sha1) a partir de título + empresa, normalizados.

    Se usa para deduplicar: dos vacantes con mismo título+empresa colapsan.
    """
    base = f"{(title or '').strip().lower()}|{(company or '').strip().lower()}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def clean_html(text: str | None, limit: int = 6000) -> str:
    """Quita etiquetas HTML y normaliza espacios; recorta a ``limit`` chars."""
    if not text:
        return ""
    text = _HTML_TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text[:limit]


@dataclass
class Job:
    """Una vacante normalizada lista para persistir."""

    title: str
    company: str
    source: str
    url: str = ""
    location: str = ""
    modality: str = ""
    description: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def uid(self) -> str:
        return make_uid(self.title, self.company)

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "title": self.title,
            "company": self.company,
            "source": self.source,
            "url": self.url,
            "location": self.location,
            "modality": self.modality,
            "description": self.description,
            "raw": self.raw,
        }


class JobSource(ABC):
    """Contrato de una fuente de vacantes."""

    #: Nombre legible (se guarda en la columna ``source``).
    name: str = "base"
    #: Grupo de scheduling: 'A' alta frecuencia, 'B' ventanas horarias.
    group: str = "A"
    #: Si está deshabilitada (stub), el scheduler la salta.
    enabled: bool = True

    def __init__(self, timeout: int = 25, proxies: dict[str, str] | None = None) -> None:
        self.timeout = timeout
        self.proxies = proxies  # capa lista para proxy VPS (desactivado por defecto)

    def _session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        if self.proxies:
            s.proxies.update(self.proxies)
        return s

    @abstractmethod
    def fetch(self) -> list[Job]:
        """Descarga y normaliza vacantes. Puede lanzar excepción (la maneja el caller)."""
        raise NotImplementedError
