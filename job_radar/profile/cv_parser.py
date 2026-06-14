"""Extracción de texto del CV (PDF/DOCX) y análisis con IA.

- ``extract_cv_text``: usa pdfplumber/pypdf para PDF y python-docx para DOCX.
- ``analyze_cv``: pide a OpenCode un JSON con tecnologías detectadas (nombre +
  nivel sugerido 1-10) y un resumen del perfil del usuario.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..ai.opencode_client import OpenCodeClient, parse_json_loose


def extract_cv_text(path: str | Path) -> str:
    """Extrae texto plano de un CV en PDF o DOCX. Lanza ValueError si no soporta."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _extract_pdf(path)
    if ext in (".docx", ".doc"):
        return _extract_docx(path)
    raise ValueError(f"Formato no soportado: {ext} (usa PDF o DOCX)")


def _extract_pdf(path: Path) -> str:
    # Primero pdfplumber (mejor layout); si falla, pypdf.
    try:
        import pdfplumber

        partes: list[str] = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                partes.append(page.extract_text() or "")
        texto = "\n".join(partes).strip()
        if texto:
            return texto
    except Exception:  # noqa: BLE001 — caemos a pypdf
        pass

    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join((p.extract_text() or "") for p in reader.pages).strip()


def _extract_docx(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs).strip()


_PROMPT = """\
Eres un analista de currículums para CUALQUIER profesión (no solo tecnología).
A partir del texto del CV de abajo, responde ÚNICAMENTE con un objeto JSON válido \
(sin markdown, sin texto extra) con esta forma:
{{
  "resumen": "<resumen profesional del candidato en 3-5 frases, en español>",
  "keywords": ["<10 frases clave de búsqueda de empleo acordes al perfil>"],
  "skills": [
    {{"name": "<skill>", "level": <entero 1-10 según dominio aparente>}}
  ]
}}
Las skills pueden ser de CUALQUIER tipo: técnicas, administrativas, legales, \
soft skills, liderazgo, idiomas, herramientas, etc. — lo que aplique al perfil.
Las keywords son **frases clave de búsqueda** para encontrar vacantes (la búsqueda \
es semántica, así que pueden ser de 1 a 4 palabras; ej. para un abogado: \
"abogado corporativo", "litigio mercantil", "derecho laboral"; para un dev: \
"desarrollador frontend", "react senior"). Devuelve EXACTAMENTE 10, variadas.
Estima el nivel por años/uso/seniority. Máximo 30 skills.

=== CV ===
{texto}
"""


def analyze_cv(client: OpenCodeClient, texto_cv: str, timeout: int = 150) -> dict[str, Any]:
    """Analiza el CV con IA. Devuelve ``{"resumen", "keywords": [...10], "skills": [...]}``.

    Normaliza/valida la salida. Lanza OpenCodeError/ValueError si falla.
    """
    prompt = _PROMPT.format(texto=texto_cv[:12000])
    raw = client.run_deep(prompt, timeout=timeout)
    data = parse_json_loose(raw)

    resumen = str(data.get("resumen", "")).strip()

    keywords: list[str] = []
    for kw in data.get("keywords", [])[:10]:
        kw = str(kw).strip()
        if kw:
            keywords.append(kw[:60])

    # Acepta "skills" (nuevo) o "tecnologias" (compatibilidad).
    raw_skills = data.get("skills") or data.get("tecnologias") or []
    skills_norm: list[dict[str, Any]] = []
    for t in raw_skills:
        if not isinstance(t, dict):
            continue
        name = str(t.get("name", "")).strip()
        if not name:
            continue
        try:
            level = int(float(t.get("level", 5)))
        except (TypeError, ValueError):
            level = 5
        skills_norm.append({"name": name[:60], "level": max(1, min(10, level))})
    # "tecnologias" se mantiene como alias para el código que ya lo usa.
    return {"resumen": resumen, "keywords": keywords,
            "skills": skills_norm, "tecnologias": skills_norm}
