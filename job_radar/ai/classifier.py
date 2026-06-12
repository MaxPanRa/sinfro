"""Clasificación rápida de vacantes (modelo barato, corre sobre cada vacante).

Devuelve un dict normalizado:
    {match_score: 0-100, modalidad, acepta_cdmx, seniority, resumen_una_linea}
"""

from __future__ import annotations

from typing import Any

from .opencode_client import OpenCodeClient, OpenCodeError, parse_json_loose

_PROMPT = """\
Eres un clasificador de vacantes para un desarrollador Full Stack senior \
(Frontend: React/Angular/TypeScript/UX-UI, +10 años, busca remoto, pago en USD).
Analiza la vacante y responde ÚNICAMENTE con un objeto JSON válido, sin texto \
adicional, sin markdown, con EXACTAMENTE estas claves:
{{
  "match_score": <entero 0-100, qué tan compatible es con el perfil>,
  "modalidad": "<Remoto|Híbrido|Presencial|Desconocido>",
  "acepta_cdmx": <true|false, si alguien en Ciudad de México podría tomarla>,
  "seniority": "<Junior|Mid|Senior|Lead|Desconocido>",
  "resumen_una_linea": "<resumen en una sola línea, máx 120 caracteres>"
}}

VACANTE:
Título: {title}
Empresa: {company}
Ubicación: {location}
Descripción: {description}
"""


def _coerce(data: dict[str, Any]) -> dict[str, Any]:
    """Normaliza/valida el dict devuelto por el modelo."""
    try:
        score = int(float(data.get("match_score", 0)))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(100, score))

    acepta = data.get("acepta_cdmx")
    if isinstance(acepta, str):
        acepta = acepta.strip().lower() in {"true", "sí", "si", "yes", "1"}

    return {
        "match_score": score,
        "modalidad": str(data.get("modalidad", "Desconocido"))[:20] or "Desconocido",
        "acepta_cdmx": bool(acepta),
        "seniority": str(data.get("seniority", "Desconocido"))[:20] or "Desconocido",
        "resumen_una_linea": str(data.get("resumen_una_linea", ""))[:140],
    }


def classify_job(client: OpenCodeClient, job: dict[str, Any], timeout: int = 60) -> dict[str, Any]:
    """Clasifica una vacante. Lanza :class:`OpenCodeError` o ``ValueError`` si falla.

    ``job`` es el dict de una vacante (claves title/company/location/description).
    """
    prompt = _PROMPT.format(
        title=job.get("title", "")[:200],
        company=job.get("company", "")[:120],
        location=job.get("location", "")[:120],
        description=(job.get("description", "") or "")[:2500],
    )
    raw = client.run_fast(prompt, timeout=timeout)
    data = parse_json_loose(raw)
    return _coerce(data)
