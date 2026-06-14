"""Ventana principal: menú, dos columnas, barra de estado y cableado general."""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QMessageBox, QSplitter, QWidget,
)

from .. import __app_name__, __version__
from ..config import GROUP_A_INTERVAL_MIN, ICON_PATH
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
        self.manual_ai_pool = QThreadPool()
        self.manual_ai_pool.setMaxThreadCount(1)
        self._scheduler = None  # se inyecta en Fase 5
        self._monitoring_active = False

        self.setWindowTitle(f"{__app_name__} v{__version__}")
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.resize(1180, 760)
        self._build_menu()
        self._build_body()
        self._wire()

    # -- Construcción ---------------------------------------------------------

    def _build_menu(self) -> None:
        barra = self.menuBar()
        self.menu_ajustes = barra.addMenu("Ajustes")
        act = QAction("Abrir Ajustes…", self)
        act.triggered.connect(self._abrir_ajustes)
        self.menu_ajustes.addAction(act)

        menu_ayuda = barra.addMenu("Ayuda")
        self.act_shared = QAction(
            "Usar un solo ajuste para todos los perfiles", self, checkable=True)
        self.act_shared.setChecked(self.db.settings_shared())
        self.act_shared.toggled.connect(self._toggle_shared_settings)
        menu_ayuda.addAction(self.act_shared)
        menu_ayuda.addSeparator()
        act_about = QAction("Acerca de", self)
        act_about.triggered.connect(self._about)
        menu_ayuda.addAction(act_about)
        self._update_settings_menu_label()

    def _update_settings_menu_label(self) -> None:
        if self.db.settings_shared():
            self.menu_ajustes.setTitle("Ajustes (compartidos)")
        else:
            self.menu_ajustes.setTitle(f"Ajustes · {self.db.active_profile_name()}")

    def _toggle_shared_settings(self, shared: bool) -> None:
        self.db.set_setting("settings_shared", "1" if shared else "0")
        self._update_settings_menu_label()
        self.left.reload_data()
        self.inbox.refresh()

    def _build_body(self) -> None:
        splitter = QSplitter(Qt.Horizontal)
        self.left = LeftPanel(self.db, self.service, self.pool, self.manual_ai_pool)
        self.inbox = Inbox(self.db, self.service)
        splitter.addWidget(self.left)
        splitter.addWidget(self.inbox)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 760])
        self.setCentralWidget(splitter)
        self.statusBar().showMessage("Listo. Monitoreo detenido.")

    def _wire(self) -> None:
        self.left.monitoring_toggled.connect(self._on_monitoring)
        # Al cambiar de perfil, la bandeja y el título de Ajustes se actualizan.
        self.left.profile_changed.connect(self.inbox.refresh)
        self.left.profile_changed.connect(self._update_settings_menu_label)
        self.inbox.job_opened.connect(self._abrir_evaluacion)

    # -- Acciones de menú -----------------------------------------------------

    def _abrir_ajustes(self) -> None:
        dlg = SettingsDialog(self.db, self.service, self.pool, self)
        dlg.vacantes_nuevas.connect(self._tras_busqueda_manual)
        dlg.datos_limpiados.connect(self._tras_limpiar_datos)
        dlg.exec()

    def _tras_busqueda_manual(self, nuevos: list) -> None:
        """Refresca la bandeja y clasifica las vacantes de una búsqueda manual."""
        self.inbox.refresh()
        self.statusBar().showMessage(
            f"Busqueda manual: {len(nuevos)} vacantes nuevas con compatibilidad preliminar."
        )

    def _tras_limpiar_datos(self) -> None:
        self.inbox.refresh()
        self.statusBar().showMessage("Bandeja e historial limpiados.")

    def _about(self) -> None:
        QMessageBox.information(
            self, "Acerca de",
            f"{__app_name__} v{__version__}\n\nMonitor de vacantes con IA "
            "(OpenCode). Persistencia local SQLite."
        )

    def _abrir_evaluacion(self, uid: str) -> None:
        dlg = EvaluationDialog(self.db, self.service, self.manual_ai_pool, uid, self)
        dlg.estado_cambiado.connect(self.inbox.refresh)
        dlg.exec()

    # -- Monitoreo (corrida inmediata; scheduler recurrente en Fase 5) --------

    def _on_monitoring(self, activo: bool) -> None:
        self._monitoring_active = activo
        if self._scheduler is not None:
            # Si el scheduler de Fase 5 está presente, delega en él.
            self._scheduler.set_active(activo)
        if activo:
            self.statusBar().showMessage("Monitoreo iniciado. Buscando vacantes…")
            self.run_group_a()
        else:
            self.statusBar().showMessage("Monitoreo detenido.")
            self.left.set_estado("Monitoreo detenido.")

    def _on_progress(self, texto: str) -> None:
        """Muestra el progreso en vivo debajo del botón y en la barra de estado."""
        self.left.set_estado(texto)
        self.statusBar().showMessage(texto)

    def _proxima_corrida_str(self) -> str:
        """Hora aproximada de la próxima corrida del Grupo A."""
        dev = self.db.get_setting("dev_fast_scheduler", "0") == "1"
        mins = 1 if dev else GROUP_A_INTERVAL_MIN
        return (datetime.now() + timedelta(minutes=mins)).strftime("%H:%M:%S")

    def run_group_a(self) -> None:
        """Lanza una corrida del Grupo A en un worker (no bloquea la UI)."""
        proxies = self.service.proxies()
        worker = Worker(self._fetch_group_a, proxies)
        worker.kwargs = {"progress": worker.signals.progress.emit}
        worker.signals.progress.connect(self._on_progress)
        worker.signals.result.connect(self._group_a_listo)
        worker.signals.error.connect(
            lambda m: self.statusBar().showMessage(f"Error en ingesta: {m}")
        )
        self.pool.start(worker)

    def _fetch_group_a(self, proxies, progress=None) -> dict:
        total_nuevos: list[str] = []
        fallos: list[str] = []
        for source_cls in GROUP_A_SOURCES:
            src = source_cls(proxies=proxies)
            if progress:
                progress(f"🔎 Buscando en {src.name}…")
            try:
                total_nuevos.extend(self.service.ingest_jobs(src.fetch()))
            except Exception as exc:  # noqa: BLE001 — una fuente no tumba al resto
                fallos.append(f"{src.name}: {type(exc).__name__}")
        return {"nuevos": total_nuevos, "fallos": fallos}

    def _group_a_listo(self, data: dict) -> None:
        nuevos = data["nuevos"]
        fallos = data["fallos"]
        self.inbox.refresh()
        resumen = f"{len(nuevos)} vacantes nuevas"
        if fallos:
            resumen += f" · fallos: {', '.join(fallos)}"
        if self._monitoring_active:
            estado = (f"✅ {resumen}. Esperando hasta las "
                      f"{self._proxima_corrida_str()} para volver a buscar…")
        else:
            estado = f"✅ {resumen}. Monitoreo detenido."
        self.statusBar().showMessage(estado)
        self.left.set_estado(estado)

    def run_group_b(self, day_key: str) -> None:
        """Corrida del Grupo B (JobSpy + SerpAPI). Registra la corrida en ``runs``.

        Respeta la cuota mensual de SerpAPI y salta fuentes desactivadas (OCC).
        """
        from ..sources import (
            AdzunaSource, JobSpySource, JoobleSource, OCCSource, SerpApiSource,
        )

        proxies = self.service.proxies()
        query = self.service.build_group_b_query()
        location = self.service.group_b_location()
        serpapi_query = self.service.build_serpapi_query()
        serpapi_location = self.service.serpapi_location()
        serpapi_key = self.db.get_setting("serpapi_key", "")
        serp_disponible = bool(serpapi_key) and self.service.serpapi_remaining() > 0
        jooble_key = self.db.get_setting("jooble_api_key", "")
        jooble_disponible = bool(jooble_key) and self.service.jooble_remaining() > 0
        adzuna_id = self.db.get_setting("adzuna_app_id", "")
        adzuna_key = self.db.get_setting("adzuna_app_key", "")
        adzuna_disponible = bool(adzuna_id) and bool(adzuna_key)
        run_id = self.db.start_run("B", day_key)

        def tarea(progress=None) -> dict:
            def avisa(nombre: str) -> None:
                if progress:
                    progress(f"🔎 Buscando en {nombre}…")
            nuevos: list[str] = []
            fallos: list[str] = []
            # JobSpy (LinkedIn + Indeed).
            avisa("LinkedIn/Indeed")
            try:
                js = JobSpySource(search_term=query, location=location, proxies=proxies)
                nuevos.extend(self.service.ingest_jobs(js.fetch()))
            except Exception as exc:  # noqa: BLE001
                fallos.append(f"JobSpy: {type(exc).__name__}")
            # OCC Mundial (parsing HTML).
            avisa("OCC Mundial")
            try:
                occ = OCCSource(query=query, location=location, proxies=proxies)
                nuevos.extend(self.service.ingest_jobs(occ.fetch()))
            except Exception as exc:  # noqa: BLE001
                fallos.append(f"OCC: {type(exc).__name__}")
            # SerpAPI (si hay key y cuota).
            if serp_disponible:
                avisa("Google for Jobs")
                try:
                    sp = SerpApiSource(
                        api_key=serpapi_key,
                        query=serpapi_query,
                        location=serpapi_location,
                    )
                    nuevos.extend(self.service.ingest_jobs(sp.fetch()))
                    self.db.increment_quota(self.service.serpapi_period())
                except Exception as exc:  # noqa: BLE001
                    fallos.append(f"SerpAPI: {type(exc).__name__}")
            # Jooble MX (si hay key y cuota).
            if jooble_disponible:
                avisa("Jooble MX")
                try:
                    jooble = JoobleSource(
                        api_key=jooble_key,
                        keywords=self.service.build_jooble_query(),
                        location=self.service.group_b_location(),
                        proxies=proxies,
                    )
                    nuevos.extend(self.service.ingest_jobs(jooble.fetch()))
                    self.db.increment_quota(self.service.jooble_period())
                except Exception as exc:  # noqa: BLE001
                    fallos.append(f"Jooble: {type(exc).__name__}")
            # Adzuna (México + todas las profesiones; requiere app_id/app_key).
            if adzuna_disponible:
                avisa("Adzuna")
                try:
                    adz = AdzunaSource(
                        app_id=adzuna_id,
                        app_key=adzuna_key,
                        query=query,
                        location=location,
                        country="mx",
                        proxies=proxies,
                    )
                    nuevos.extend(self.service.ingest_jobs(adz.fetch()))
                except Exception as exc:  # noqa: BLE001
                    fallos.append(f"Adzuna: {type(exc).__name__}")
            return {"nuevos": nuevos, "fallos": fallos, "run_id": run_id}

        worker = Worker(tarea)
        worker.kwargs = {"progress": worker.signals.progress.emit}
        worker.signals.progress.connect(self._on_progress)
        worker.signals.result.connect(self._group_b_listo)
        worker.signals.error.connect(
            lambda m: self.statusBar().showMessage(f"Error en Grupo B: {m}")
        )
        self.pool.start(worker)

    def _group_b_listo(self, data: dict) -> None:
        nuevos, fallos = data["nuevos"], data["fallos"]
        self.db.finish_run(
            data["run_id"], "error" if fallos and not nuevos else "ok",
            ", ".join(fallos), len(nuevos),
        )
        self.inbox.refresh()
        restante = self.service.serpapi_remaining()
        msg = (
            f"✅ Grupo B: {len(nuevos)} vacantes nuevas. "
            f"SerpAPI: {restante} · Jooble: {self.service.jooble_remaining()}."
        )
        if fallos:
            msg += f" Fallos: {', '.join(fallos)}"
        if self._monitoring_active:
            msg += (f" Esperando hasta las {self._proxima_corrida_str()} "
                    "para volver a buscar…")
        self.statusBar().showMessage(msg)
        self.left.set_estado(msg)
        if not self._monitoring_active:
            return
        self.inbox.refresh()

    def _encolar_clasificaciones(self, uids: list[str], *, require_monitoring: bool) -> None:
        return
        for uid in uids[:MAX_AUTO_CLASSIFICATIONS]:
            self._encolar_clasificacion(uid, require_monitoring=require_monitoring)
        restantes = max(0, len(uids) - MAX_AUTO_CLASSIFICATIONS)
        if restantes:
            self.statusBar().showMessage(
                f"Clasificando {MAX_AUTO_CLASSIFICATIONS} vacantes; "
                f"{restantes} quedan sin IA para evitar saturar OpenCode."
            )

    def _encolar_clasificacion(self, uid: str, *, require_monitoring: bool) -> None:
        return
        client = self.service.build_client()
        epoch = self._classification_epoch
        self._clasificando += 1

        def tarea() -> str:
            if require_monitoring and (
                not self._monitoring_active or epoch != self._classification_epoch
            ):
                return uid
            self.service.classify_uid(client, uid)
            return uid

        worker = Worker(tarea)
        worker.signals.result.connect(lambda _uid: self.inbox.refresh())
        worker.signals.error.connect(
            lambda m: self.statusBar().showMessage(f"Clasificación falló: {m}")
        )
        worker.signals.finished.connect(self._fin_clasificacion)
        self.classification_pool.start(worker)

    def _fin_clasificacion(self) -> None:
        self._clasificando = max(0, self._clasificando - 1)
        if self._clasificando == 0:
            self.statusBar().showMessage("Clasificación completada.")

    # -- Cierre limpio --------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 — API Qt
        if self._scheduler is not None:
            self._scheduler.stop()
        self.pool.clear()
        self.manual_ai_pool.clear()
        self.db.close()
        super().closeEvent(event)
