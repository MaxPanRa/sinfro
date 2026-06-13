"""Columna derecha: bandeja de vacantes estilo correo (compacta)."""

from __future__ import annotations

import json
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from ..db.database import Database
from ..service import AppService

FILTROS = [("Todas", "todas"), ("No vistas", "no_vistas"),
           ("Aplicadas", "aplicadas"), ("Descartadas", "descartadas")]

# --- Paleta de estados (fondo de la fila) ------------------------------------
COLOR_APLICADA_BG = "#d7f3df"      # verde claro: aplicada
COLOR_APLICADA_BORDE = "#27ae60"
COLOR_DESCARTADA_BG = "#fcdcdc"    # rojo claro: descartada (sigue visible)
COLOR_DESCARTADA_BORDE = "#c0392b"
COLOR_VISTA_BG = "#fdf3c7"         # amarillo claro: vista / analizada
COLOR_VISTA_BORDE = "#f1c40f"

# --- Paleta de la caja de porcentaje -----------------------------------------
SCORE_VERDE = "#16a34a"
SCORE_AMARILLO = "#eab308"
SCORE_NARANJA = "#f97316"
SCORE_ROJO = "#dc2626"
SCORE_PRELIM_BG = "#e5e7eb"        # gris claro: preliminar
SCORE_PRELIM_FG = "#4b5563"        # gris oscuro

_COMP_PREFIX_RE = re.compile(r"^\s*COMP\s+(?:PRELIM|IA)\s+\d+%\s*-?\s*", re.IGNORECASE)


def score_color(score: int, threshold: int) -> str:
    """Color de la caja según la distancia al umbral deseado por el usuario."""
    if score >= threshold:
        return SCORE_VERDE
    if score >= threshold - 20:
        return SCORE_AMARILLO
    if score >= threshold - 40:
        return SCORE_NARANJA
    return SCORE_ROJO


class JobRow(QWidget):
    """Fila visual compacta: contenido a la izquierda, caja de % a altura completa."""

    def __init__(self, job: dict, threshold: int) -> None:
        super().__init__()
        self.setObjectName("JobRow")
        self.setStyleSheet(self._row_style(job))

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Columna de contenido (izquierda) ---
        izq = QWidget()
        v = QVBoxLayout(izq)
        v.setContentsMargins(11, 6, 8, 6)
        v.setSpacing(1)

        no_vista = not job.get("seen")
        titulo = QLabel(job.get("title", "")[:120])
        titulo.setWordWrap(True)
        f = QFont()
        f.setBold(no_vista)
        f.setPointSize(10)
        titulo.setFont(f)
        titulo.setStyleSheet("color:#1f2933;")
        v.addWidget(titulo)

        meta = " · ".join(filter(None, [
            job.get("company", ""), job.get("source", ""), job.get("modality", ""),
            job.get("location", ""),
        ]))
        lbl_meta = QLabel(meta[:160])
        lbl_meta.setStyleSheet("color:#7f8c8d;font-size:10px;")
        v.addWidget(lbl_meta)

        # Línea de estado/skills + badges sutiles.
        fila3 = QHBoxLayout()
        fila3.setSpacing(5)
        resumen = self._summary(job)
        if resumen:
            lbl_summary = QLabel(resumen[:150])
            lbl_summary.setWordWrap(True)
            lbl_summary.setStyleSheet("color:#52606d;font-size:10px;")
            fila3.addWidget(lbl_summary, 1)
        else:
            fila3.addStretch(1)
        for texto, bg, fg in self._badges(job):
            b = QLabel(texto)
            b.setStyleSheet(
                f"background:{bg};color:{fg};border-radius:5px;"
                "padding:0px 6px;font-size:9px;font-weight:bold;"
            )
            fila3.addWidget(b)
        v.addLayout(fila3)

        root.addWidget(izq, 1)

        # --- Caja de porcentaje (derecha, altura completa) ---
        root.addWidget(self._score_box(job, threshold))

    # -- Caja de porcentaje ---------------------------------------------------

    @staticmethod
    def _score_box(job: dict, threshold: int) -> QLabel:
        score = job.get("quick_score")
        data = JobRow._classification(job)
        analizado = str(data.get("source", "")).startswith("ai_")

        box = QLabel()
        box.setAlignment(Qt.AlignCenter)
        box.setFixedWidth(58)
        box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        f = QFont()
        f.setBold(True)
        f.setPointSize(11)
        box.setFont(f)

        if score is None:
            box.setText("¿\n?\n?")
            box.setStyleSheet(
                f"background:{SCORE_PRELIM_BG};color:{SCORE_PRELIM_FG};")
            return box

        if analizado:
            # Analizado por IA: caja sólida coloreada según umbral.
            color = score_color(int(score), threshold)
            fg = "#3f3f00" if color == SCORE_AMARILLO else "white"
            box.setText(f"{score}%")
            box.setStyleSheet(f"background:{color};color:{fg};")
        else:
            # Preliminar (precalculado): gris con signos de interrogación.
            box.setText(f"¿\n{score}%\n?")
            box.setStyleSheet(
                f"background:{SCORE_PRELIM_BG};color:{SCORE_PRELIM_FG};")
        return box

    # -- Estilos / helpers ----------------------------------------------------

    @staticmethod
    def _row_style(job: dict) -> str:
        base = "#JobRow{{background:{bg};border-left:4px solid {borde};}}"
        if job.get("applied"):
            return base.format(bg=COLOR_APLICADA_BG, borde=COLOR_APLICADA_BORDE)
        if job.get("discarded"):
            return base.format(bg=COLOR_DESCARTADA_BG, borde=COLOR_DESCARTADA_BORDE)
        if job.get("seen"):
            return base.format(bg=COLOR_VISTA_BG, borde=COLOR_VISTA_BORDE)
        return "#JobRow{background:#ffffff;border-left:4px solid transparent;}"

    @staticmethod
    def _summary(job: dict) -> str:
        data = JobRow._classification(job)
        resumen = str(data.get("resumen_una_linea", "")).strip()
        # Quita el prefijo redundante "COMP PRELIM NN% -" / "COMP IA NN% -".
        return _COMP_PREFIX_RE.sub("", resumen).strip()

    @staticmethod
    def _badges(job: dict) -> list[tuple[str, str, str]]:
        out: list[tuple[str, str, str]] = []
        if job.get("applied"):
            out.append(("✓ Aplicada", COLOR_APLICADA_BORDE, "white"))
        if job.get("discarded"):
            out.append(("✕ Descartada", COLOR_DESCARTADA_BORDE, "white"))
        if job.get("visited_site") and not job.get("applied"):
            out.append(("Visitada", "#b7791f", "white"))
        return out

    @staticmethod
    def _classification(job: dict) -> dict:
        raw = job.get("classification_json")
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}


