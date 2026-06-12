"""Diálogo de Ajustes. Lee/guarda en la tabla ``settings`` de SQLite.

Incluye API key de OpenCode Go (oculta), modelos de clasificación y evaluación,
toggle de modelo gratis, key de SerpAPI, nivel de inglés, objetivo salarial,
toggle de proxy VPS y umbral de match.
"""

from __future__ import annotations

from PySide6.QtCore import QThreadPool, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)

from ..config import NIVELES_INGLES, SERPAPI_MONTHLY_QUOTA
from ..db.database import Database
from .workers import Worker


class SettingsDialog(QDialog):
    """Modal de configuración global."""

    #: Emitida tras una búsqueda manual de SerpAPI con los uids nuevos ingeridos.
    vacantes_nuevas = Signal(list)

    def __init__(self, db: Database, service=None, pool: QThreadPool | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.service = service
        self.pool = pool or QThreadPool.globalInstance()
        self.setWindowTitle("Ajustes")
        self.setMinimumWidth(560)
        self._build()
        self._load()
        self._update_serp_quota()

    def _build(self) -> None:
        root = QVBoxLayout(self)

        # --- OpenCode / IA ---
        grp_ia = QGroupBox("OpenCode Go e IA")
        f_ia = QFormLayout(grp_ia)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("Se inyecta como OPENCODE_API_KEY (no se loguea)")
        self.fast_model = QLineEdit()
        self.deep_model = QLineEdit()
        self.use_free = QCheckBox("Usar modelo gratuito de respaldo si se agota el saldo")
        self.free_model = QLineEdit()
        f_ia.addRow("API key de OpenCode Go:", self.api_key)
        f_ia.addRow("Modelo clasificación rápida:", self.fast_model)
        f_ia.addRow("Modelo evaluación profunda:", self.deep_model)
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

        botones = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._save_and_accept)
        botones.rejected.connect(self.reject)
        root.addWidget(botones)

    def _load(self) -> None:
        s = self.db.get_all_settings()
        self.api_key.setText(s.get("opencode_api_key", ""))
        self.fast_model.setText(s.get("fast_model", ""))
        self.deep_model.setText(s.get("deep_model", ""))
        self.use_free.setChecked(s.get("use_free_fallback", "0") == "1")
        self.free_model.setText(s.get("free_model", ""))
        self.serpapi_key.setText(s.get("serpapi_key", ""))
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
        query = service.build_group_b_query()
        location = service.group_b_location()
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

    def _save_and_accept(self) -> None:
        pares = {
            "opencode_api_key": self.api_key.text().strip(),
            "fast_model": self.fast_model.text().strip(),
            "deep_model": self.deep_model.text().strip(),
            "use_free_fallback": "1" if self.use_free.isChecked() else "0",
            "free_model": self.free_model.text().strip(),
            "serpapi_key": self.serpapi_key.text().strip(),
            "proxy_enabled": "1" if self.proxy_enabled.isChecked() else "0",
            "proxy_host": self.proxy_host.text().strip(),
            "nivel_ingles": self.nivel_ingles.currentText(),
            "salario_monto": str(self.salario_monto.value()),
            "salario_moneda": self.salario_moneda.currentText(),
            "salario_periodo": self.salario_periodo.currentText(),
            "match_threshold": str(self.match_threshold.value()),
            "dev_fast_scheduler": "1" if self.dev_fast.isChecked() else "0",
        }
        for k, v in pares.items():
            self.db.set_setting(k, v)
        self.accept()
