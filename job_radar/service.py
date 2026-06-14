"""Servicio de aplicacion: orquesta DB, fuentes e IA. Sin dependencias de Qt."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any

from .ai.evaluator import evaluate_job
from .ai.opencode_client import OpenCodeClient
from .config import (
    JOOBLE_MONTHLY_QUOTA,
    OPENCODE_TIMEOUT_DEEP,
    OPENCODE_TIMEOUT_FAST,
    SERPAPI_MONTHLY_QUOTA,
)
from .db.database import Database
from .sources.base import Job

#: Palabras vacías que se ignoran al dividir keywords/skills en tokens.
_STOPWORDS = {
    "de", "del", "la", "el", "los", "las", "y", "o", "u", "en", "con", "para",
    "por", "un", "una", "al", "a", "the", "of", "and", "or", "to", "in", "for",
    "with",
}

#: Sinónimos para reforzar el match de términos tech comunes (clave normalizada).
_ALIASES = {
    "frontend": ["frontend", "front end", "front-end", "ui engineer"],
    "fullstack": ["fullstack", "full stack", "full-stack"],
    "typescript": ["typescript", "type script"],
    "javascript": ["javascript"],
    "react": ["react", "react.js", "reactjs", "next.js", "nextjs"],
    "angular": ["angular"],
    "ux/ui": ["ux/ui", "ux ui", "ui design", "product design"],
    "spring": ["spring", "spring boot"],
    "node": ["node", "node.js", "nodejs"],
}


class AppService:
    """Fachada de logica de negocio compartida por la UI y el scheduler."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # -- Cliente IA construido desde settings ---------------------------------

    def build_client(self) -> OpenCodeClient:
        s = self.db.get_all_settings()
        return OpenCodeClient(
            api_key=s.get("opencode_api_key", ""),
            fast_model=s.get("fast_model") or "opencode-go/deepseek-v4-flash",
            deep_model=s.get("deep_model") or "opencode-go/kimi-k2.6",
            free_model=s.get("free_model") or "opencode/deepseek-v4-flash-free",
            use_free_fallback=s.get("use_free_fallback", "0") == "1",
        )

    def proxies(self) -> dict[str, str] | None:
        s = self.db.get_all_settings()
        if s.get("proxy_enabled") == "1" and s.get("proxy_host"):
            host = s["proxy_host"]
            return {"http": f"http://{host}", "https": f"http://{host}"}
        return None

    def salario_objetivo_str(self) -> str:
        s = self.db.get_all_settings()
        return (
            f"{s.get('salario_monto','25')} "
            f"{s.get('salario_moneda','USD')}/{s.get('salario_periodo','hora')}"
        )

    # -- Prefiltros -----------------------------------------------------------

    @staticmethod
    def keyword_match(job: Job, keywords: list[str]) -> bool:
        if not keywords:
            return True
        blob = f"{job.title} {job.description}".lower()
        return any(kw.lower() in blob for kw in keywords)

    @staticmethod
    def _norm(text: str) -> str:
        text = unicodedata.normalize("NFKD", text or "")
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        return text.lower()

    def location_match(self, job: Job | dict[str, Any]) -> bool:
        """Acepta vacantes compatibles con Mexico/estado o remoto global/LatAm."""
        selected = self.db.get_setting("ubicacion", "")
        selected_norm = self._norm(selected)
        if isinstance(job, dict):
            title = str(job.get("title", ""))
            location = str(job.get("location", ""))
            modality = str(job.get("modality", ""))
            description = str(job.get("description", ""))
        else:
            title = job.title
            location = job.location
            modality = job.modality
            description = job.description

        blob = self._norm(" ".join([title, location, modality, description]))
        mexico_terms = (
            "mexico", "mexico city", "ciudad de mexico", "cdmx",
            "republica mexicana",
        )
        global_remote_terms = (
            "worldwide", "anywhere", "global", "latin america", "latam",
            "america latina", "americas", "north america", "remote - global",
        )
        foreign_only_re = re.compile(
            r"\b("
            r"us only|usa only|u\.s\. only|united states only|"
            r"united states|estados unidos|usa|u\.s\.|us|"
            r"canada|uk|united kingdom|"
            r"europe|emea|australia|new zealand|singapore|india|"
            r"germany|france|spain|espana|netherlands|poland|portugal|"
            r"new york|nyc|san francisco|bay area|seattle|austin|"
            r"california|texas|boston|chicago|los angeles"
            r")\b"
        )

        matches_mexico = (
            any(term in blob for term in mexico_terms)
            or re.search(r"\bmx\b", blob) is not None
        )
        matches_state = (
            selected_norm
            and selected_norm not in {"toda la republica", "solo remoto internacional"}
            and selected_norm in blob
        )
        matches_global_remote = any(term in blob for term in global_remote_terms)

        if matches_state or matches_mexico or matches_global_remote:
            return True
        if foreign_only_re.search(blob):
            return False
        return selected_norm == "solo remoto internacional" and "remot" in blob

    def semantic_preclassification(self, job: Job | dict[str, Any]) -> dict[str, Any]:
        if isinstance(job, dict):
            title = str(job.get("title", ""))
            company = str(job.get("company", ""))
            location = str(job.get("location", ""))
            modality = str(job.get("modality", ""))
            description = str(job.get("description", ""))
        else:
            title = job.title
            company = job.company
            location = job.location
            modality = job.modality
            description = job.description

        blob = self._norm(" ".join([title, company, location, modality, description]))
        reasons: list[str] = []
        penalties: list[str] = []

        foreign_only = re.search(
            r"\b(us only|usa only|u\.s\. only|united states only|"
            r"united states|usa|u\.s\.|canada only|uk only|europe only)\b",
            blob,
        ) is not None
        if foreign_only and not self.location_match(job):
            return {
                "match_score": 0,
                "source": "semantic_prelim",
                "compatible": False,
                "discard_reason": "Restriccion geografica extranjera",
                "resumen_una_linea": "Descartada por restriccion geografica (US/foreign only).",
            }

        # --- Palabras clave = FUENTE PRINCIPAL (se dividen en tokens + frase) ---
        kw_points = 0
        kw_matched: list[str] = []
        for kw in self.db.get_keywords():
            fuerza = self._match_strength(kw, blob, _ALIASES.get(self._norm(kw)))
            if fuerza == 3:
                kw_points += 14
                kw_matched.append(kw)
            elif fuerza == 2:
                kw_points += 10
                kw_matched.append(kw)
            elif fuerza == 1:
                kw_points += 4
        kw_points = min(55, kw_points)
        if kw_matched:
            reasons.append("keywords: " + ", ".join(kw_matched[:5]))

        # --- Skills = pesan fuerte en el %, ponderadas por nivel ---
        skill_points = 0.0
        skill_matched: list[str] = []
        for t in self.db.get_technologies():
            fuerza = self._match_strength(
                t["name"], blob, _ALIASES.get(self._norm(t["name"])))
            if fuerza >= 2:
                skill_points += 2.5 + float(t.get("level", 5)) * 0.6
                skill_matched.append(t["name"])
            elif fuerza == 1:
                skill_points += 1.0
        skill_points = min(35.0, skill_points)
        if skill_matched:
            reasons.append("skills: " + ", ".join(skill_matched[:5]))

        location_ok = self.location_match(job)
        location_score = 12 if location_ok else 0
        if location_ok:
            reasons.append("ubicacion compatible")

        modalities = {
            self._norm(m).strip()
            for m in (self.db.get_setting("modalidades", "") or "").split(",")
            if m.strip()
        }
        remoteish = any(t in blob for t in ["remoto", "remote", "work from home", "wfh"])
        hybridish = any(t in blob for t in ["hibrido", "hybrid"])
        onsiteish = any(t in blob for t in ["presencial", "onsite", "on-site"])
        if not modalities:
            modality_score = 6
        elif "remoto" in modalities and remoteish:
            modality_score = 8
            reasons.append("remoto")
        elif "hibrido" in modalities and hybridish:
            modality_score = 6
            reasons.append("hibrido")
        elif "presencial" in modalities and onsiteish:
            modality_score = 5
        else:
            modality_score = 0
            penalties.append("modalidad no ideal")

        seniority_score = 0
        if any(t in blob for t in ["senior", "sr.", "lead", "staff", "principal"]):
            seniority_score = 4
        elif any(t in blob for t in ["junior", "intern", "trainee", "becario"]):
            seniority_score = -6
            penalties.append("seniority bajo")

        if any(t in blob for t in ["visa", "security clearance", "clearance required"]):
            penalties.append("posible requisito legal/visa")

        relevancia = kw_points + skill_points
        score = relevancia + location_score + modality_score + seniority_score
        # Las palabras clave MANDAN: sin un match sólido de keyword → fuera de tema.
        if not kw_matched:
            score = min(score, 18)
            penalties.append("sin coincidencia de palabras clave")
        score = max(0, min(100, int(round(score))))
        threshold = self.compatibility_threshold()
        compatible = score >= threshold

        resumen = f"COMP PRELIM {score}%"
        if reasons:
            resumen += " - " + "; ".join(reasons[:3])
        if penalties:
            resumen += " | Revisar: " + ", ".join(penalties[:2])

        return {
            "match_score": score,
            "source": "semantic_prelim",
            "compatible": compatible,
            "threshold": threshold,
            "modalidad": "Remoto" if remoteish else ("Hibrido" if hybridish else ""),
            "acepta_cdmx": location_ok,
            "seniority": "Senior/Lead" if seniority_score > 0 else "Revisar",
            "matched_skills": skill_matched,
            "reasons": reasons,
            "penalties": penalties,
            "resumen_una_linea": resumen[:180],
        }

    @staticmethod
    def _term_in_blob(term: str, blob: str) -> bool:
        term = term.strip()
        if not term:
            return False
        if len(term) <= 3:
            return re.search(rf"\b{re.escape(term)}\b", blob) is not None
        return term in blob

    def _tokens(self, texto: str) -> list[str]:
        """Divide una frase en palabras útiles (sin stopwords ni tokens cortos)."""
        return [t for t in re.split(r"[\s/,_.\-]+", self._norm(texto))
                if len(t) > 2 and t not in _STOPWORDS]

    def _match_strength(self, phrase: str, blob: str,
                        aliases: list[str] | None = None) -> int:
        """Fuerza del match de una frase contra el blob.

        3 = frase/alias exacto; 2 = todos sus tokens; 1 = algún token; 0 = nada.
        Así "abogado litigante" matchea "abogado", "litigante" y la frase completa.
        """
        p = self._norm(phrase).strip()
        if not p:
            return 0
        for cand in [p, *(aliases or [])]:
            if self._term_in_blob(self._norm(cand), blob):
                return 3
        toks = self._tokens(phrase)
        if not toks:
            return 0
        hits = sum(1 for t in toks if self._term_in_blob(t, blob))
        if hits >= len(toks):
            return 2
        return 1 if hits > 0 else 0

    def compatibility_threshold(self) -> int:
        try:
            return int(self.db.get_setting("match_threshold", "70") or 70)
        except ValueError:
            return 70

    # -- Ingesta --------------------------------------------------------------

    def ingest_jobs(self, jobs: list[Job]) -> list[str]:
        nuevos: list[str] = []
        for job in jobs:
            prelim = self.semantic_preclassification(job)
            if prelim.get("discard_reason"):
                continue
            # Con el gate de keywords, lo fuera de tema queda en <=18 y no entra;
            # bajamos el umbral para capturar más empleos realmente on-topic.
            if int(prelim.get("match_score", 0)) < 28:
                continue
            if self.db.insert_job(job.to_dict()):
                self.db.set_quick_classification(
                    job.uid, int(prelim["match_score"]), prelim
                )
                nuevos.append(job.uid)
        return nuevos

    # -- Clasificacion rapida -------------------------------------------------

    def classify_uid(self, client: OpenCodeClient, uid: str) -> dict[str, Any] | None:
        job = self.db.get_job(uid)
        if not job:
            return None
        data = self.semantic_preclassification(job)
        self.db.set_quick_classification(uid, int(data["match_score"]), data)
        return data

    def pending_classification(self) -> list[str]:
        rows = self.db.list_jobs(filtro="todas")
        return [r["uid"] for r in rows if r.get("quick_score") is None]

    # -- Evaluacion profunda --------------------------------------------------

    def get_or_create_evaluation(
        self, client: OpenCodeClient, uid: str, *, force: bool = False,
        mode: str | None = None,
    ) -> str:
        if not force:
            cached = self.db.get_evaluation(uid)
            if cached:
                self._update_ai_score_from_markdown(uid, cached["markdown"])
                return cached["markdown"]
        job = self.db.get_job(uid)
        if not job:
            raise ValueError("Vacante no encontrada")
        s = self.db.get_all_settings()
        # ``mode`` explícito (ej. "Análisis Profundo") tiene prioridad sobre Ajustes.
        mode = mode or s.get("evaluation_mode", "rapida")
        if mode not in {"rapida", "profunda"}:
            mode = "rapida"
        timeout = OPENCODE_TIMEOUT_FAST if mode == "rapida" else OPENCODE_TIMEOUT_DEEP
        markdown = evaluate_job(
            client, job,
            profile_summary=self.db.get_profile_summary(),
            technologies=self.db.get_technologies(),
            nivel_ingles=s.get("nivel_ingles", "B2"),
            salario_objetivo=self.salario_objetivo_str(),
            mode=mode,
            timeout=timeout,
        )
        model = client.fast_model if mode == "rapida" else client.deep_model
        self.db.save_evaluation(uid, markdown, model)
        self._update_ai_score_from_markdown(uid, markdown, source=f"ai_{mode}")
        return markdown

    def current_eval_mode(self, uid: str) -> str | None:
        """Modo del análisis cacheado: 'rapida' | 'profunda' | None (sin análisis).

        Se detecta por el título del Markdown (la evaluación rápida usa
        'Evaluacion rapida de Vacante').
        """
        ev = self.db.get_evaluation(uid)
        if not ev:
            return None
        md = self._norm(ev.get("markdown", ""))
        if "evaluacion rapida" in md:
            return "rapida"
        return "profunda"

    def _update_ai_score_from_markdown(
        self, uid: str, markdown: str, *, source: str = "ai_final"
    ) -> None:
        score = self._extract_ai_score(markdown)
        if score is None:
            return
        data = {
            "match_score": score,
            "source": source,
            "compatible": score >= self.compatibility_threshold(),
            "threshold": self.compatibility_threshold(),
            "resumen_una_linea": f"COMP IA {score}% - calculada al abrir la vacante.",
        }
        self.db.set_quick_classification(uid, score, data)

    @staticmethod
    def _extract_ai_score(markdown: str) -> int | None:
        patterns = [
            r"Score Total:\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*10",
            r"Compatibilidad general.*?([0-9]+(?:\.[0-9]+)?)\s*/\s*10",
            r"Compatibilidad.*?([0-9]{1,3})\s*%",
        ]
        for pattern in patterns:
            match = re.search(pattern, markdown, flags=re.IGNORECASE | re.DOTALL)
            if not match:
                continue
            value = float(match.group(1))
            if value <= 10:
                value *= 10
            return max(0, min(100, int(round(value))))
        return None

    # -- Grupo B: query, ubicacion y cuota SerpAPI ----------------------------

    def build_group_b_query(self) -> str:
        kws = self.db.get_keywords()[:4]
        return " ".join(kws) if kws else "desarrollador"

    def build_serpapi_query(self) -> str:
        kws = [self._norm(k).strip() for k in self.db.get_keywords() if k.strip()]
        preferred = (
            "frontend", "fullstack", "react", "angular", "typescript",
            "java", "ux/ui",
        )
        base = next((kw for kw in preferred if kw in kws), None)
        base = base or (kws[0] if kws else "frontend")
        query = "Frontend" if base == "frontend" else base
        modalidades = {
            self._norm(m).strip()
            for m in (self.db.get_setting("modalidades", "") or "").split(",")
            if m.strip()
        }
        if "remoto" in modalidades and "remote" not in self._norm(query):
            query = f"{query} remote"
        return query

    def build_jooble_query(self) -> str:
        return self.build_serpapi_query()

    def group_b_location(self) -> str:
        ub = self.db.get_setting("ubicacion", "")
        if not ub or ub == "Toda la República":
            return "México"
        if ub == "Solo remoto internacional":
            return "Remote"
        return f"{ub}, México"

    def serpapi_location(self) -> str:
        raw = self.db.get_setting("ubicacion", "")
        ub = self._norm(raw)
        if not ub or ub == "toda la republica":
            return "Mexico City, Mexico City, Mexico"
        if ub == "solo remoto internacional":
            return "Mexico"
        if ub in {"ciudad de mexico", "cdmx"} or ("ciudad" in ub and "xico" in ub):
            return "Mexico City, Mexico City, Mexico"
        return f"{raw}, Mexico"

    def serpapi_period(self) -> str:
        return "serpapi:" + datetime.now().strftime("%Y-%m")

    def serpapi_remaining(self) -> int:
        usadas = self.db.get_quota_count(self.serpapi_period())
        return max(0, SERPAPI_MONTHLY_QUOTA - usadas)

    def jooble_period(self) -> str:
        return "jooble:" + datetime.now().strftime("%Y-%m")

    def jooble_remaining(self) -> int:
        usadas = self.db.get_quota_count(self.jooble_period())
        return max(0, JOOBLE_MONTHLY_QUOTA - usadas)

    # -- Utilidades de estado -------------------------------------------------

    def today_key(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")
