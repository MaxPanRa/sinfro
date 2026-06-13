"""Renderizador del Markdown de evaluación a HTML embellecido para QTextBrowser.

Convierte la plantilla de evaluación en HTML moderno dentro de las limitaciones
del rich text de Qt: secciones con emoji, porcentajes coloreados, dinero en
negritas verdes, y palomita/tache (✅/❌/⚠️) en objetivos, fortalezas y brechas.
"""

from __future__ import annotations

import html as _html
import re

# Emoji por sección (## ...). La clave se compara en minúsculas y sin acentos suaves.
_SECTION_EMOJI = {
    "resumen": "📋", "empresa": "🏢", "modalidad": "🏠", "salario": "💰",
    "soft skills requeridas": "🤝", "hard skills obligatorias": "🛠️",
    "hard skills deseables": "✨", "match con mi perfil": "🎯",
    "riesgos de entrevista": "⚠️", "tiempo para ponerse al día": "⏱️",
    "tiempo para ponerse al dia": "⏱️", "probabilidad de avanzar": "📈",
    "veredicto": "⚖️", "alineación con mis objetivos": "🧭",
    "alineacion con mis objetivos": "🧭", "preparación recomendada": "📚",
    "preparacion recomendada": "📚", "impacto profesional": "🚀",
    "calificación final": "🏆", "calificacion final": "🏆",
}

_MONEY_RE = re.compile(
    r"(\$\s?[\d][\d.,]*\s?(?:USD|MXN|EUR|mil|k)?\b(?:\s?(?:mensual|al mes|/mes|/hr|por hora|brutos?|netos?))?)",
    re.IGNORECASE)
_PCT_RE = re.compile(r"\b(\d{1,3})\s*%")
_SCORE10_RE = re.compile(r"\b(\d{1,2}(?:\.\d)?)\s*/\s*10\b")


def _esc(text: str) -> str:
    return _html.escape(text, quote=False)


def _pct_color(val: int) -> str:
    if val >= 70:
        return "#16a34a"
    if val >= 50:
        return "#f59e0b"
    if val >= 30:
        return "#f97316"
    return "#dc2626"


def _emphasize(text: str) -> str:
    """Colorea porcentajes y resalta dinero en un texto ya escapado."""
    def _pct(m: re.Match) -> str:
        val = int(m.group(1))
        return (f'<span style="color:{_pct_color(val)};font-weight:bold">'
                f'{m.group(0)}</span>')

    def _money(m: re.Match) -> str:
        return f'<b style="color:#15803d">{m.group(0)}</b>'

    text = _MONEY_RE.sub(_money, text)
    text = _PCT_RE.sub(_pct, text)
    return text


def _value_emoji(value: str) -> str:
    """Devuelve ✅/❌/⚠️ según el valor (Sí/No/Parcial) o '' si no aplica."""
    v = value.strip().lower()
    if v.startswith(("sí con reservas", "si con reservas", "parcial")):
        return "⚠️ "
    if v.startswith(("sí", "si", "cumple", "compatible")) and "no " not in v[:4]:
        return "✅ "
    if v.startswith(("no", "ninguno", "ninguna")):
        return "❌ "
    return ""


def _render_field(part: str, sub: str) -> str:
    """Renderiza un fragmento 'label: value' (o texto suelto) como <li>."""
    part = part.strip()
    if not part:
        return ""
    prefix = ""
    # Emoji por subsección (fortalezas/brechas/parcialmente).
    if "fortaleza" in sub:
        prefix = "✅ "
    elif "brecha" in sub:
        prefix = "❌ "
    elif "parcial" in sub:
        prefix = "⚠️ "

    if ":" in part:
        label, _, value = part.partition(":")
        value = value.strip()
        emoji = prefix or _value_emoji(value)
        val_html = _emphasize(_esc(value)) if value else "<i style='color:#9aa5b1'>—</i>"
        return (f'<li style="margin:2px 0;">{emoji}'
                f'<b style="color:#334155">{_esc(label.strip())}:</b> {val_html}</li>')
    return f'<li style="margin:2px 0;">{prefix}{_emphasize(_esc(part))}</li>'


