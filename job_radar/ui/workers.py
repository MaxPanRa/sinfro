"""Workers de QThreadPool. Toda llamada de red/IA corre aquí, NUNCA en la UI.

Patrón: cada worker es un ``QRunnable`` con un objeto ``WorkerSignals`` que emite
``result``/``error``/``finished``. La UI conecta esas señales para actualizarse.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    """Señales emitidas por un :class:`Worker`."""

    result = Signal(object)      # payload de éxito
    error = Signal(str)          # mensaje de error legible
    finished = Signal()          # siempre al final
    progress = Signal(str)       # texto de progreso opcional


class Worker(QRunnable):
    """Ejecuta ``fn(*args, **kwargs)`` en un hilo del pool y emite el resultado."""

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:  # noqa: D401 — método requerido por QRunnable
        try:
            resultado = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # noqa: BLE001 — reportar a la UI, no crashear
            self.signals.error.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.signals.result.emit(resultado)
        finally:
            self.signals.finished.emit()
