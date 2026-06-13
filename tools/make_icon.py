"""Genera el ícono de la app (radar) y lo guarda como .ico multi-resolución + .png.

Dibuja todo con QPainter (sin dependencias externas) y empaca un .ico con varias
resoluciones (16–256). Reproducible: vuelve a correrlo para regenerar el ícono.

    python tools/make_icon.py
"""

from __future__ import annotations

import math
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QBrush, QColor, QConicalGradient, QFont, QImage, QLinearGradient, QPainter,
    QPainterPath, QPen, QRadialGradient,
)
from PySide6.QtWidgets import QApplication  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "job_radar" / "assets"
SIZES = [16, 24, 32, 48, 64, 128, 256]

VERDE = QColor("#34d399")
VERDE_BRILLO = QColor("#6ee7b7")
BLIP = QColor("#fde047")


def render_icon(size: int) -> QImage:
    """Dibuja el ícono del radar a la resolución ``size``."""
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)

    s = size
    margin = s * 0.04
    rect = QRectF(margin, margin, s - 2 * margin, s - 2 * margin)
    radius = s * 0.22

    # Fondo: rectángulo redondeado con degradado azul profundo.
    bg = QLinearGradient(0, 0, 0, s)
    bg.setColorAt(0.0, QColor("#163a66"))
    bg.setColorAt(1.0, QColor("#0b2545"))
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    p.fillPath(path, QBrush(bg))
    p.setClipPath(path)

    cx, cy = s / 2.0, s / 2.0
    R = s * 0.36  # radio del radar
    center = QPointF(cx, cy)

    # Barrido del radar: degradado cónico verde que se desvanece.
    sweep = QConicalGradient(center, 90)
    sweep.setColorAt(0.00, QColor(52, 211, 153, 200))
    sweep.setColorAt(0.18, QColor(52, 211, 153, 40))
    sweep.setColorAt(0.40, QColor(52, 211, 153, 0))
    sweep.setColorAt(1.00, QColor(52, 211, 153, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(sweep))
    p.drawEllipse(center, R, R)

    # Globo "sin fronteras": círculo exterior + meridianos y paralelos.
    pen = QPen(QColor(52, 211, 153, 150))
    pen.setWidthF(max(1.0, s * 0.009))
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(center, R, R)  # contorno del globo

    pen_g = QPen(QColor(52, 211, 153, 90))
    pen_g.setWidthF(max(1.0, s * 0.006))
    p.setPen(pen_g)
    # Meridianos (elipses verticales de ancho variable) + eje central.
    for wf in (0.42, 0.78):
        p.drawEllipse(center, R * wf, R)
    p.drawLine(QPointF(cx, cy - R), QPointF(cx, cy + R))
    # Paralelos (elipses horizontales) + ecuador.
    for hf in (0.42, 0.78):
        p.drawEllipse(center, R, R * hf)
    p.drawLine(QPointF(cx - R, cy), QPointF(cx + R, cy))

    # Línea del barrido (radio brillante).
    ang = math.radians(-40)
    end = QPointF(cx + R * math.cos(ang), cy + R * math.sin(ang))
    penl = QPen(VERDE_BRILLO)
    penl.setWidthF(max(1.2, s * 0.012))
    penl.setCapStyle(Qt.RoundCap)
    p.setPen(penl)
    p.drawLine(center, end)

    # Blip (vacante detectada): punto brillante con halo.
    bang = math.radians(-95)
    br = R * 0.62
    bp = QPointF(cx + br * math.cos(bang), cy + br * math.sin(bang))
    halo = QRadialGradient(bp, s * 0.06)
    halo.setColorAt(0.0, QColor(253, 224, 71, 230))
    halo.setColorAt(1.0, QColor(253, 224, 71, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(halo))
    p.drawEllipse(bp, s * 0.06, s * 0.06)
    p.setBrush(BLIP)
    p.drawEllipse(bp, max(1.5, s * 0.022), max(1.5, s * 0.022))

    # Punto central.
    p.setBrush(VERDE_BRILLO)
    p.drawEllipse(center, max(1.0, s * 0.016), max(1.0, s * 0.016))

    p.end()
    return img


def png_bytes(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def build_ico(images: list[tuple[int, bytes]]) -> bytes:
    """Empaca varios PNG en un archivo .ico."""
    count = len(images)
    out = struct.pack("<HHH", 0, 1, count)
    offset = 6 + count * 16
    blobs = b""
    for size, data in images:
        wh = 0 if size >= 256 else size
        out += struct.pack("<BBBBHHII", wh, wh, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return out + blobs


def main() -> int:
    QApplication(sys.argv)
    ASSETS.mkdir(parents=True, exist_ok=True)
    pngs = [(sz, png_bytes(render_icon(sz))) for sz in SIZES]
    (ASSETS / "icon.ico").write_bytes(build_ico(pngs))
    render_icon(256).save(str(ASSETS / "icon.png"), "PNG")
    print(f"Ícono generado en {ASSETS} (.ico {len(SIZES)} tamaños + .png 256).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
