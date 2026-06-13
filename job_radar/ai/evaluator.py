"""Evaluación profunda de una vacante (modelo capaz, bajo demanda, cacheada).

Genera Markdown enriquecido siguiendo EXACTAMENTE la plantilla pedida, inyectando
el contexto del usuario (perfil, tecnologías con niveles, inglés, salario objetivo).
"""

from __future__ import annotations

from typing import Any

from ..config import PERFIL_BASE
from .opencode_client import OpenCodeClient, clean_cli_output

#: Plantilla EXACTA que el modelo debe rellenar (renderizada como Markdown).
PLANTILLA = """\
# Evaluación de Vacante
## Resumen
- Puesto: / Empresa: / Industria: / Nivel estimado: / Modalidad: / Compatibilidad general (0-10): / Prioridad (Alta / Media / Baja):
## Empresa
- Descripción breve: / Tamaño aproximado: / Industria: / Ventajas: / Posibles desventajas:
## Modalidad
- Remoto: / Híbrido: / Presencial: / Compatible desde CDMX: / Horario: / Viajes requeridos: / Restricciones geográficas:
## Salario
- Salario publicado: / Salario estimado: / Bruto mensual MXN: / Neto mensual MXN: / Equivalente USD: / Comparación con objetivo salarial:
## Soft Skills Requeridas
- Obligatorias: / Deseables: / Nivel de exigencia:
## Hard Skills Obligatorias
### Frontend / ### Backend / ### Cloud-DevOps / ### Bases de Datos / ### Testing / ### Arquitectura / ### Otras
## Hard Skills Deseables
- Nice to have: / Plus:
## Match con Mi Perfil
### Fortalezas / ### Parcialmente cubiertas / ### Brechas
## Riesgos de Entrevista
- Temas probables: / Áreas débiles: / Nivel de riesgo:
## Tiempo para Ponerse al Día
- Tecnología: / Tiempo estimado:
## Probabilidad de Avanzar
- RH: / Técnica: / Cliente: / Oferta:
## Veredicto
- Aplicar: Sí / Sí con reservas / No
- Principales razones a favor: / Principales razones en contra:
## Alineación con Mis Objetivos
- Remoto: / Frontend: / React: / Angular: / UX/UI: / Inglés: / Pago en USD: / ≥ 25 USD/hr: / Balance vida/trabajo:
## Preparación Recomendada
- Temas a estudiar: / Tecnologías a repasar: / Preguntas que podrían hacer:
## Impacto Profesional
- Corto plazo: / Mediano plazo: / Largo plazo:
## Calificación Final
- Empresa: /10 — Salario: /10 — Modalidad: /10 — Tecnologías: /10 — Crecimiento: /10 — Compatibilidad: /10
### Score Total: X.X / 10
### Compatibilidad IA: X%
### Recomendación Final
Resumen breve y directo sobre si vale la pena invertir tiempo en el proceso.
"""

_PROMPT = """\
Eres un asesor de carrera experto y objetivo. Evalúa esta vacante para el \
usuario y RELLENA la plantilla Markdown de abajo, manteniendo EXACTAMENTE su \
estructura (mismos encabezados y campos), reemplazando cada campo con tu análisis.
Sé objetivo: señala brechas técnicas reales, NO infles la compatibilidad. \
Infiere información faltante cuando sea razonable y estima un rango salarial de \
mercado si la vacante no lo publica (incluye conversión MXN/USD aproximada). \
Responde SOLO con el Markdown rellenado, sin comentarios extra ni fences.

=== PERFIL DEL USUARIO ===
{perfil}
Nivel de inglés: {ingles}
Objetivo salarial: {salario}
Tecnologías y niveles (1-10):
{tecnologias}

=== VACANTE ===
Título: {title}
Empresa: {company}
Ubicación: {location}
Fuente: {source}
URL: {url}
Descripción completa:
{description}

=== PLANTILLA A RELLENAR ===
{plantilla}
"""


