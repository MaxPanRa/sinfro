"""Smoke test de la UI en modo offscreen: construye todo y procesa eventos.

No abre ventana real (usa QT_QPA_PLATFORM=offscreen). Verifica que MainWindow,
LeftPanel, Inbox, Scheduler y los diálogos se construyen sin errores.
Ejecutar:  python -m tests.test_ui_smoke
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from job_radar.db.database import Database  # noqa: E402
from job_radar.scheduler.scheduler import Scheduler  # noqa: E402
from job_radar.sources.base import Job  # noqa: E402


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    tmp = Path(tempfile.mkdtemp()) / "ui.db"
    db = Database(tmp)

    # Inserta una vacante de prueba para poblar la bandeja y el popup.
    job = Job(title="Senior React Engineer", company="Acme", source="RemoteOK",
              url="https://example.com/job", location="Remoto", modality="Remoto",
              description="React, TypeScript, Node. 100% remoto.")
    db.insert_job(job.to_dict())
    db.set_quick_classification(job.uid, 82, {"match_score": 82, "modalidad": "Remoto",
                                              "acepta_cdmx": True, "seniority": "Senior",
                                              "resumen_una_linea": "Buen match remoto"})

    from job_radar.ui.main_window import MainWindow
    from job_radar.ui.settings_dialog import SettingsDialog
    from job_radar.ui.evaluation_dialog import EvaluationDialog

    win = MainWindow(db)
    win._scheduler = Scheduler(win)
    win.show()
    app.processEvents()

    # Bandeja: debe listar la vacante.
    assert win.inbox.lista.count() == 1, win.inbox.lista.count()

    # Diálogo de ajustes: construye y carga.
    dlg = SettingsDialog(db, win)
    assert dlg.fast_model.text() == "opencode-go/deepseek-v4-flash"
    dlg.close()

    # Popup de evaluación: pre-cacheamos para probar la ruta de caché (sin red).
    db.save_evaluation(job.uid, "# Evaluación de Vacante\n## Veredicto\n- Aplicar: Sí",
                       "opencode-go/kimi-k2.6")
    ev = EvaluationDialog(db, win.service, win.pool, job.uid, win)
    app.processEvents()
    assert "Evaluación de Vacante" in ev.viewer.toMarkdown()
    ev.close()

    # Scheduler: activar/desactivar timers sin error.
    win._scheduler.set_active(True)
    assert win._scheduler.timer_a.isActive()
    win._scheduler.set_active(False)
    assert not win._scheduler.timer_a.isActive()

    # Ventana de Grupo B: lógica horaria.
    from datetime import datetime
    en_ventana = Scheduler._en_ventana_b(datetime.now().replace(hour=6, minute=2))
    fuera = Scheduler._en_ventana_b(datetime.now().replace(hour=12, minute=0))
    assert en_ventana and not fuera

    win.close()
    print("OK: UI offscreen construida y validada (bandeja, ajustes, popup, scheduler).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
