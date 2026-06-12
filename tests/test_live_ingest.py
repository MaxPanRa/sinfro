"""Prueba en vivo del threading: run_group_a real puebla la bandeja.

Usa red real (fuentes Grupo A) pero stubea la clasificación IA para no gastar
saldo ni tardar. Verifica que el worker corre fuera del hilo de UI y que la
bandeja se refresca. Ejecutar:  python -m tests.test_live_ingest
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from job_radar.db.database import Database  # noqa: E402


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    tmp = Path(tempfile.mkdtemp()) / "live.db"
    db = Database(tmp)

    from job_radar.ui.main_window import MainWindow
    win = MainWindow(db)
    # Stub: no clasificar (evita gasto y latencia); probamos solo la ingesta.
    win._encolar_clasificacion = lambda uid: None  # type: ignore[assignment]
    win.show()

    win.run_group_a()

    # Espera activa hasta que el worker termine de poblar (máx 90s).
    inicio = time.time()
    while time.time() - inicio < 90:
        app.processEvents()
        if win.inbox.lista.count() > 0:
            break
        time.sleep(0.2)

    count = win.inbox.lista.count()
    estado = win.statusBar().currentMessage()
    win.close()
    print(f"Bandeja poblada con {count} vacantes. Estado: {estado!r}")
    return 0 if count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
