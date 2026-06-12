"""Diálogo de Ajustes. Lee/guarda en la tabla ``settings`` de SQLite.

Incluye API key de OpenCode Go (oculta), modelos de clasificación y evaluación,
toggle de modelo gratis, key de SerpAPI, nivel de inglés, objetivo salarial,
toggle de proxy VPS y umbral de match.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QSpinBox, QVBoxLayout, QWidget,
)

from ..config import NIVELES_INGLES
from ..db.database import Database


class SettingsDialog(QDialog):
    """Modal de configuración global."""

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Ajustes")
        self.setMinimumWidth(560)
        self._build()
        self._load()

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
        f_src.addRow("API key de SerpAPI:", self.serpapi_key)
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
