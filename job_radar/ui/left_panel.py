"""Columna izquierda: parámetros de búsqueda y control de monitoreo."""

from __future__ import annotations

from PySide6.QtCore import QThreadPool, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QSpinBox,
    QTextEdit, QVBoxLayout, QWidget,
)

from ..config import DEFAULT_KEYWORDS, MODALIDADES, UBICACIONES
from ..db.database import Database
from ..profile.cv_parser import analyze_cv, extract_cv_text
from ..service import AppService
from .widgets import CheckableComboBox, Chip, FlowLayout, SkillBadge
from .workers import Worker


class LeftPanel(QWidget):
    """Panel de configuración de búsqueda. Persiste todo en SQLite."""

    #: Emitida al pulsar el botón grande: True=comenzar, False=detener.
    monitoring_toggled = Signal(bool)
    #: Emitida cuando cambian filtros que afectan la bandeja (repetidas).
    filtros_cambiados = Signal()

    def __init__(self, db: Database, service: AppService, pool: QThreadPool,
                 ai_pool: QThreadPool | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.service = service
        self.pool = pool
        self.ai_pool = ai_pool or pool
        self._monitoring = False
        self._build()
        self._load()

    # -- Construcción ---------------------------------------------------------

    def _build(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        contenido = QWidget()
        scroll.setWidget(contenido)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        col = QVBoxLayout(contenido)
        col.setContentsMargins(8, 8, 8, 8)
        col.setSpacing(7)

        col.addWidget(self._build_keywords())
        col.addWidget(self._build_modalidad_ubicacion())
        col.addWidget(self._build_tecnologias())
        col.addWidget(self._build_cv())
        col.addWidget(self._build_opciones())
        col.addWidget(self._build_control())
        col.addStretch(1)

    @staticmethod
    def _mini_label(texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setStyleSheet("color:#475569;font-size:10px;font-weight:bold;")
        return lbl

    def _build_keywords(self) -> QGroupBox:
        grp = QGroupBox("Palabras clave")
        v = QVBoxLayout(grp)
        v.setSpacing(5)
        fila = QHBoxLayout()
        self.kw_input = QLineEdit()
        self.kw_input.setPlaceholderText("Escribe una palabra clave…")
        self.kw_input.returnPressed.connect(self._add_keyword)
        btn = QPushButton("Agregar")
        btn.clicked.connect(self._add_keyword)
        fila.addWidget(self.kw_input)
        fila.addWidget(btn)
        v.addLayout(fila)
        self.kw_container = QWidget()
        self.kw_flow = FlowLayout(self.kw_container, spacing=3)
        v.addWidget(self.kw_container)
        return grp

    def _build_modalidad_ubicacion(self) -> QGroupBox:
        """Modalidad (multi-select) y Ubicación en la misma fila."""
        grp = QGroupBox("Modalidad y ubicación")
        h = QHBoxLayout(grp)
        h.setSpacing(8)

        col_m = QVBoxLayout()
        col_m.setSpacing(2)
        col_m.addWidget(self._mini_label("Modalidad"))
        self.modalidad_combo = CheckableComboBox("Cualquiera")
        self.modalidad_combo.addItems(MODALIDADES)
        self.modalidad_combo.changed.connect(self._save_modalidad)
        col_m.addWidget(self.modalidad_combo)
        h.addLayout(col_m, 1)

        col_u = QVBoxLayout()
        col_u.setSpacing(2)
        col_u.addWidget(self._mini_label("Ubicación"))
        self.ubicacion = QComboBox()
        self.ubicacion.addItems(UBICACIONES)
        self.ubicacion.currentTextChanged.connect(
            lambda t: self.db.set_setting("ubicacion", t)
        )
        col_u.addWidget(self.ubicacion)
        h.addLayout(col_u, 1)
        return grp

    def _build_tecnologias(self) -> QGroupBox:
        grp = QGroupBox("Mis tecnologías")
        v = QVBoxLayout(grp)
        v.setSpacing(5)
        fila = QHBoxLayout()
        self.tech_input = QLineEdit()
        self.tech_input.setPlaceholderText("Tecnología…")
        self.tech_level = QSpinBox()
        self.tech_level.setRange(1, 10)
        self.tech_level.setValue(5)
        self.tech_level.setPrefix("Nivel ")
        btn = QPushButton("Agregar")
        btn.clicked.connect(self._add_tech)
        self.tech_input.returnPressed.connect(self._add_tech)
        fila.addWidget(self.tech_input, 1)
        fila.addWidget(self.tech_level)
        fila.addWidget(btn)
        v.addLayout(fila)

        self.tech_container = QWidget()
        self.tech_flow = FlowLayout(self.tech_container, spacing=4)
        v.addWidget(self.tech_container)

        v.addWidget(self._build_tech_legend())
        return grp

    def _build_tech_legend(self) -> QWidget:
        """Leyenda: colores por origen y cómo editar/eliminar."""
        cont = QWidget()
        h = QHBoxLayout(cont)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        def swatch(color: str, texto: str) -> QWidget:
            w = QWidget()
            hh = QHBoxLayout(w)
            hh.setContentsMargins(0, 0, 0, 0)
            hh.setSpacing(4)
            q = QLabel()
            q.setFixedSize(12, 12)
            q.setStyleSheet(
                f"background:{color};border:1px solid #94a3b8;border-radius:3px;")
            t = QLabel(texto)
            t.setStyleSheet("color:#52606d;font-size:10px;")
            hh.addWidget(q)
            hh.addWidget(t)
            return w

        h.addWidget(swatch("#fde68a", "del CV"))
        h.addWidget(swatch("#fed7aa", "manual"))
        ayuda = QLabel("· clic: editar nivel · doble clic: eliminar")
        ayuda.setStyleSheet("color:#52606d;font-size:10px;")
        h.addWidget(ayuda)
        h.addStretch(1)
        return cont

    def _build_cv(self) -> QGroupBox:
        grp = QGroupBox("Mi CV y perfil")
        v = QVBoxLayout(grp)
        v.setSpacing(5)
        self.btn_cv = QPushButton("Cargar CV (PDF o DOCX)")
        self.btn_cv.clicked.connect(self._cargar_cv)
        v.addWidget(self.btn_cv)
        v.addWidget(self._mini_label(
            "Resumen del perfil (editable, se usa en cada evaluación):"))
        self.perfil_summary = QTextEdit()
        self.perfil_summary.setPlaceholderText(
            "Se autocompleta al cargar el CV; puedes editarlo."
        )
        self.perfil_summary.setMinimumHeight(170)
        self.perfil_summary.textChanged.connect(self._save_summary)
        v.addWidget(self.perfil_summary)
        return grp

    def _build_opciones(self) -> QGroupBox:
        grp = QGroupBox("Opciones")
        v = QVBoxLayout(grp)
        self.chk_repetidas = QCheckBox("Mostrar vacantes repetidas")
        self.chk_repetidas.stateChanged.connect(self._on_repetidas)
        v.addWidget(self.chk_repetidas)
        return grp

    def _build_control(self) -> QWidget:
        cont = QWidget()
        v = QVBoxLayout(cont)
        self.btn_monitor = QPushButton("▶  Comenzar monitoreo")
        self.btn_monitor.setMinimumHeight(44)
        self.btn_monitor.setStyleSheet(
            "QPushButton{background:#27ae60;color:white;font-weight:bold;font-size:14px;"
            "border-radius:6px;} QPushButton:hover{background:#2ecc71;}"
        )
        self.btn_monitor.clicked.connect(self._toggle_monitor)
        v.addWidget(self.btn_monitor)
        self.lbl_estado = QLabel("Monitoreo detenido.")
        self.lbl_estado.setWordWrap(True)
        self.lbl_estado.setStyleSheet("color:gray;font-size:11px;")
        v.addWidget(self.lbl_estado)
        return cont

    # -- Carga inicial --------------------------------------------------------

    def _load(self) -> None:
        self.db.seed_keywords_if_empty(DEFAULT_KEYWORDS)
        self._refresh_keywords()
        self._refresh_techs()
        self.perfil_summary.blockSignals(True)
        self.perfil_summary.setPlainText(self.db.get_profile_summary())
        self.perfil_summary.blockSignals(False)
        s = self.db.get_all_settings()
        sel = [m for m in (s.get("modalidades", "") or "").split(",") if m]
        self.modalidad_combo.blockSignals(True)
        self.modalidad_combo.set_checked(sel)
        self.modalidad_combo.blockSignals(False)
        ub = s.get("ubicacion", "")
        if ub:
            i = self.ubicacion.findText(ub)
            if i >= 0:
                self.ubicacion.setCurrentIndex(i)

    # -- Keywords -------------------------------------------------------------

    def _add_keyword(self) -> None:
        palabra = self.kw_input.text().strip()
        if palabra:
            self.db.add_keyword(palabra)
            self.kw_input.clear()
            self._refresh_keywords()

    def _refresh_keywords(self) -> None:
        while self.kw_flow.count():
            item = self.kw_flow.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        for palabra in self.db.get_keywords():
            chip = Chip(palabra)
            chip.removed.connect(self._remove_keyword)
            self.kw_flow.addWidget(chip)

    def _remove_keyword(self, palabra: str) -> None:
        self.db.remove_keyword(palabra)
        self._refresh_keywords()

    # -- Modalidad / opciones -------------------------------------------------

    def _save_modalidad(self) -> None:
        self.db.set_setting("modalidades", ",".join(self.modalidad_combo.checked_items()))

    def _on_repetidas(self) -> None:
        self.db.set_setting(
            "mostrar_repetidas", "1" if self.chk_repetidas.isChecked() else "0"
        )
        self.filtros_cambiados.emit()

    def mostrar_repetidas(self) -> bool:
        return self.chk_repetidas.isChecked()

    # -- Tecnologías ----------------------------------------------------------

    def _add_tech(self) -> None:
        nombre = self.tech_input.text().strip()
        if nombre:
            self.db.upsert_technology(nombre, self.tech_level.value(), "manual")
            self.tech_input.clear()
            self._refresh_techs()

    def _refresh_techs(self) -> None:
        while self.tech_flow.count():
            item = self.tech_flow.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        for t in self.db.get_technologies():
            badge = SkillBadge(t)
            badge.edit_requested.connect(self._edit_tech)
            badge.delete_requested.connect(self._delete_tech)
            self.tech_flow.addWidget(badge)

    def _edit_tech(self, tech_id: int) -> None:
        tech = next(
            (t for t in self.db.get_technologies() if t["id"] == tech_id), None)
        if not tech:
            return
        nivel, ok = QInputDialog.getInt(
            self, "Editar nivel", f"Nivel de {tech['name']} (1-10):",
            int(tech["level"]), 1, 10)
        if ok:
            self.db.update_technology_level(tech_id, nivel)
            self._refresh_techs()

    def _delete_tech(self, tech_id: int) -> None:
        self.db.remove_technology(int(tech_id))
        self._refresh_techs()

    # -- Perfil ---------------------------------------------------------------

    def _save_summary(self) -> None:
        self.db.set_profile_summary(self.perfil_summary.toPlainText())

    # -- CV -------------------------------------------------------------------

    def _cargar_cv(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Selecciona tu CV", "", "Documentos (*.pdf *.docx)"
        )
        if not ruta:
            return
        self.btn_cv.setEnabled(False)
        self.btn_cv.setText("Analizando CV con IA…")
        client = self.service.build_client()

        def tarea() -> dict:
            texto = extract_cv_text(ruta)
            if not texto.strip():
                raise ValueError("No se pudo extraer texto del CV.")
            return analyze_cv(client, texto)

        worker = Worker(tarea)
        worker.signals.result.connect(self._cv_listo)
        worker.signals.error.connect(self._cv_error)
        worker.signals.finished.connect(lambda: (
            self.btn_cv.setEnabled(True),
            self.btn_cv.setText("Cargar CV (PDF o DOCX)"),
        ))
        self.ai_pool.start(worker)

    def _cv_listo(self, data: dict) -> None:
        # Agrega tecnologías detectadas sin borrar ni duplicar las manuales.
        for t in data.get("tecnologias", []):
            self.db.upsert_technology(t["name"], t["level"], "cv")
        self._refresh_techs()
        resumen = data.get("resumen", "").strip()
        if resumen:
            actual = self.perfil_summary.toPlainText().strip()
            nuevo = resumen if not actual else f"{actual}\n\n{resumen}"
            self.perfil_summary.setPlainText(nuevo)
        QMessageBox.information(
            self, "CV analizado",
            f"Se detectaron {len(data.get('tecnologias', []))} tecnologías y se "
            "actualizó el resumen del perfil."
        )

    def _cv_error(self, msg: str) -> None:
        QMessageBox.warning(self, "Error al analizar el CV", msg)

    # -- Control de monitoreo -------------------------------------------------

    def _toggle_monitor(self) -> None:
        self._monitoring = not self._monitoring
        if self._monitoring:
            self.btn_monitor.setText("⏹  Detener monitoreo")
            self.btn_monitor.setStyleSheet(
                "QPushButton{background:#c0392b;color:white;font-weight:bold;"
                "font-size:14px;border-radius:6px;} QPushButton:hover{background:#e74c3c;}"
            )
        else:
            self.btn_monitor.setText("▶  Comenzar monitoreo")
            self.btn_monitor.setStyleSheet(
                "QPushButton{background:#27ae60;color:white;font-weight:bold;"
                "font-size:14px;border-radius:6px;} QPushButton:hover{background:#2ecc71;}"
            )
        self.monitoring_toggled.emit(self._monitoring)

    def set_estado(self, texto: str) -> None:
        self.lbl_estado.setText(texto)
