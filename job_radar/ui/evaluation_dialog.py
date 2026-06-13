"""Popup modal de evaluación de una vacante (con pestañas y diseño moderno)."""

from __future__ import annotations

import webbrowser

from PySide6.QtCore import QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTabWidget,
    QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from ..db.database import Database
from ..service import AppService
from .eval_render import render_eval_html


class EvaluationDialog(QDialog):
    """Diálogo amplio con pestañas: análisis embellecido + vacante original."""

    estado_cambiado = Signal()  # avisa a la bandeja para refrescar

    def __init__(self, db: Database, service: AppService, pool: QThreadPool,
                 uid: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.service = service
        self.pool = pool
        self.uid = uid
        self.job = db.get_job(uid) or {}
        self._eval_running = False
        self._eval_seconds = 0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick_eval)
        self.setWindowTitle("Evaluación de vacante")
        self.resize(760, 800)
        self._build()
        self._cargar_evaluacion(force=False)

    # -- Construcción ---------------------------------------------------------

    def _build(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(8)

        v.addWidget(self._build_header())

        # Pestañas: Análisis / Vacante original.
        self.tabs = QTabWidget()
        self.viewer = QTextBrowser()
        self.viewer.setOpenExternalLinks(True)
        self.viewer.setStyleSheet("QTextBrowser{border:none;background:#ffffff;}")
        self.tabs.addTab(self.viewer, "🔍  Análisis")

        self.tabs.addTab(self._build_raw_tab(), "📄  Vacante (editable)")
        v.addWidget(self.tabs, 1)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#7f8c8d;font-size:11px;")
        v.addWidget(self.lbl_status)

        v.addLayout(self._build_buttons())
        self._sync_aplicar()
        self._actualizar_boton_analisis()

    def _build_header(self) -> QFrame:
        card = QFrame()
        card.setObjectName("EvalHeader")
        card.setStyleSheet(
            "#EvalHeader{background:#f8fafc;border:1px solid #e2e8f0;"
            "border-radius:10px;}")
        h = QHBoxLayout(card)
        h.setContentsMargins(14, 10, 12, 10)

        col = QVBoxLayout()
        col.setSpacing(2)
        titulo = QLabel(self.job.get("title", ""))
        titulo.setWordWrap(True)
        titulo.setStyleSheet("font-size:15px;font-weight:bold;color:#0f172a;")
        col.addWidget(titulo)
        meta = " · ".join(filter(None, [
            self.job.get("company", ""), self.job.get("source", ""),
            self.job.get("modality", ""), self.job.get("location", ""),
        ]))
        lbl_meta = QLabel(meta)
        lbl_meta.setStyleSheet("color:#64748b;font-size:11px;")
        lbl_meta.setWordWrap(True)
        col.addWidget(lbl_meta)
        h.addLayout(col, 1)

        # Chip de compatibilidad.
        self.chip_score = QLabel()
        self.chip_score.setFixedWidth(64)
        self.chip_score.setAlignment(Qt.AlignCenter)
        self.chip_score.setStyleSheet(
            "font-size:16px;font-weight:bold;border-radius:8px;padding:8px 4px;")
        h.addWidget(self.chip_score)
        self._actualizar_chip()
        return card

    def _build_buttons(self) -> QHBoxLayout:
        botones = QHBoxLayout()
        botones.setSpacing(6)
        self.btn_aplicar = QPushButton("✓  Aplicar")
        self.btn_aplicar.setStyleSheet(
            "QPushButton{background:#16a34a;color:white;border:none;font-weight:bold;}"
            "QPushButton:hover{background:#15803d;}"
            "QPushButton:disabled{background:#cbd5e1;color:#64748b;}")
        self.btn_aplicar.clicked.connect(self._aplicar)
        self.btn_analizar = QPushButton("🔬  Análisis Profundo")
        self.btn_analizar.clicked.connect(self._on_analizar)
        btn_ir = QPushButton("🌐  Ir al sitio")
        btn_ir.clicked.connect(self._ir_al_sitio)
        btn_copiar = QPushButton("📋  Copiar URL")
        btn_copiar.clicked.connect(self._copiar_url)
        self.btn_descartar = QPushButton("🗑  Descartar")
        self.btn_descartar.clicked.connect(self._descartar)
        self.btn_cerrar = QPushButton("✕  Cerrar")
        self.btn_cerrar.setToolTip("Cierra sin descartar; solo marca como vista.")
        self.btn_cerrar.clicked.connect(self._cerrar)
        for b in (self.btn_aplicar, self.btn_analizar, btn_ir, btn_copiar,
                  self.btn_descartar, self.btn_cerrar):
            botones.addWidget(b)
        return botones

    def _build_raw_tab(self) -> QWidget:
        """Pestaña con el contenido de la vacante EDITABLE (mejora el análisis)."""
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(2, 4, 2, 2)
        v.setSpacing(5)

        url = self.job.get("url", "")
        if url:
            link = QLabel(f'<a href="{url}">{url}</a>')
            link.setOpenExternalLinks(True)
            link.setWordWrap(True)
            link.setStyleSheet("font-size:11px;")
            v.addWidget(link)

        ayuda = QLabel(
            "✏️ Edita o pega aquí el texto completo de la vacante (a veces las "
            "fuentes lo traen recortado). Guarda y vuelve a analizar para una "
            "evaluación más precisa.")
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet("color:#64748b;font-size:11px;")
        v.addWidget(ayuda)

        self.desc_edit = QTextEdit()
        self.desc_edit.setAcceptRichText(False)
        self.desc_edit.setPlainText(self.job.get("description", "") or "")
        v.addWidget(self.desc_edit, 1)

        fila = QHBoxLayout()
        fila.addStretch(1)
        btn_guardar = QPushButton("💾  Guardar contenido")
        btn_guardar.setStyleSheet(
            "QPushButton{background:#2563eb;color:white;border:none;font-weight:bold;}"
            "QPushButton:hover{background:#1d4ed8;}")
        btn_guardar.clicked.connect(self._guardar_contenido)
        fila.addWidget(btn_guardar)
        v.addLayout(fila)
        return w

    def _guardar_contenido(self) -> None:
        texto = self.desc_edit.toPlainText().strip()
        self.db.update_job_description(self.uid, texto)
        self.job["description"] = texto
        self.lbl_status.setText("Contenido guardado ✓")
        # Ofrece reanalizar de inmediato con el texto editado.
        box = QMessageBox(self)
        box.setWindowTitle("Contenido guardado")
        box.setIcon(QMessageBox.Question)
        box.setText("Se guardó el contenido de la vacante.\n\n"
                    "¿Quieres reanalizarla ahora con el texto editado?")
        btn_si = box.addButton("Sí, reanalizar", QMessageBox.YesRole)
        box.addButton("Ahora no", QMessageBox.NoRole)
        box.setDefaultButton(btn_si)
        box.exec()
        if box.clickedButton() is btn_si:
            self.tabs.setCurrentIndex(0)
            self._cargar_evaluacion(force=True, mode=None)

    # -- Chip / etiquetas dinámicas -------------------------------------------

    def _actualizar_chip(self) -> None:
        job = self.db.get_job(self.uid) or {}
        score = job.get("quick_score")
        threshold = self.service.compatibility_threshold()
        if score is None:
            self.chip_score.setText("¿?")
            self.chip_score.setStyleSheet(
                self.chip_score.styleSheet() + "background:#e5e7eb;color:#4b5563;")
            return
        from .inbox import score_color
        color = score_color(int(score), threshold)
        fg = "#3f3f00" if color == "#eab308" else "white"
        self.chip_score.setText(f"{score}%")
        self.chip_score.setStyleSheet(
            "font-size:16px;font-weight:bold;border-radius:8px;padding:8px 4px;"
            f"background:{color};color:{fg};")

    def _actualizar_boton_analisis(self) -> None:
        """'Análisis Profundo' si el actual es rápido; 'Volver a Analizar' si es profundo."""
        if self._eval_running:
            return
        mode = self.service.current_eval_mode(self.uid)
        if mode == "profunda":
            self.btn_analizar.setText("🔄  Volver a Analizar")
            self.btn_analizar.setToolTip(
                "Re-analiza usando el modo configurado en Ajustes.")
        else:
            self.btn_analizar.setText("🔬  Análisis Profundo")
            self.btn_analizar.setToolTip(
                "Genera un análisis profundo y detallado con el modelo capaz.")

    def _on_analizar(self) -> None:
        """Profundo si el actual es rápido/inexistente; según Ajustes si ya es profundo."""
        mode = self.service.current_eval_mode(self.uid)
        if mode == "profunda":
            self._cargar_evaluacion(force=True, mode=None)       # según Ajustes
        else:
            self._cargar_evaluacion(force=True, mode="profunda")  # fuerza profundo

    # -- Evaluación -----------------------------------------------------------

    def _cargar_evaluacion(self, force: bool, mode: str | None = None) -> None:
        if self._eval_running:
            return
        cached = None if force else self.db.get_evaluation(self.uid)
        if cached:
            self.viewer.setHtml(render_eval_html(cached["markdown"]))
            self.lbl_status.setText(
                f"Análisis cacheado ({cached.get('created_at','')[:16].replace('T',' ')}).")
            self._actualizar_chip()
            self._actualizar_boton_analisis()
            return

        # Generar en hilo de fondo.
        etiqueta = "profundo" if (mode == "profunda" or
                                  self.db.get_setting("evaluation_mode") == "profunda"
                                  ) else "rápido"
        self.viewer.setHtml(
            f'<div style="color:#64748b;font-size:13px;padding:20px;">'
            f'⏳ Generando análisis {etiqueta} con IA… espera.</div>')
        self.lbl_status.setText("Llamando a OpenCode… 0s")
        self._eval_running = True
        self._eval_seconds = 0
        self._timer.start()
        self.btn_analizar.setEnabled(False)
        self.btn_analizar.setText("⏳  Analizando…")
        client = self.service.build_client()

        def tarea() -> str:
            return self.service.get_or_create_evaluation(
                client, self.uid, force=force, mode=mode)

        from .workers import Worker
        worker = Worker(tarea)
        worker.signals.result.connect(self._eval_lista)
        worker.signals.error.connect(self._eval_error)
        worker.signals.finished.connect(self._eval_finished)
        self.pool.start(worker)

    def _tick_eval(self) -> None:
        if not self._eval_running:
            return
        self._eval_seconds += 1
        self.lbl_status.setText(
            f"Llamando a OpenCode… {self._eval_seconds}s. "
            "Los análisis profundos pueden tardar 1-3 min.")

    def _eval_finished(self) -> None:
        self._eval_running = False
        self._timer.stop()
        self.btn_analizar.setEnabled(True)
        self._actualizar_boton_analisis()

    def _eval_lista(self, markdown: str) -> None:
        self.viewer.setHtml(render_eval_html(markdown))
        self._actualizar_chip()
        self.estado_cambiado.emit()
        self.lbl_status.setText("Análisis generado y cacheado ✓")

    def _eval_error(self, msg: str) -> None:
        self.viewer.setHtml(
            f'<div style="padding:16px;color:#334155;">'
            f'<h3 style="color:#dc2626;">No se pudo generar el análisis</h3>'
            f'<pre style="background:#f1f5f9;padding:8px;color:#475569;">{msg}</pre>'
            f'<p>Revisa tu API key / saldo de OpenCode Go en Ajustes, o activa el '
            f'modelo gratuito de respaldo.</p></div>')
        self.lbl_status.setText("Error al generar el análisis.")

    # -- Acciones -------------------------------------------------------------

    def _sync_aplicar(self) -> None:
        job = self.db.get_job(self.uid) or {}
        if job.get("applied"):
            fecha = (job.get("applied_at") or "")[:16].replace("T", " ")
            self.btn_aplicar.setEnabled(False)
            self.btn_aplicar.setText(f"✓ Aplicada el {fecha}")

    def _aplicar(self) -> None:
        # 1) Manda al usuario a la URL de la vacante.
        url = (self.db.get_job(self.uid) or {}).get("url", "")
        if url:
            self.db.mark_visited_site(self.uid)
            webbrowser.open(url)
        # 2) Espera su confirmación de vuelta (botones en español).
        box = QMessageBox(self)
        box.setWindowTitle("Confirmar aplicación")
        box.setIcon(QMessageBox.Question)
        box.setText("Se abrió la vacante en tu navegador.\n\n¿Aplicaste a la vacante?")
        btn_si = box.addButton("Sí", QMessageBox.YesRole)
        box.addButton("No", QMessageBox.NoRole)
        box.setDefaultButton(btn_si)
        box.exec()
        if box.clickedButton() is btn_si:
            self.db.mark_applied(self.uid)
            self._sync_aplicar()
        self.estado_cambiado.emit()

    def _ir_al_sitio(self) -> None:
        url = (self.db.get_job(self.uid) or {}).get("url", "")
        if url:
            self.db.mark_visited_site(self.uid)
            self.estado_cambiado.emit()
            webbrowser.open(url)

    def _copiar_url(self) -> None:
        url = (self.db.get_job(self.uid) or {}).get("url", "")
        if url:
            QGuiApplication.clipboard().setText(url)
            self.lbl_status.setText("URL copiada al portapapeles ✓")

    def _descartar(self) -> None:
        self.db.mark_discarded(self.uid)
        self.estado_cambiado.emit()
        self.accept()

    def _cerrar(self) -> None:
        # Cierra sin descartar; solo asegura el estado "vista".
        self.db.mark_seen(self.uid)
        self.estado_cambiado.emit()
        self.accept()
