"""Tema visual global (QSS) de Job Radar.

Se aplica a toda la QApplication. Los estilos inline de widgets concretos
(caja de %, botón de monitoreo, chips) tienen prioridad y no se ven afectados.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

QSS = """
* { font-family: 'Segoe UI', 'Inter', sans-serif; }
QWidget { font-size: 12px; color: #1f2933; }

QMainWindow, QDialog { background: #eef1f5; }

/* --- Menú superior --- */
QMenuBar { background: #ffffff; border-bottom: 1px solid #e1e4e8; padding: 2px; }
QMenuBar::item { padding: 5px 12px; border-radius: 5px; }
QMenuBar::item:selected { background: #e8eef7; color: #1d4ed8; }
QMenu { background: #ffffff; border: 1px solid #e1e4e8; padding: 4px; }
QMenu::item { padding: 6px 22px; border-radius: 4px; }
QMenu::item:selected { background: #e8eef7; color: #1d4ed8; }

/* --- Cajas agrupadas --- */
QGroupBox {
    background: #ffffff; border: 1px solid #e1e4e8; border-radius: 9px;
    margin-top: 14px; padding: 10px 8px 8px 8px; font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 10px; padding: 0 5px; color: #334155;
}

/* --- Campos de texto / combos --- */
QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {
    background: #ffffff; border: 1px solid #cbd2d9; border-radius: 6px;
    padding: 5px 7px; selection-background-color: #2563eb;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
    border: 1px solid #2563eb;
}
QComboBox::drop-down { border: none; width: 20px; }

/* --- Botones --- */
QPushButton {
    background: #ffffff; border: 1px solid #cbd2d9; border-radius: 6px;
    padding: 6px 12px; color: #1f2933; font-weight: 600;
}
QPushButton:hover { background: #f1f5f9; border-color: #94a3b8; }
QPushButton:pressed { background: #e2e8f0; }
QPushButton:disabled { color: #9aa5b1; background: #f1f3f5; border-color: #e1e4e8; }
QPushButton:checked { background: #2563eb; color: #ffffff; border-color: #1d4ed8; }

/* --- Checkboxes --- */
QCheckBox { spacing: 6px; }

/* --- Bandeja --- */
QListWidget#InboxList {
    background: #ffffff; border: 1px solid #e1e4e8; border-radius: 9px; padding: 2px;
}
QListWidget#InboxList::item { border-bottom: 1px solid #f0f2f5; }
QListWidget#InboxList::item:selected { background: transparent; }
QListWidget#InboxList::item:hover { background: #f7f9fc; }

/* --- Otras listas (tecnologías, etc.) --- */
QListWidget { background: #ffffff; border: 1px solid #cbd2d9; border-radius: 6px; }
QListWidget::item:selected { background: #e8eef7; color: #1d4ed8; }

/* --- Barras de scroll --- */
QScrollBar:vertical { background: transparent; width: 11px; margin: 2px; }
QScrollBar::handle:vertical { background: #cbd2d9; border-radius: 5px; min-height: 26px; }
QScrollBar::handle:vertical:hover { background: #9aa5b1; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 11px; margin: 2px; }
QScrollBar::handle:horizontal { background: #cbd2d9; border-radius: 5px; min-width: 26px; }

/* --- Barra de estado --- */
QStatusBar { background: #eef1f5; color: #52606d; }
QStatusBar::item { border: none; }
"""


def apply_theme(app: QApplication) -> None:
    """Aplica el tema global a la aplicación."""
    app.setStyleSheet(QSS)
