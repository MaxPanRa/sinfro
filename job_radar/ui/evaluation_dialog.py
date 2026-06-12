"""Popup modal de evaluación profunda de una vacante."""

from __future__ import annotations

import webbrowser
from datetime import datetime

from PySide6.QtCore import QThreadPool, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from ..db.database import Database
from ..service import AppService
from .workers import Worker


class EvaluationDialog(QDialog):
    """Diálogo amplio y scrolleable con la evaluación en Markdown."""

    estado_cambiado = Signal()  # avisa a la bandeja para refrescar

    def __init__(self, db: Database, service: AppService, pool: QThreadPool,
                 uid: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.service = service
        self.pool = pool
        self.uid = uid
        self.job = db.get_job(uid) or {}
        self.setWindowTitle("Evaluación de vacante")
        self.resize(720, 760)
        self._build()
        self._cargar_evaluacion(force=False)

    def _build(self) -> None:
        v = QVBoxLayout(self)

        # Encabezado con datos básicos.
        titulo = QLabel(f"<b>{self.job.get('title','')}</b>")
        titulo.setWordWrap(True)
        titulo.setStyleSheet("font-size:15px;")
        v.addWidget(titulo)
        meta = " · ".join(filter(None, [
            self.job.get("company", ""), self.job.get("source", ""),
            self.job.get("modality", ""), self.job.get("location", ""),
        ]))
        lbl_meta = QLabel(meta)
        lbl_meta.setStyleSheet("color:#7f8c8d;")
        lbl_meta.setWordWrap(True)
        v.addWidget(lbl_meta)

        # Visor de Markdown.
        self.viewer = QTextBrowser()
        self.viewer.setOpenExternalLinks(True)
        v.addWidget(self.viewer, 1)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:gray;font-size:11px;")
        v.addWidget(self.lbl_status)

        # Botonera.
        botones = QHBoxLayout()
        self.btn_aplicar = QPushButton("Aplicar")
        self.btn_aplicar.clicked.connect(self._aplicar)
        self.btn_regenerar = QPushButton("Regenerar evaluación")
        self.btn_regenerar.clicked.connect(lambda: self._cargar_evaluacion(force=True))
        btn_ir = QPushButton("Ir al sitio")
        btn_ir.clicked.connect(self._ir_al_sitio)
        btn_copiar = QPushButton("Copiar URL")
        btn_copiar.clicked.connect(self._copiar_url)
        self.btn_descartar = QPushButton("Descartar")
        self.btn_descartar.clicked.connect(self._descartar)
        for b in (self.btn_aplicar, self.btn_regenerar, btn_ir, btn_copiar, self.btn_descartar):
            botones.addWidget(b)
        v.addLayout(botones)

        self._sync_aplicar()

    # -- Evaluación -----------------------------------------------------------

    def _cargar_evaluacion(self, force: bool) -> None:
        cached = None if force else self.db.get_evaluation(self.uid)
        if cached:
            self.viewer.setMarkdown(cached["markdown"])
            self.lbl_status.setText(f"Evaluación cacheada ({cached.get('created_at','')[:16]}).")
            return
        # Generar en hilo de fondo.
        self.viewer.setMarkdown("_Generando evaluación profunda con IA… espera._")
        self.lbl_status.setText("Llamando a OpenCode…")
        self.btn_regenerar.setEnabled(False)
        client = self.service.build_client()

        def tarea() -> str:
            return self.service.get_or_create_evaluation(client, self.uid, force=force)

        worker = Worker(tarea)
        worker.signals.result.connect(self._eval_lista)
        worker.signals.error.connect(self._eval_error)
        worker.signals.finished.connect(lambda: self.btn_regenerar.setEnabled(True))
        self.pool.start(worker)

    def _eval_lista(self, markdown: str) -> None:
        self.viewer.setMarkdown(markdown)
        self.lbl_status.setText("Evaluación generada y cacheada.")

    def _eval_error(self, msg: str) -> None:
        self.viewer.setMarkdown(
            f"### No se pudo generar la evaluación\n\n```\n{msg}\n```\n\n"
            "Revisa tu API key / saldo de OpenCode Go en Ajustes, o activa el "
            "modelo gratuito de respaldo."
        )
        self.lbl_status.setText("Error al generar la evaluación.")

    # -- Acciones -------------------------------------------------------------

    def _sync_aplicar(self) -> None:
        job = self.db.get_job(self.uid) or {}
        if job.get("applied"):
            fecha = (job.get("applied_at") or "")[:16].replace("T", " ")
            self.btn_aplicar.setEnabled(False)
            self.btn_aplicar.setText(f"Aplicada el {fecha}")

    def _aplicar(self) -> None:
        self.db.mark_applied(self.uid)
        self._sync_aplicar()
        self.estado_cambiado.emit()

    def _ir_al_sitio(self) -> None:
        url = (self.db.get_job(self.uid) or {}).get("url", "")
        if url:
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
