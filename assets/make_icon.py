"""Génère assets/youstrow.ico et youstrow.png (rendu Qt, sans dépendance supplémentaire)."""
import sys
from pathlib import Path
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QRadialGradient

app = QGuiApplication(sys.argv)
here = Path(__file__).parent
for size in (256,):
    img = QImage(size, size, QImage.Format_ARGB32); img.fill(Qt.transparent)
    p = QPainter(img); p.setRenderHint(QPainter.Antialiasing)
    r = QRectF(8, 8, size - 16, size - 16)
    g = QLinearGradient(0, 0, size, size); g.setColorAt(0, QColor("#141824")); g.setColorAt(1, QColor("#05060a"))
    path = QPainterPath(); path.addRoundedRect(r, 52, 52); p.fillPath(path, g)
    for i, col in enumerate(("#19d3ff", "#ffd60a", "#ff4d6a")):          # trois faisceaux
        glow = QRadialGradient(QPointF(64 + i * 64, 70), 70); c = QColor(col); c.setAlpha(170); glow.setColorAt(0, c); c.setAlpha(0); glow.setColorAt(1, c)
        p.setPen(Qt.NoPen); p.setBrush(glow); p.drawEllipse(QPointF(64 + i * 64, 70), 70, 70)
    f = QFont("Segoe UI", 1); f.setPixelSize(112); f.setBold(True); p.setFont(f); p.setPen(QColor("#f5f7fa"))
    p.drawText(QRectF(0, 96, size, 130), Qt.AlignCenter, "YS")
    p.end()
img.save(str(here / "youstrow.png")); img.save(str(here / "youstrow.ico"))
print("ok", (here / "youstrow.ico").stat().st_size)