def render_eval_html(markdown: str) -> str:
    """Convierte el Markdown de evaluación en HTML embellecido."""
    bloques: list[str] = []
    sub = ""
    li_buffer: list[str] = []

    def flush() -> None:
        if li_buffer:
            bloques.append(
                '<ul style="margin:2px 0 8px 0;-qt-list-indent:1;">'
                + "".join(li_buffer) + "</ul>")
            li_buffer.clear()

    for raw in markdown.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue

        if line.startswith("# ") and not line.startswith("## "):
            flush()
            bloques.append(
                f'<div style="font-size:17px;font-weight:bold;color:#0f172a;'
                f'margin:0 0 4px 0;">{_esc(line[2:].strip())}</div>')
            continue

        if line.startswith("## "):
            flush()
            sub = ""
            sec = line[3:].strip()
            emoji = _SECTION_EMOJI.get(sec.lower(), "🔹")
            bloques.append(
                f'<div style="font-size:13px;font-weight:bold;color:#1d4ed8;'
                f'margin:12px 0 2px 0;padding-bottom:3px;'
                f'border-bottom:2px solid #dbe4f0;">{emoji}&nbsp;{_esc(sec)}</div>')
            continue

        if line.startswith("### "):
            flush()
            sub = line[4:].strip().lower()
            titulo = line[4:].strip()
            # Casos especiales: Score Total y Compatibilidad IA → badge grande.
            m_score = _SCORE10_RE.search(titulo)
            m_pct = _PCT_RE.search(titulo)
            if "score total" in sub and m_score:
                val = float(m_score.group(1))
                color = _pct_color(int(val * 10))
                bloques.append(
                    f'<div style="margin:6px 0;font-size:14px;">🏆 '
                    f'<b>Score Total:</b> <span style="color:{color};'
                    f'font-size:18px;font-weight:bold;">{m_score.group(1)}</span>'
                    f'<span style="color:#94a3b8;"> / 10</span></div>')
                continue
            if "compatibilidad ia" in sub and m_pct:
                val = int(m_pct.group(1))
                color = _pct_color(val)
                bloques.append(
                    f'<div style="margin:4px 0;font-size:13px;">🎯 '
                    f'<b>Compatibilidad IA:</b> '
                    f'<span style="background:{color};color:white;padding:1px 8px;'
                    f'font-weight:bold;">{val}%</span></div>')
                continue
            icono = ("✅ " if "fortaleza" in sub else "❌ " if "brecha" in sub
                     else "⚠️ " if "parcial" in sub else "")
            bloques.append(
                f'<div style="font-weight:bold;color:#475569;margin:8px 0 2px 0;">'
                f'{icono}{_esc(titulo)}</div>')
            continue

        if line.startswith("- "):
            contenido = line[2:].strip()
            # Separa campos empacados con " / " en items independientes.
            partes = re.split(r"\s/\s", contenido) if " / " in contenido else [contenido]
            for parte in partes:
                li = _render_field(parte, sub)
                if li:
                    li_buffer.append(li)
            continue

        # Párrafo suelto (p. ej. recomendación final).
        flush()
        bloques.append(
            f'<p style="margin:4px 0;color:#334155;">{_emphasize(_esc(line))}</p>')

    flush()
    cuerpo = "\n".join(bloques)
    return (
        '<div style="font-family:\'Segoe UI\';font-size:12px;'
        f'line-height:140%;color:#1f2933;">{cuerpo}</div>')


def render_job_html(job: dict) -> str:
    """HTML para la pestaña 'Vacante original'."""
    title = _esc(str(job.get("title", "")))
    company = _esc(str(job.get("company", "")))
    source = _esc(str(job.get("source", "")))
    location = _esc(str(job.get("location", "")))
    modality = _esc(str(job.get("modality", "")))
    url = str(job.get("url", ""))
    desc = _esc(str(job.get("description", "")) or "(sin descripción)")
    desc = desc.replace("\n", "<br>")

    meta_items = " · ".join(filter(None, [company, source, modality, location]))
    link = (f'<p style="margin:6px 0;"><a href="{_html.escape(url, quote=True)}" '
            f'style="color:#2563eb;">{_html.escape(url, quote=True)}</a></p>'
            if url else "")
    return (
        f'<div style="font-family:\'Segoe UI\';font-size:12px;color:#1f2933;">'
        f'<div style="font-size:16px;font-weight:bold;color:#0f172a;">{title}</div>'
        f'<div style="color:#64748b;margin:3px 0 6px 0;">{meta_items}</div>'
        f'{link}'
        f'<hr style="border:none;border-top:1px solid #e2e8f0;">'
        f'<div style="margin-top:6px;color:#334155;line-height:145%;">{desc}</div>'
        f'</div>')