_FAST_PROMPT = """\
Eres un asesor tecnico de carrera. Evalua rapido esta vacante para decidir si
vale la pena invertir tiempo. Se objetivo, no infles el match y responde SOLO
Markdown.

Incluye exactamente estas secciones:
# Evaluacion rapida de Vacante
## Resumen
- Puesto:
- Empresa:
- Modalidad:
- Ubicacion:
- Compatibilidad general:
## Match con Mi Perfil
- Fortalezas:
- Brechas:
- Restricciones geograficas:
## Veredicto
- Aplicar: Si / Si con reservas / No
- Razones:
## Calificacion Final
### Score Total: X.X / 10
### Compatibilidad IA: X%
### Recomendacion Final

=== PERFIL DEL USUARIO ===
{perfil}
Nivel de ingles: {ingles}
Objetivo salarial: {salario}
Tecnologias y niveles:
{tecnologias}

=== VACANTE ===
Titulo: {title}
Empresa: {company}
Ubicacion: {location}
Fuente: {source}
URL: {url}
Descripcion:
{description}
"""


def _format_techs(techs: list[dict[str, Any]]) -> str:
    if not techs:
        return "(sin tecnologías declaradas)"
    return "\n".join(f"- {t['name']}: {t['level']}/10 ({t['origin']})" for t in techs)


def build_eval_prompt(
    job: dict[str, Any],
    *,
    profile_summary: str,
    technologies: list[dict[str, Any]],
    nivel_ingles: str,
    salario_objetivo: str,
) -> str:
    """Construye el prompt de evaluación profunda con todo el contexto."""
    perfil = (profile_summary or "").strip()
    perfil = f"{PERFIL_BASE}\n{perfil}" if perfil else PERFIL_BASE
    return _PROMPT.format(
        perfil=perfil,
        ingles=nivel_ingles or "B2",
        salario=salario_objetivo or "25 USD/hora",
        tecnologias=_format_techs(technologies),
        title=job.get("title", ""),
        company=job.get("company", ""),
        location=job.get("location", ""),
        source=job.get("source", ""),
        url=job.get("url", ""),
        description=(job.get("description", "") or "")[:3500],
        plantilla=PLANTILLA,
    )


def build_fast_eval_prompt(
    job: dict[str, Any],
    *,
    profile_summary: str,
    technologies: list[dict[str, Any]],
    nivel_ingles: str,
    salario_objetivo: str,
) -> str:
    """Construye un prompt compacto para evaluacion bajo demanda rapida."""
    perfil = (profile_summary or "").strip()
    perfil = f"{PERFIL_BASE}\n{perfil}" if perfil else PERFIL_BASE
    return _FAST_PROMPT.format(
        perfil=perfil,
        ingles=nivel_ingles or "B2",
        salario=salario_objetivo or "25 USD/hora",
        tecnologias=_format_techs(technologies),
        title=job.get("title", ""),
        company=job.get("company", ""),
        location=job.get("location", ""),
        source=job.get("source", ""),
        url=job.get("url", ""),
        description=(job.get("description", "") or "")[:1800],
    )


def evaluate_job(
    client: OpenCodeClient,
    job: dict[str, Any],
    *,
    profile_summary: str,
    technologies: list[dict[str, Any]],
    nivel_ingles: str,
    salario_objetivo: str,
    mode: str = "profunda",
    timeout: int = 180,
) -> str:
    """Genera la evaluación profunda en Markdown. Devuelve el texto listo para cachear."""
    if mode == "rapida":
        prompt = build_fast_eval_prompt(
            job,
            profile_summary=profile_summary,
            technologies=technologies,
            nivel_ingles=nivel_ingles,
            salario_objetivo=salario_objetivo,
        )
        raw = client.run_fast(prompt, timeout=timeout)
    else:
        prompt = build_eval_prompt(
            job,
            profile_summary=profile_summary,
            technologies=technologies,
            nivel_ingles=nivel_ingles,
            salario_objetivo=salario_objetivo,
        )
        raw = client.run_deep(prompt, timeout=timeout)
    markdown = clean_cli_output(raw)
    # Si el modelo envolvió en fences, quítalos conservando el contenido.
    if markdown.startswith("```"):
        markdown = markdown.strip("`")
        markdown = markdown.split("\n", 1)[-1] if "\n" in markdown else markdown
    return markdown.strip()
