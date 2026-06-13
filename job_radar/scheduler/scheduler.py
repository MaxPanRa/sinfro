"""Scheduler con QTimer. Solo corre mientras la app está abierta.

- Grupo A: cada 20 min (o 1 min con el flag de desarrollo).
- Grupo B: chequeo cada minuto; dispara en ventanas 6:00-6:05 y 18:00-18:05,
  una vez por día (marca en DB vía ``runs``).
Al detener el monitoreo o cerrar la ventana, los timers se paran limpiamente.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject, QTimer

from ..config import GROUP_A_INTERVAL_MIN


class Scheduler(QObject):
    """Orquesta las corridas periódicas llamando a la ventana principal."""

    def __init__(self, window) -> None:  # window: MainWindow
        super().__init__(window)
        self.window = window
        self.db = window.db
        self._active = False

        # Timer del Grupo A.
        self.timer_a = QTimer(self)
        self.timer_a.timeout.connect(self._tick_a)
        # Timer de chequeo del Grupo B (cada minuto).
        self.timer_b = QTimer(self)
        self.timer_b.setInterval(60_000)
        self.timer_b.timeout.connect(self._tick_b)

    # -- Control --------------------------------------------------------------

    def _interval_a_ms(self) -> int:
        dev = self.db.get_setting("dev_fast_scheduler", "0") == "1"
        minutos = 1 if dev else GROUP_A_INTERVAL_MIN
        return minutos * 60_000

    def set_active(self, activo: bool) -> None:
        """Arranca o detiene los timers. La corrida inmediata la dispara la ventana."""
        self._active = activo
        if activo:
            self.timer_a.start(self._interval_a_ms())
            self.timer_b.start()
        else:
            self.stop()

    def stop(self) -> None:
        self.timer_a.stop()
        self.timer_b.stop()
        self._active = False

    # -- Ticks ----------------------------------------------------------------

    def _tick_a(self) -> None:
        if self._active:
            self.window.run_group_a()

    def _tick_b(self) -> None:
        if not self._active:
            return
        ahora = datetime.now()
        day_key = self._group_b_day_key(ahora)
        if not day_key:
            return
        if self.db.group_b_ran_today(day_key):
            return
        # Ejecuta Grupo B si la ventana lo implementa (Fase 6).
        if hasattr(self.window, "run_group_b"):
            self.window.run_group_b(day_key)

    def _group_b_start_hour(self) -> int:
        try:
            return int(self.db.get_setting("group_b_hour", "6")) % 12
        except ValueError:
            return 6

    def _group_b_day_key(self, ahora: datetime) -> str | None:
        hour = self._matching_group_b_hour(ahora, self._group_b_start_hour())
        if hour is None:
            return None
        return f"{ahora:%Y-%m-%d}:{hour:02d}"

    @staticmethod
    def _matching_group_b_hour(ahora: datetime, start_hour: int = 6) -> int | None:
        start_hour = start_hour % 12
        for hour in (start_hour, start_hour + 12):
            if ahora.hour == hour and 0 <= ahora.minute <= 5:
                return hour
        return None

    @staticmethod
    def _en_ventana_b(ahora: datetime, start_hour: int = 6) -> bool:
        return Scheduler._matching_group_b_hour(ahora, start_hour) is not None
