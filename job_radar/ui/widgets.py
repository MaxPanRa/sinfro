"""Widgets reutilizables: FlowLayout (envuelve líneas) y Chip removible."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QLabel, QLayout, QLayoutItem, QPushButton, QSizePolicy, QWidget, QHBoxLayout,
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
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 4, 4)
        layout.setSpacing(4)
        label = QLabel(text)
        label.setStyleSheet("background: transparent;")
        boton = QPushButton("×")
        boton.setFixedSize(18, 18)
        boton.setCursor(Qt.PointingHandCursor)
        boton.setStyleSheet(
            "QPushButton{border:none;border-radius:9px;background:#c0392b;"
            "color:white;font-weight:bold;} QPushButton:hover{background:#e74c3c;}"
        )
        boton.clicked.connect(lambda: self.removed.emit(self._text))
        layout.addWidget(label)
        layout.addWidget(boton)
        self.setStyleSheet(
            "#Chip{background:#34495e;border-radius:12px;} QLabel{color:white;}"
        )
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
