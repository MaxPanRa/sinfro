"""Ventana principal: menú, dos columnas, barra de estado y cableado general."""

from __future__ import annotations

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QMessageBox, QSplitter, QWidget,
)

from .. import __app_name__, __version__
from ..db.database import Database
from ..service import AppService
from ..sources import GROUP_A_SOURCES
from .evaluation_dialog import EvaluationDialog
from .inbox import Inbox
from .left_panel import LeftPanel
from .settings_dialog import SettingsDialog
from .workers import Worker


class MainWindow(QMainWindow):
    """Contenedor principal de la aplicación."""

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.service = AppService(db)
        self.pool = QThreadPool.globalInstance()
        self._scheduler = None  # se inyecta en Fase 5
        self._clasificando = 0

        self.setWindowTitle(f"{__app_name__} v{__version__}")
        self.resize(1180, 760)
        self._build_menu()
        self._build_body()
        self._wire()

    # -- Construcción ---------------------------------------------------------

    def _build_menu(self) -> None:
        barra = self.menuBar()
        menu_ajustes = barra.addMenu("Ajustes")
        act = QAction("Abrir Ajustes…", self)
        act.triggered.connect(self._abrir_ajustes)
        menu_ajustes.addAction(act)

        menu_ayuda = barra.addMenu("Ayuda")
        act_about = QAction("Acerca de", self)
        act_about.triggered.connect(self._about)
        menu_ayuda.addAction(act_about)

    def _build_body(self) -> None:
        splitter = QSplitter(Qt.Horizontal)
        self.left = LeftPanel(self.db, self.service, self.pool)
        self.inbox = Inbox(self.db)
        splitter.addWidget(self.left)
        splitter.addWidget(self.inbox)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 760])
        self.setCentralWidget(splitter)
        self.statusBar().showMessage("Listo. Monitoreo detenido.")

    def _wire(self) -> None:
        self.left.monitoring_toggled.connect(self._on_monitoring)
        self.left.filtros_cambiados.connect(
            lambda: self.inbox.set_mostrar_repetidas(self.left.mostrar_repetidas())
        )
        self.inbox.job_opened.connect(self._abrir_evaluacion)
        self.inbox.set_mostrar_repetidas(self.left.mostrar_repetidas())

    # -- Acciones de menú -----------------------------------------------------

    def _abrir_ajustes(self) -> None:
        dlg = SettingsDialog(self.db, self)
        dlg.exec()

    def _about(self) -> None:
        QMessageBox.information(
            self, "Acerca de",
            f"{__app_name__} v{__version__}\n\nMonitor de vacantes con IA "
            "(OpenCode). Persistencia local SQLite."
        )

    def _abrir_evaluacion(self, uid: str) -> None:
        dlg = EvaluationDialog(self.db, self.service, self.pool, uid, self)
        dlg.estado_cambiado.connect(self.inbox.refresh)
        dlg.exec()

    # -- Monitoreo (corrida inmediata; scheduler recurrente en Fase 5) --------

    def _on_monitoring(self, activo: bool) -> None:
        if self._scheduler is not None:
            # Si el scheduler de Fase 5 está presente, delega en él.
            self._scheduler.set_active(activo)
        if activo:
            self.statusBar().showMessage("Monitoreo iniciado. Buscando vacantes…")
            self.run_group_a()
        else:
            self.statusBar().showMessage("Monitoreo detenido.")
            self.left.set_estado("Monitoreo detenido.")

    def run_group_a(self) -> None:
        """Lanza una corrida del Grupo A en un worker (no bloquea la UI)."""
        proxies = self.service.proxies()

        def tarea() -> dict:
            total_nuevos: list[str] = []
            fallos: list[str] = []
            for source_cls in GROUP_A_SOURCES:
                src = source_cls(proxies=proxies)
                try:
                    jobs = src.fetch()
                    nuevos = self.service.ingest_jobs(jobs)
                    total_nuevos.extend(nuevos)
                except Exception as exc:  # noqa: BLE001 — una fuente no tumba al resto
                    fallos.append(f"{src.name}: {type(exc).__name__}")
            return {"nuevos": total_nuevos, "fallos": fallos}

        worker = Worker(tarea)
        worker.signals.result.connect(self._group_a_listo)
        worker.signals.error.connect(
            lambda m: self.statusBar().showMessage(f"Error en ingesta: {m}")
        )
        self.pool.start(worker)

    def _group_a_listo(self, data: dict) -> None:
        nuevos = data["nuevos"]
        fallos = data["fallos"]
        self.inbox.refresh()
        msg = f"Grupo A: {len(nuevos)} vacantes nuevas."
        if fallos:
            msg += f"  Fuentes con fallo: {', '.join(fallos)}"
        self.statusBar().showMessage(msg)
        self.left.set_estado(msg)
        # Encola la clasificación rápida de las nuevas.
        for uid in nuevos:
            self._encolar_clasificacion(uid)

    def _encolar_clasificacion(self, uid: str) -> None:
        client = self.service.build_client()
        self._clasificando += 1

        def tarea() -> str:
            self.service.classify_uid(client, uid)
            return uid

        worker = Worker(tarea)
        worker.signals.result.connect(lambda _uid: self.inbox.refresh())
        worker.signals.error.connect(
            lambda m: self.statusBar().showMessage(f"Clasificación falló: {m}")
        )
        worker.signals.finished.connect(self._fin_clasificacion)
        self.pool.start(worker)

    def _fin_clasificacion(self) -> None:
        self._clasificando = max(0, self._clasificando - 1)
        if self._clasificando == 0:
            self.statusBar().showMessage("Clasificación completada.")

    # -- Cierre limpio --------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 — API Qt
        if self._scheduler is not None:
            self._scheduler.stop()
        self.pool.clear()
        self.db.close()
        super().closeEvent(event)
