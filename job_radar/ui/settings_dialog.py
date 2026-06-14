"""Diálogo de Ajustes. Lee/guarda en la tabla ``settings`` de SQLite.

Incluye API key de OpenCode Go (oculta), modelos de clasificación y evaluación,
toggle de modelo gratis, key de SerpAPI, nivel de inglés, objetivo salarial,
toggle de proxy VPS y umbral de match.
"""

from __future__ import annotations

from PySide6.QtCore import QThreadPool, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from ..config import JOOBLE_MONTHLY_QUOTA, NIVELES_INGLES, SERPAPI_MONTHLY_QUOTA
from ..db.database import Database
from .workers import Worker


class SettingsDialog(QDialog):
    """Modal de configuración global."""

    #: Emitida tras una búsqueda manual de SerpAPI con los uids nuevos ingeridos.
    vacantes_nuevas = Signal(list)
    datos_limpiados = Signal()

    def __init__(self, db: Database, service=None, pool: QThreadPool | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.service = service
        self.pool = pool or QThreadPool.globalInstance()
        self.setWindowTitle("Ajustes")
        self.setMinimumWidth(560)
        self._build()
        # La ventana nunca excede la pantalla; el contenido se scrollea.
        avail = QGuiApplication.primaryScreen().availableGeometry().height()
        self.setMaximumHeight(avail - 60)
        self.resize(600, min(720, avail - 60))
        self._load()
        self._update_serp_quota()
        self._update_jooble_quota()

    def _build(self) -> None:
        # Todo el contenido va dentro de un área scrolleable (cabe en monitores chicos).
        dlg_layout = QVBoxLayout(self)
        dlg_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        _cont = QWidget()
        scroll.setWidget(_cont)
        dlg_layout.addWidget(scroll)
        root = QVBoxLayout(_cont)

        # --- OpenCode / IA ---
        grp_ia = QGroupBox("OpenCode Go e IA")
        f_ia = QFormLayout(grp_ia)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("Se inyecta como OPENCODE_API_KEY (no se loguea)")
        self.fast_model = QLineEdit()
        self.deep_model = QLineEdit()
        self.evaluation_mode = QComboBox()
        self.evaluation_mode.addItem("Rapida (modelo flash)", "rapida")
        self.evaluation_mode.addItem("Profunda (modelo completo)", "profunda")
        self.use_free = QCheckBox("Usar modelo gratuito de respaldo si se agota el saldo")
        self.free_model = QLineEdit()
        f_ia.addRow("API key de OpenCode Go:", self.api_key)
        f_ia.addRow("Modelo clasificación rápida:", self.fast_model)
        f_ia.addRow("Modelo evaluación profunda:", self.deep_model)
        f_ia.addRow("Modo al abrir vacante:", self.evaluation_mode)
        f_ia.addRow("", self.use_free)
        f_ia.addRow("Modelo gratuito (respaldo):", self.free_model)
        root.addWidget(grp_ia)

        # --- Fuentes externas ---
        grp_src = QGroupBox("Fuentes externas")
        f_src = QFormLayout(grp_src)
        self.serpapi_key = QLineEdit()
        self.serpapi_key.setEchoMode(QLineEdit.Password)
        self.serpapi_key.textChanged.connect(self._update_serp_quota)
        f_src.addRow("API key de SerpAPI:", self.serpapi_key)
        # Búsquedas restantes este mes + botón "Buscar ahora".
        self.lbl_serp_quota = QLabel("—")
        f_src.addRow("Búsquedas Google restantes:", self.lbl_serp_quota)
        self.btn_buscar_ahora = QPushButton("Buscar ahora")
        self.btn_buscar_ahora.clicked.connect(self._buscar_ahora)
        f_src.addRow("", self.btn_buscar_ahora)
        self.jooble_key = QLineEdit()
        self.jooble_key.setEchoMode(QLineEdit.Password)
        self.jooble_key.textChanged.connect(self._update_jooble_quota)
        f_src.addRow("API key de Jooble:", self.jooble_key)
        self.lbl_jooble_quota = QLabel("—")
        f_src.addRow("Busquedas Jooble restantes:", self.lbl_jooble_quota)
        self.btn_buscar_jooble = QPushButton("Buscar Jooble MX")
        self.btn_buscar_jooble.clicked.connect(self._buscar_jooble)
        f_src.addRow("", self.btn_buscar_jooble)
        self.ats_company = QLineEdit()
        self.ats_company.setPlaceholderText("slug o empresa: zillow, rippling, stripe...")
        f_src.addRow("Empresa / ATS:", self.ats_company)
        self.btn_buscar_empresa = QPushButton("Buscar empresa ATS")
        self.btn_buscar_empresa.clicked.connect(self._buscar_empresa_ats)
        f_src.addRow("", self.btn_buscar_empresa)
        self.group_b_hour = QComboBox()
        for h in range(12):
            am = 12 if h == 0 else h
            pm = 12 if h == 0 else h
            self.group_b_hour.addItem(f"{am}:00 AM / {pm}:00 PM", str(h))
        f_src.addRow("Búsqueda automática cada 12 h:", self.group_b_hour)
        self.proxy_enabled = QCheckBox("Activar proxy VPS (para enmascarar IP)")
        self.proxy_host = QLineEdit()
        self.proxy_host.setPlaceholderText("host:puerto (ej. 1.2.3.4:8080)")
        f_src.addRow("", self.proxy_enabled)
        f_src.addRow("Proxy host:puerto:", self.proxy_host)
        root.addWidget(grp_src)

        # --- Perfil / objetivos ---
        grp_perf = QGroupBox("Perfil y objetivos")
        f_perf = QFormLayout(grp_perf)
        self.nivel_ingles = QComboBox()
        self.nivel_ingles.addItems(NIVELES_INGLES)
        # Objetivo salarial: monto + moneda + periodo.
        fila_sal = QHBoxLayout()
        self.salario_monto = QSpinBox()
        self.salario_monto.setRange(0, 1_000_000)
        self.salario_moneda = QComboBox()
        self.salario_moneda.addItems(["USD", "MXN", "EUR"])
        self.salario_periodo = QComboBox()
        self.salario_periodo.addItems(["hora", "mes"])
        cont_sal = QWidget()
        fila_sal = QHBoxLayout(cont_sal)
        fila_sal.setContentsMargins(0, 0, 0, 0)
        fila_sal.addWidget(self.salario_monto)
        fila_sal.addWidget(self.salario_moneda)
        fila_sal.addWidget(QLabel("por"))
        fila_sal.addWidget(self.salario_periodo)
        self.match_threshold = QSpinBox()
        self.match_threshold.setRange(0, 100)
        self.match_threshold.setSuffix(" / 100")
        f_perf.addRow("Nivel de inglés:", self.nivel_ingles)
        f_perf.addRow("Objetivo salarial:", cont_sal)
        f_perf.addRow("Umbral mínimo de match:", self.match_threshold)
        root.addWidget(grp_perf)

        # --- Desarrollo ---
        grp_dev = QGroupBox("Desarrollo")
        f_dev = QFormLayout(grp_dev)
        self.dev_fast = QCheckBox("Scheduler rápido (intervalo 1 min para pruebas)")
        f_dev.addRow("", self.dev_fast)
        root.addWidget(grp_dev)

        grp_mant = QGroupBox("Mantenimiento")
        v_mant = QVBoxLayout(grp_mant)
        estilo_rojo = (
            "QPushButton{background:#c0392b;color:white;font-weight:bold;"
            "border-radius:6px;padding:7px 10px;} QPushButton:hover{background:#e74c3c;}")
        self.btn_limpiar_datos = QPushButton("Limpiar inbox del perfil actual")
        self.btn_limpiar_datos.setStyleSheet(estilo_rojo)
        self.btn_limpiar_datos.clicked.connect(self._limpiar_inbox_actual)
        v_mant.addWidget(self.btn_limpiar_datos)
        self.btn_limpiar_todos = QPushButton("Resetear TODOS los inboxes")
        self.btn_limpiar_todos.setStyleSheet(
            "QPushButton{background:#7f1d1d;color:white;font-weight:bold;"
            "border-radius:6px;padding:7px 10px;} QPushButton:hover{background:#991b1b;}")
        self.btn_limpiar_todos.clicked.connect(self._limpiar_todos_inboxes)
        v_mant.addWidget(self.btn_limpiar_todos)
        root.addWidget(grp_mant)

        botones = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._save_and_accept)
        botones.rejected.connect(self.reject)
        root.addWidget(botones)

    def _load(self) -> None:
        s = self.db.get_all_settings()
        self.api_key.setText(s.get("opencode_api_key", ""))
        self.fast_model.setText(s.get("fast_model", ""))
        self.deep_model.setText(s.get("deep_model", ""))
        idx_mode = self.evaluation_mode.findData(s.get("evaluation_mode", "rapida"))
        self.evaluation_mode.setCurrentIndex(max(0, idx_mode))
        self.use_free.setChecked(s.get("use_free_fallback", "0") == "1")
        self.free_model.setText(s.get("free_model", ""))
        self.serpapi_key.setText(s.get("serpapi_key", ""))
        self.jooble_key.setText(s.get("jooble_api_key", ""))
        self.ats_company.setText(s.get("ats_company", ""))
        idx_hour = self.group_b_hour.findData(s.get("group_b_hour", "6"))
        self.group_b_hour.setCurrentIndex(max(0, idx_hour))
        self.proxy_enabled.setChecked(s.get("proxy_enabled", "0") == "1")
        self.proxy_host.setText(s.get("proxy_host", ""))
        idx = self.nivel_ingles.findText(s.get("nivel_ingles", "B2"))
        self.nivel_ingles.setCurrentIndex(max(0, idx))
        self.salario_monto.setValue(int(s.get("salario_monto", "25") or 0))
        self.salario_moneda.setCurrentText(s.get("salario_moneda", "USD"))
        self.salario_periodo.setCurrentText(s.get("salario_periodo", "hora"))
        self.match_threshold.setValue(int(s.get("match_threshold", "70") or 0))
        self.dev_fast.setChecked(s.get("dev_fast_scheduler", "0") == "1")

    # -- SerpAPI: cuota y búsqueda manual -------------------------------------

    def _serp_remaining(self) -> int:
        """Búsquedas restantes este mes (usa el servicio si está disponible)."""
        if self.service is not None:
            return self.service.serpapi_remaining()
        from ..service import AppService
        return AppService(self.db).serpapi_remaining()

    def _update_serp_quota(self) -> None:
        """Refresca la etiqueta y el botón con el contador X/250."""
        restantes = self._serp_remaining()
        self.lbl_serp_quota.setText(f"{restantes}/{SERPAPI_MONTHLY_QUOTA} este mes")
        self.btn_buscar_ahora.setText(f"Buscar ahora ({restantes}/{SERPAPI_MONTHLY_QUOTA})")
        tiene_key = bool(self.serpapi_key.text().strip())
        self.btn_buscar_ahora.setEnabled(tiene_key and restantes > 0)

    def _jooble_remaining(self) -> int:
        if self.service is not None:
            return self.service.jooble_remaining()
        from ..service import AppService
        return AppService(self.db).jooble_remaining()

    def _update_jooble_quota(self) -> None:
        restantes = self._jooble_remaining()
        self.lbl_jooble_quota.setText(f"{restantes}/{JOOBLE_MONTHLY_QUOTA} este mes")
        self.btn_buscar_jooble.setText(
            f"Buscar Jooble MX ({restantes}/{JOOBLE_MONTHLY_QUOTA})"
        )
        tiene_key = bool(self.jooble_key.text().strip())
        self.btn_buscar_jooble.setEnabled(tiene_key and restantes > 0)

    def _buscar_ahora(self) -> None:
        """Lanza una búsqueda inmediata en Google for Jobs (SerpAPI) en un worker."""
        if self.service is None:
            QMessageBox.information(self, "No disponible",
                                   "La búsqueda manual no está disponible en este contexto.")
            return
        key = self.serpapi_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Falta la key", "Ingresa tu API key de SerpAPI.")
            return
        if self._serp_remaining() <= 0:
            QMessageBox.warning(self, "Sin cuota",
                                "Agotaste las búsquedas de SerpAPI de este mes.")
            return
        # Persiste la key para que la corrida y futuras llamadas la usen.
        self.db.set_setting("serpapi_key", key)

        from ..sources import SerpApiSource
        service = self.service
        query = service.build_serpapi_query()
        location = service.serpapi_location()
        self.btn_buscar_ahora.setEnabled(False)
        self.btn_buscar_ahora.setText("Buscando en Google…")

        def tarea() -> list[str]:
            src = SerpApiSource(api_key=key, query=query, location=location)
            nuevos = service.ingest_jobs(src.fetch())
            self.db.increment_quota(service.serpapi_period())
            return nuevos

        worker = Worker(tarea)
        worker.signals.result.connect(self._serp_listo)
        worker.signals.error.connect(self._serp_error)
        worker.signals.finished.connect(self._update_serp_quota)
        self.pool.start(worker)

    def _buscar_jooble(self) -> None:
        if self.service is None:
            QMessageBox.information(self, "No disponible",
                                    "La busqueda manual no esta disponible en este contexto.")
            return
        key = self.jooble_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Falta la key", "Ingresa tu API key de Jooble.")
            return
        if self._jooble_remaining() <= 0:
            QMessageBox.warning(self, "Sin cuota", "Agotaste las busquedas de Jooble de este mes.")
            return
        self.db.set_setting("jooble_api_key", key)

        from ..sources import JoobleSource
        service = self.service
        self.btn_buscar_jooble.setEnabled(False)
        self.btn_buscar_jooble.setText("Buscando en Jooble...")

        def tarea() -> list[str]:
            src = JoobleSource(
                api_key=key,
                keywords=service.build_jooble_query(),
                location=service.group_b_location(),
            )
            nuevos = service.ingest_jobs(src.fetch())
            self.db.increment_quota(service.jooble_period())
            return nuevos

        worker = Worker(tarea)
        worker.signals.result.connect(self._jooble_listo)
        worker.signals.error.connect(self._jooble_error)
        worker.signals.finished.connect(self._update_jooble_quota)
        self.pool.start(worker)

    def _buscar_empresa_ats(self) -> None:
        if self.service is None:
            QMessageBox.information(self, "No disponible",
                                    "La busqueda manual no esta disponible en este contexto.")
            return
        company = self.ats_company.text().strip()
        if not company:
            QMessageBox.warning(self, "Falta empresa", "Ingresa una empresa o slug ATS.")
            return
        self.db.set_setting("ats_company", company)
        key = self.jooble_key.text().strip()
        use_jooble = bool(key) and self._jooble_remaining() > 0
        if key:
            self.db.set_setting("jooble_api_key", key)

        from ..sources import ATSCompanySource, JoobleSource
        service = self.service
        self.btn_buscar_empresa.setEnabled(False)
        self.btn_buscar_empresa.setText("Buscando empresa...")

        def tarea() -> list[str]:
            jobs = ATSCompanySource(company=company).fetch()
            # El extra de Jooble es OPCIONAL: si falla (cuota/red/key), no debe
            # tumbar los resultados de los ATS (Lever/Greenhouse/Workable/Ashby).
            if use_jooble:
                try:
                    jobs.extend(JoobleSource(
                        api_key=key,
                        keywords=company,
                        location=service.group_b_location(),
                        companysearch=True,
                    ).fetch())
                    self.db.increment_quota(service.jooble_period())
                except Exception:  # noqa: BLE001 — Jooble es complemento, no crítico
                    pass
            return service.ingest_jobs(jobs)

        worker = Worker(tarea)
        worker.signals.result.connect(self._empresa_lista)
        worker.signals.error.connect(self._empresa_error)
        worker.signals.finished.connect(self._empresa_finished)
        self.pool.start(worker)

    def _serp_listo(self, nuevos: list) -> None:
        self._update_serp_quota()
        QMessageBox.information(
            self, "Búsqueda completada",
            f"Google for Jobs: {len(nuevos)} vacantes nuevas ingeridas."
        )
        if nuevos:
            self.vacantes_nuevas.emit(nuevos)

    def _serp_error(self, msg: str) -> None:
        self._update_serp_quota()
        QMessageBox.warning(self, "Error en SerpAPI", msg)

    def _jooble_listo(self, nuevos: list) -> None:
        self._update_jooble_quota()
        QMessageBox.information(
            self, "Busqueda completada",
            f"Jooble MX: {len(nuevos)} vacantes nuevas ingeridas.",
        )
        if nuevos:
            self.vacantes_nuevas.emit(nuevos)

    def _jooble_error(self, msg: str) -> None:
        self._update_jooble_quota()
        QMessageBox.warning(self, "Error en Jooble", msg)

    def _empresa_lista(self, nuevos: list) -> None:
        self._update_jooble_quota()
        QMessageBox.information(
            self, "Busqueda completada",
            f"Empresa/ATS: {len(nuevos)} vacantes nuevas ingeridas.",
        )
        if nuevos:
            self.vacantes_nuevas.emit(nuevos)

    def _empresa_error(self, msg: str) -> None:
        self._update_jooble_quota()
        QMessageBox.warning(self, "Error en empresa/ATS", msg)

    def _empresa_finished(self) -> None:
        self._update_jooble_quota()
        self.btn_buscar_empresa.setEnabled(True)
        self.btn_buscar_empresa.setText("Buscar empresa ATS")

    def _limpiar_inbox_actual(self) -> None:
        ok = QMessageBox.question(
            self,
            "Limpiar inbox del perfil actual",
            "Esto borra las vacantes y evaluaciones SOLO del perfil activo. Tus "
            "keywords, skills y resumen de este perfil se conservan.\n\n¿Continuar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if ok != QMessageBox.Yes:
            return
        self.db.clear_current_inbox()
        self.datos_limpiados.emit()
        QMessageBox.information(
            self, "Inbox limpiado",
            "El inbox del perfil activo quedó vacío.")

    def _limpiar_todos_inboxes(self) -> None:
        ok = QMessageBox.question(
            self,
            "Resetear TODOS los inboxes",
            "Esto borra las vacantes y evaluaciones de TODOS los perfiles, además "
            "del historial de corridas. Keywords, skills y resúmenes se conservan.\n\n"
            "¿Continuar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if ok != QMessageBox.Yes:
            return
        self.db.clear_all_inboxes()
        self.datos_limpiados.emit()
        QMessageBox.information(
            self, "Inboxes reseteados",
            "Se vaciaron los inboxes de todos los perfiles.")

    def _save_and_accept(self) -> None:
        pares = {
            "opencode_api_key": self.api_key.text().strip(),
            "fast_model": self.fast_model.text().strip(),
            "deep_model": self.deep_model.text().strip(),
            "evaluation_mode": str(self.evaluation_mode.currentData()),
            "use_free_fallback": "1" if self.use_free.isChecked() else "0",
            "free_model": self.free_model.text().strip(),
            "serpapi_key": self.serpapi_key.text().strip(),
            "jooble_api_key": self.jooble_key.text().strip(),
            "ats_company": self.ats_company.text().strip(),
            "proxy_enabled": "1" if self.proxy_enabled.isChecked() else "0",
            "proxy_host": self.proxy_host.text().strip(),
            "nivel_ingles": self.nivel_ingles.currentText(),
            "salario_monto": str(self.salario_monto.value()),
            "salario_moneda": self.salario_moneda.currentText(),
            "salario_periodo": self.salario_periodo.currentText(),
            "match_threshold": str(self.match_threshold.value()),
            "group_b_hour": str(self.group_b_hour.currentData()),
            "dev_fast_scheduler": "1" if self.dev_fast.isChecked() else "0",
        }
        for k, v in pares.items():
            self.db.set_setting(k, v)
        self.accept()
