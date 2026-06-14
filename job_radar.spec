# -*- mode: python ; coding: utf-8 -*-
"""Spec de PyInstaller para Job Radar.

Estrategia: ONEDIR + windowed (sin consola). One-folder es más estable con
PySide6 que one-file (este último re-extrae Qt a un temporal en cada arranque,
causando inicios lentos y falsos positivos de antivirus). El resultado queda en
dist/JobRadar/JobRadar.exe.

Las dependencias con imports dinámicos (jobspy y sus libs, pdfplumber/pdfminer,
feedparser, python-docx) se recolectan con collect_all para que no falten en
tiempo de ejecución.
"""

import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

# El ícono .ico solo aplica en Windows; en macOS PyInstaller espera .icns.
APP_ICON = "job_radar/assets/icon.ico" if sys.platform == "win32" else None

datas, binaries, hiddenimports = [], [], []

# Recursos (ícono) empacados en la misma ruta relativa que en dev.
datas += [
    ("job_radar/assets/icon.ico", "job_radar/assets"),
    ("job_radar/assets/icon.png", "job_radar/assets"),
]

# jobspy se importa de forma diferida dentro de la fuente → recolectar todo.
for paquete in ("jobspy", "pdfplumber", "pdfminer", "feedparser", "docx", "pypdf"):
    try:
        d, b, h = collect_all(paquete)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

hiddenimports += collect_submodules("jobspy")

block_cipher = None

a = Analysis(
    ["run_job_radar.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "tests"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Sinfro",
    icon=APP_ICON,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # --windowed: app de escritorio, sin consola
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Sinfro",
)
