"""Widgets reutilizables: FlowLayout (envuelve líneas) y Chip removible."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox, QLabel, QLayout, QLayoutItem, QPushButton, QSizePolicy, QWidget,
    QHBoxLayout,
)


class FlowLayout(QLayout):
    """Layout que acomoda los widgets en filas y los envuelve al llegar al borde."""

    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = 6) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802 — API Qt
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        x, y, line_height = rect.x(), rect.y(), 0
        spacing = self.spacing()
        for item in self._items:
            w = item.sizeHint().width()
            h = item.sizeHint().height()
            next_x = x + w + spacing
            if next_x - spacing > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + spacing
                next_x = x + w + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, h)
        return y + line_height - rect.y()


class Chip(QWidget):
    """Etiqueta con texto y botón × que emite ``removed`` con su texto."""

    removed = Signal(str)

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setObjectName("Chip")
        self.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 1, 4, 1)
        layout.setSpacing(4)
        label = QLabel(text)
        label.setStyleSheet("background:transparent;color:#1f2933;font-size:11px;")
        boton = QPushButton("✕")
        boton.setFixedSize(16, 16)
        boton.setCursor(Qt.PointingHandCursor)
        boton.setToolTip("Quitar")
        boton.setStyleSheet(
            "QPushButton{border:1px solid #475569;border-radius:8px;background:#ffffff;"
            "color:#334155;font-weight:bold;font-size:11px;padding:0;}"
            "QPushButton:hover{background:#ef4444;color:white;border-color:#ef4444;}"
        )
        boton.clicked.connect(lambda: self.removed.emit(self._text))
        layout.addWidget(label)
        layout.addWidget(boton)
        self.setStyleSheet(
            "#Chip{background:#eef2f7;border:1px solid #475569;border-radius:11px;}"
        )
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)


class SkillBadge(QWidget):
    """Badge de tecnología: "Nombre (nivel)" con la bolita del nivel más oscura.

    Amarillo = detectada del CV, naranja claro = manual. Un clic edita el nivel;
    doble clic la elimina. Emite los ids de la tecnología.
    """

    edit_requested = Signal(int)
    delete_requested = Signal(int)

    #: Paleta por origen: (fondo, borde, color de la bolita del nivel).
    _COLORS = {
        "cv": ("#fde68a", "#d4a017", "#b45309"),       # amarillo
        "manual": ("#fed7aa", "#f59e6a", "#c2410c"),   # naranja claro
    }

    def __init__(self, tech: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tech_id = int(tech["id"])
        self.setObjectName("SkillBadge")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Clic: editar nivel · Doble clic: eliminar")

        bg, borde, circ = self._COLORS.get(
            tech.get("origin", "manual"), self._COLORS["manual"])
        self.setStyleSheet(
            f"#SkillBadge{{background:{bg};border:1px solid {borde};border-radius:11px;}}")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(9, 1, 4, 1)
        lay.setSpacing(5)
        nombre = QLabel(str(tech["name"]))
        nombre.setStyleSheet(
            "background:transparent;color:#3f2d00;font-size:11px;font-weight:600;")
        bolita = QLabel(str(tech["level"]))
        bolita.setFixedSize(18, 18)
        bolita.setAlignment(Qt.AlignCenter)
        bolita.setStyleSheet(
            f"background:{circ};color:white;border-radius:9px;"
            "font-size:10px;font-weight:bold;")
        lay.addWidget(nombre)
        lay.addWidget(bolita)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # Distingue clic (editar) de doble clic (eliminar) con un temporizador.
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(220)
        self._click_timer.timeout.connect(
            lambda: self.edit_requested.emit(self.tech_id))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._click_timer.start()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self._click_timer.stop()
        self.delete_requested.emit(self.tech_id)


class CheckableComboBox(QComboBox):
    """Combo de selección múltiple con casillas; el popup no se cierra al elegir."""

    changed = Signal()

    def __init__(self, placeholder: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setModel(QStandardItemModel(self))
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setPlaceholderText(placeholder)
        self.lineEdit().installEventFilter(self)
        self.view().viewport().installEventFilter(self)

    def addItems(self, textos: list[str]) -> None:  # noqa: N802 — API Qt
        for t in textos:
            self.add_check_item(t)

    def add_check_item(self, texto: str, checked: bool = False) -> None:
        item = QStandardItem(texto)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
        item.setData(Qt.Checked if checked else Qt.Unchecked, Qt.CheckStateRole)
        self.model().appendRow(item)
        self._update_text()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self.lineEdit() and event.type() == QEvent.MouseButtonRelease:
            self.showPopup()
            return True
        if obj is self.view().viewport() and event.type() == QEvent.MouseButtonRelease:
            idx = self.view().indexAt(event.position().toPoint())
            item = self.model().itemFromIndex(idx)
            if item is not None:
                nuevo = Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
                item.setCheckState(nuevo)
                self._update_text()
                self.changed.emit()
            return True  # mantiene el popup abierto
        return super().eventFilter(obj, event)

    def checked_items(self) -> list[str]:
        m = self.model()
        return [m.item(i).text() for i in range(m.rowCount())
                if m.item(i).checkState() == Qt.Checked]

    def set_checked(self, textos: list[str]) -> None:
        objetivo = set(textos)
        m = self.model()
        for i in range(m.rowCount()):
            it = m.item(i)
            it.setCheckState(Qt.Checked if it.text() in objetivo else Qt.Unchecked)
        self._update_text()

    def _update_text(self) -> None:
        self.lineEdit().setText(", ".join(self.checked_items()))
