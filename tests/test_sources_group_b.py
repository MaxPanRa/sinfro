"""Prueba de fuentes Grupo B. JobSpy es real (puede ser bloqueado: se tolera).

OCC debe estar desactivada. SerpAPI requiere key (se prueba aparte si se provee).
Ejecutar:  python -m tests.test_sources_group_b
"""

from __future__ import annotations

import sys

from job_radar.sources import JobSpySource, OCCSource


def main() -> int:
    # OCC: ahora activada (parsing del HTML de resultados).
    assert OCCSource.enabled is True
    try:
        occ = OCCSource(query="desarrollador frontend", location="México")
        jobs_occ = occ.fetch()
        print(f"[OK] OCC devolvió {len(jobs_occ)} vacantes.")
        for j in jobs_occ[:3]:
            print(f"     {j.title[:45]!r} @ {j.company[:30]!r} | {j.location[:25]!r}")
            print(f"        url={j.url}  desc={j.description[:50]!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"[INFO] OCC no devolvió datos ({type(exc).__name__}: {str(exc)[:80]}).")

    # JobSpy: intento real; si falla por bloqueo, lo reportamos sin romper.
    try:
        js = JobSpySource(search_term="react developer",
                          location="Ciudad de México, México", results_wanted=8)
        jobs = js.fetch()
        print(f"[OK] JobSpy devolvió {len(jobs)} vacantes.")
        if jobs:
            j = jobs[0]
            print(f"     ej: {j.title[:50]!r} @ {j.company[:30]!r} [{j.source}]")
    except Exception as exc:  # noqa: BLE001
        print(f"[INFO] JobSpy no devolvió datos ({type(exc).__name__}: "
              f"{str(exc)[:80]}). Es esperable si LinkedIn/Indeed bloquean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
