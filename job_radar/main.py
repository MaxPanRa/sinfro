"""Punto de entrada de Job Radar. Lanza la aplicación PySide6.

Ejecutar en desarrollo:  python -m job_radar.main
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from . import __app_name__
from .config import DB_PATH
from .db.database import Database


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)

    db = Database(DB_PATH)

    # Import diferido para que la app falle limpio si falta una dependencia de UI.
    from .ui.main_window import MainWindow
    from .scheduler.scheduler import Scheduler

    window = MainWindow(db)
    # Inyecta el scheduler (Fase 5): QTimer Grupo A + ventanas Grupo B.
    window._scheduler = Scheduler(window)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
