"""Prueba real de las fuentes del Grupo A: descarga e imprime conteos.

Ejecutar:  python -m tests.test_sources_group_a
No usa mocks: golpea las APIs reales. Una fuente que falle no detiene a las demás.
"""

from __future__ import annotations

import sys

from job_radar.sources import GROUP_A_SOURCES


def main() -> int:
    total = 0
    fallos = 0
    for source_cls in GROUP_A_SOURCES:
        src = source_cls()
        try:
            jobs = src.fetch()
            total += len(jobs)
            ejemplo = jobs[0] if jobs else None
            print(f"[OK]   {src.name:16} -> {len(jobs):4} vacantes")
            if ejemplo:
                print(f"       ej: {ejemplo.title[:60]!r} @ {ejemplo.company[:30]!r}")
                print(f"           uid={ejemplo.uid[:12]}  url={ejemplo.url[:50]}")
        except Exception as exc:  # noqa: BLE001 — resiliencia: seguir con las demás
            fallos += 1
            print(f"[FALLA] {src.name:16} -> {type(exc).__name__}: {exc}")
    print(f"\nTotal vacantes: {total} | fuentes con fallo: {fallos}/{len(GROUP_A_SOURCES)}")
    # Éxito si al menos una fuente respondió con datos.
    return 0 if total > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
