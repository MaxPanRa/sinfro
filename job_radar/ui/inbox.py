"""Columna derecha: bandeja de vacantes estilo correo."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from ..db.database import Database

#: Filtros disponibles (texto → clave interna de ``list_jobs``).
FILTROS = [("Todas", "todas"), ("No vistas", "no_vistas"),
           ("Aplicadas", "aplicadas"), ("Descartadas", "descartadas")]


class JobRow(QWidget):
    """Fila visual de una vacante (título, empresa, fuente, score, badges)."""

    def __init__(self, job: dict) -> None:
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 6, 8, 6)
        v.setSpacing(2)

        no_vista = not job.get("seen")
        # Línea 1: título + score.
        l1 = QHBoxLayout()
        titulo = QLabel(job.get("title", "")[:90])
        f = QFont()
        f.setBold(no_vista)  # no vista = negrita (como correo no leído)
        f.setPointSize(11)
        titulo.setFont(f)
        l1.addWidget(titulo, 1)
        score = job.get("quick_score")
        score_txt = f"{score}" if score is not None else "…"
        lbl_score = QLabel(score_txt)
        lbl_score.setFixedWidth(36)
        lbl_score.setAlignment(Qt.AlignCenter)
        lbl_score.setStyleSheet(
            f"background:{self._score_color(score)};color:white;border-radius:8px;"
            "font-weight:bold;padding:2px;"
        )
        l1.addWidget(lbl_score)
        v.addLayout(l1)

        # Línea 2: empresa · fuente · modalidad + badges de estado.
        meta = " · ".join(filter(None, [
            job.get("company", ""), job.get("source", ""), job.get("modality", "")
        ]))
        l2 = QHBoxLayout()
        lbl_meta = QLabel(meta[:110])
        lbl_meta.setStyleSheet("color:#7f8c8d;font-size:11px;")
        l2.addWidget(lbl_meta, 1)
        for badge, color in self._badges(job):
            b = QLabel(badge)
            b.setStyleSheet(
                f"background:{color};color:white;border-radius:6px;"
                "padding:1px 6px;font-size:10px;"
            )
            l2.addWidget(b)
        v.addLayout(l2)

    @staticmethod
    def _score_color(score: int | None) -> str:
        if score is None:
            return "#95a5a6"
        if score >= 75:
            return "#27ae60"
        if score >= 50:
            return "#f39c12"
        return "#c0392b"

    @staticmethod
    def _badges(job: dict) -> list[tuple[str, str]]:
        out = []
        if job.get("applied"):
            out.append(("✓ Aplicada", "#2980b9"))
        if job.get("discarded"):
            out.append(("Descartada", "#7f8c8d"))
        return out


class Inbox(QWidget):
    """Bandeja con filtros y lista de vacantes."""

    job_opened = Signal(str)  # uid

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self._filtro = "todas"
        self._mostrar_repetidas = False
        self._build()
        self.refresh()

    def _build(self) -> None:
        v = QVBoxLayout(self)
        # Barra de filtros.
        barra = QHBoxLayout()
        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)
        for i, (texto, clave) in enumerate(FILTROS):
            b = QPushButton(texto)
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.clicked.connect(lambda _=False, c=clave: self._set_filtro(c))
            self._grupo.addButton(b)
            barra.addWidget(b)
        barra.addStretch(1)
        self.lbl_count = QLabel("0 vacantes")
        self.lbl_count.setStyleSheet("color:gray;")
        barra.addWidget(self.lbl_count)
        v.addLayout(barra)

        self.lista = QListWidget()
        self.lista.setAlternatingRowColors(True)
        self.lista.itemClicked.connect(self._on_click)
        v.addWidget(self.lista)

    def set_mostrar_repetidas(self, valor: bool) -> None:
        self._mostrar_repetidas = valor
        self.refresh()

    def _set_filtro(self, clave: str) -> None:
        self._filtro = clave
        self.refresh()

    def refresh(self) -> None:
        self.lista.clear()
        jobs = self.db.list_jobs(
            filtro=self._filtro, show_duplicates=self._mostrar_repetidas
        )
        for job in jobs:
            item = QListWidgetItem(self.lista)
            row = JobRow(job)
            item.setData(Qt.UserRole, job["uid"])
            item.setSizeHint(row.sizeHint())
            self.lista.addItem(item)
            self.lista.setItemWidget(item, row)
        self.lbl_count.setText(f"{len(jobs)} vacantes")

    def _on_click(self, item: QListWidgetItem) -> None:
        uid = item.data(Qt.UserRole)
        if uid:
            self.db.mark_seen(uid)
            self.refresh()
            self.job_opened.emit(uid)
