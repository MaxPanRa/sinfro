"""Lanzador de Job Radar para ejecución directa y para PyInstaller.

Uso en desarrollo:  python run_job_radar.py
PyInstaller usa este archivo como script de entrada (ver job_radar.spec).
"""

from __future__ import annotations

import sys

from job_radar.main import main

if __name__ == "__main__":
    sys.exit(main())
