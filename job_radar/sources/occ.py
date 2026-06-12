"""Fuente OCC Mundial — STUB DESACTIVADO (requiere navegador).

Investigación (2026-06-12):
- El sitio https://www.occ.com.mx/empleos/de-<query>/ responde 200 pero renderiza
  las vacantes del lado del cliente (no hay __NEXT_DATA__ ni __next_f con datos).
- El único bloque ld+json es metadata del sitio, NO contiene JobPosting.
- Los endpoints internos /api/... responden 403 (protección anti-bot tipo
  Akamai/Cloudflare), incluso con User-Agent realista.

Conclusión: no es viable sin un navegador headless (Selenium/Playwright), que está
fuera del stack permitido. Queda DESACTIVADA. Para habilitarla en el futuro:
1. Añadir Playwright como dependencia opcional.
2. Cargar la página, esperar el render y leer el DOM o interceptar la respuesta
   XHR real de búsqueda (capturar el endpoint + headers/cookies necesarios).
3. Implementar ``fetch`` parseando esos resultados a objetos :class:`Job`.
"""

from __future__ import annotations

from .base import Job, JobSource


class OCCSource(JobSource):
    name = "OCCMundial"
    group = "B"
    enabled = False  # ← desactivada: requiere navegador headless

    def fetch(self) -> list[Job]:
        # No-op documentado: el scheduler salta las fuentes con enabled=False.
        raise RuntimeError(
            "OCC Mundial requiere navegador headless (ver docstring). Fuente desactivada."
        )
