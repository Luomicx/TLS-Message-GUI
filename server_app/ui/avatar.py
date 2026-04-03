from __future__ import annotations

import hashlib

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QPixmap


def pixmap_from_avatar_blob(blob: bytes) -> QPixmap:
    pm = QPixmap()
    pm.loadFromData(blob)
    if pm.isNull():
        return pm
    return pm.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def make_placeholder_avatar(seed: str) -> QPixmap:
    h = hashlib.md5(seed.encode("utf-8"), usedforsecurity=False).digest()
    color = QColor(120 + h[0] % 100, 120 + h[1] % 100, 120 + h[2] % 100)

    pm = QPixmap(48, 48)
    pm.fill(Qt.transparent)

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(color)
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(0, 0, 48, 48, 10, 10)

    ch = (seed.strip()[:1] or "?").upper()
    painter.setPen(Qt.white)
    font = painter.font()
    font.setBold(True)
    font.setPointSize(16)
    painter.setFont(font)
    painter.drawText(pm.rect(), Qt.AlignCenter, ch)
    painter.end()

    return pm
