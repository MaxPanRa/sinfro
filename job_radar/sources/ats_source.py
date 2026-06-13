"""Fuentes ATS publicas por empresa: Lever, Greenhouse, Workable y Ashby."""

from __future__ import annotations

import re
from typing import Any

from .base import Job, JobSource, clean_html


def company_slug(text: str) -> str:
    """Normaliza una empresa para endpoints ATS que usan slugs."""
    slug = (text or "").strip().lower()
    slug = re.sub(r"https?://", "", slug)
    slug = slug.split("/")[0] if "/" in slug else slug
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug


class ATSCompanySource(JobSource):
    name = "ATS"
    group = "B"

    def __init__(
        self,
        company: str,
        timeout: int = 25,
        proxies: dict[str, str] | None = None,
    ) -> None:
        super().__init__(timeout=timeout, proxies=proxies)
        self.company = company
        self.slug = company_slug(company)

    def fetch(self) -> list[Job]:
        if not self.slug:
            raise RuntimeError("Ingresa el nombre/slug de empresa.")

        jobs: list[Job] = []
        jobs.extend(self._lever())
        jobs.extend(self._greenhouse())
        jobs.extend(self._workable())
        jobs.extend(self._ashby())
        return jobs

    def _get_json(self, url: str, **params: Any) -> Any | None:
        try:
            with self._session() as s:
                resp = s.get(url, params=params or None, timeout=self.timeout)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
        except Exception:
            return None

    def _lever(self) -> list[Job]:
        data = self._get_json(
            f"https://api.lever.co/v0/postings/{self.slug}",
            mode="json",
        )
        if not isinstance(data, list):
            return []
        jobs: list[Job] = []
        for item in data:
            title = item.get("text") or ""
            if not title:
                continue
            categories = item.get("categories") or {}
            location = categories.get("location") or ""
            commitment = categories.get("commitment") or ""
            salary = item.get("salaryRange") or {}
            salary_text = ""
            if isinstance(salary, dict) and salary:
                salary_text = f"Salario: {salary.get('min', '')}-{salary.get('max', '')} {salary.get('currency', '')}"
            description = "\n".join(filter(None, [
                clean_html(item.get("descriptionPlain") or item.get("description")),
                salary_text,
            ]))
            modality = "Remoto" if "remot" in f"{title} {location} {description}".lower() else ""
            jobs.append(Job(
                title=title,
                company=self.company,
                source="Lever",
                url=item.get("hostedUrl") or item.get("applyUrl") or "",
                location=location,
                modality=modality,
                description=description,
                raw={"team": categories.get("team"), "commitment": commitment},
            ))
        return jobs

    def _greenhouse(self) -> list[Job]:
        data = self._get_json(
            f"https://api.greenhouse.io/v1/boards/{self.slug}/jobs",
            content="true",
        )
        rows = data.get("jobs", []) if isinstance(data, dict) else []
        jobs: list[Job] = []
        for item in rows:
            title = item.get("title") or ""
            if not title:
                continue
            offices = item.get("offices") or []
            location = ", ".join(o.get("name", "") for o in offices if o.get("name"))
            description = clean_html(item.get("content"))
            modality = "Remoto" if "remot" in f"{title} {location} {description}".lower() else ""
            jobs.append(Job(
                title=title,
                company=self.company,
                source="Greenhouse",
                url=item.get("absolute_url") or "",
                location=location,
                modality=modality,
                description=description,
                raw={"id": item.get("id"), "updated_at": item.get("updated_at")},
            ))
        return jobs

    def _workable(self) -> list[Job]:
        data = self._get_json(
            f"https://apply.workable.com/api/v1/widget/accounts/{self.slug}",
        )
        rows = data.get("jobs", []) if isinstance(data, dict) else []
        jobs: list[Job] = []
        for item in rows:
            title = item.get("title") or ""
            if not title:
                continue
            location_obj = item.get("location") or {}
            location = location_obj.get("location_str") if isinstance(location_obj, dict) else ""
            description = clean_html(item.get("description") or item.get("shortcode"))
            modality = "Remoto" if item.get("remote") or "remot" in f"{title} {location} {description}".lower() else ""
            code = item.get("shortcode") or item.get("id") or ""
            url = item.get("url") or (f"https://apply.workable.com/{self.slug}/j/{code}/" if code else "")
            jobs.append(Job(
                title=title,
                company=self.company,
                source="Workable",
                url=url,
                location=location or item.get("city") or "",
                modality=modality,
                description=description,
                raw={"code": code, "department": item.get("department")},
            ))
        return jobs

    def _ashby(self) -> list[Job]:
        data = self._get_json(
            f"https://api.ashbyhq.com/posting-api/job-board/{self.slug}",
            includeCompensation="true",
        )
        rows = data.get("jobs", []) if isinstance(data, dict) else []
        jobs: list[Job] = []
        for item in rows:
            title = item.get("title") or ""
            if not title:
                continue
            location = item.get("location") or ""
            description = clean_html(item.get("descriptionPlain") or item.get("descriptionHtml"))
            compensation = item.get("compensation") or {}
            if isinstance(compensation, dict) and compensation:
                description = "\n".join(filter(None, [description, clean_html(compensation.get("compensationTierSummary"))]))
            modality = "Remoto" if "remot" in f"{title} {location} {description}".lower() else ""
            jobs.append(Job(
                title=title,
                company=self.company,
                source="Ashby",
                url=item.get("jobUrl") or item.get("applyUrl") or "",
                location=location,
                modality=modality,
                description=description,
                raw={"id": item.get("id"), "department": item.get("department")},
            ))
        return jobs
