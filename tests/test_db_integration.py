"""Prueba de integración DB: inserta vacantes de una fuente real, valida dedup.

Usa una DB temporal para no tocar la real. Ejecutar:
    python -m tests.test_db_integration
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from job_radar.db.database import Database
from job_radar.sources import RemotiveSource


def main() -> int:
    tmp = Path(tempfile.mkdtemp()) / "test.db"
    db = Database(tmp)

    # Settings y seed por defecto deben existir.
    assert db.get_setting("fast_model") == "opencode-go/deepseek-v4-flash"
    db.seed_keywords_if_empty(["react", "angular"])
    assert set(db.get_keywords()) == {"react", "angular"}

    # Tecnologías: no duplica, respeta manual sobre cv.
    db.upsert_technology("React", 8, "manual")
    db.upsert_technology("react", 5, "cv")  # no debe pisar la manual
    techs = db.get_technologies()
    react = next(t for t in techs if t["name"].lower() == "react")
    assert react["level"] == 8 and react["origin"] == "manual", react

    # Inserción real desde Remotive.
    jobs = RemotiveSource().fetch()
    nuevos = sum(1 for j in jobs if db.insert_job(j.to_dict()))
    repetidos = sum(1 for j in jobs if not db.insert_job(j.to_dict()))  # 2a vez = dups
    print(f"Remotive: {len(jobs)} traídas, {nuevos} insertadas, {repetidos} dups en reinserción")
    assert nuevos > 0
    assert repetidos == nuevos  # la 2a pasada son todos duplicados

    # Estados.
    if jobs:
        uid = jobs[0].uid
        db.mark_seen(uid)
        assert db.get_job(uid)["seen"] == 1
        db.mark_applied(uid)
        assert db.get_job(uid)["applied"] == 1
        assert db.get_job(uid)["applied_at"] is not None

    # Evaluación cacheada.
    db.save_evaluation(jobs[0].uid, "# Eval\nhola", "opencode-go/kimi-k2.6")
    assert db.get_evaluation(jobs[0].uid)["markdown"].startswith("# Eval")

    # Cuota SerpAPI.
    assert db.increment_quota("serpapi:2026-06") == 1
    assert db.increment_quota("serpapi:2026-06") == 2

    # Runs.
    rid = db.start_run("A", "2026-06-12")
    db.finish_run(rid, "ok", "prueba", nuevos)
    assert db.last_run("A")["status"] == "ok"

    print("OK: todas las aserciones de DB pasaron.")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