class Inbox(QWidget):
    """Bandeja con filtros, leyenda de colores y lista de vacantes."""

    job_opened = Signal(str)  # uid

    def __init__(
        self,
        db: Database,
        service: AppService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.service = service
        self._filtro = "todas"
        self._mostrar_repetidas = False
        self._build()
        self.refresh()

    def _build(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(5)

        # Barra de filtros.
        barra = QHBoxLayout()
        barra.setSpacing(4)
        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)
        for i, (texto, clave) in enumerate(FILTROS):
            b = QPushButton(texto)
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=clave: self._set_filtro(c))
            self._grupo.addButton(b)
            barra.addWidget(b)
        barra.addStretch(1)
        self.lbl_count = QLabel("0 vacantes")
        self.lbl_count.setStyleSheet("color:#7f8c8d;")
        barra.addWidget(self.lbl_count)
        v.addLayout(barra)

        # Leyenda de colores.
        v.addWidget(self._build_legend())

        self.lista = QListWidget()
        self.lista.setObjectName("InboxList")
        self.lista.setAlternatingRowColors(False)
        self.lista.setSpacing(2)
        self.lista.setUniformItemSizes(False)
        self.lista.itemClicked.connect(self._on_click)
        v.addWidget(self.lista, 1)

    def _build_legend(self) -> QWidget:
        """Leyenda explicando el significado de cada color."""
        cont = QWidget()
        h = QHBoxLayout(cont)
        h.setContentsMargins(2, 0, 2, 0)
        h.setSpacing(10)

        def chip(color: str, texto: str, fg: str = "white") -> QWidget:
            w = QWidget()
            hh = QHBoxLayout(w)
            hh.setContentsMargins(0, 0, 0, 0)
            hh.setSpacing(4)
            cuadro = QLabel(" ")
            cuadro.setFixedSize(13, 13)
            cuadro.setStyleSheet(
                f"background:{color};border:1px solid #00000022;border-radius:3px;")
            etiqueta = QLabel(texto)
            etiqueta.setStyleSheet("color:#52606d;font-size:10px;")
            hh.addWidget(cuadro)
            hh.addWidget(etiqueta)
            return w

        leyenda = QLabel("Filas:")
        leyenda.setStyleSheet("color:#52606d;font-size:10px;font-weight:bold;")
        h.addWidget(leyenda)
        h.addWidget(chip(COLOR_APLICADA_BG, "Aplicada"))
        h.addWidget(chip(COLOR_VISTA_BG, "Vista/analizada"))
        h.addWidget(chip(COLOR_DESCARTADA_BG, "Descartada"))
        sep = QLabel("│ %:")
        sep.setStyleSheet("color:#9aa5b1;font-size:10px;font-weight:bold;")
        h.addWidget(sep)
        h.addWidget(chip(SCORE_PRELIM_BG, "¿?=preliminar", SCORE_PRELIM_FG))
        h.addWidget(chip(SCORE_VERDE, "cumple"))
        h.addWidget(chip(SCORE_AMARILLO, "-20"))
        h.addWidget(chip(SCORE_NARANJA, "-40"))
        h.addWidget(chip(SCORE_ROJO, "bajo"))
        h.addStretch(1)
        return cont

    def set_mostrar_repetidas(self, valor: bool) -> None:
        self._mostrar_repetidas = valor
        self.refresh()

    def _set_filtro(self, clave: str) -> None:
        self._filtro = clave
        self.refresh()

    def refresh(self) -> None:
        self.lista.clear()
        threshold = self.service.compatibility_threshold() if self.service else 70
        jobs = self.db.list_jobs(
            filtro=self._filtro, show_duplicates=self._mostrar_repetidas
        )
        if self.service is not None:
            jobs = [job for job in jobs if self.service.location_match(job)]
        for job in jobs:
            item = QListWidgetItem(self.lista)
            row = JobRow(job, threshold)
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
