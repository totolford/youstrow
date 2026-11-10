"""DMX Monitor (lecture seule) et DMX Tester (faders directs)."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSpinBox,
                               QVBoxLayout, QWidget)

from ..controller import AppController
from . import theme as T
from .widgets import Fader


class _Grid(QWidget):
    COLS = 32

    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl, self.uni, self.hover = ctl, 0, -1
        self.setMinimumHeight(300); self.setMouseTracking(True)

    def _cell(self):
        return self.width() / self.COLS, self.height() / (512 // self.COLS)

    def mouseMoveEvent(self, e):
        cw, ch = self._cell()
        self.hover = int(e.position().y() // ch) * self.COLS + int(e.position().x() // cw)
        self.update()

    def leaveEvent(self, _): self.hover = -1; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        data = self.ctl.console.universes[self.uni].snapshot()
        cw, ch = self._cell()
        f = QFont(self.font()); f.setPointSize(7); p.setFont(f)
        for i, v in enumerate(data):
            x, y = (i % self.COLS) * cw, (i // self.COLS) * ch
            r = QRectF(x + 1, y + 1, cw - 2, ch - 2)
            col = QColor(T.RAISED) if v == 0 else QColor(T.ACCENT).darker(int(400 - 300 * v / 255))
            p.setPen(Qt.NoPen); p.setBrush(col); p.drawRoundedRect(r, 3, 3)
            if i == self.hover:
                p.setPen(QColor(T.BRAND)); p.setBrush(Qt.NoBrush); p.drawRoundedRect(r, 3, 3)
            p.setPen(QColor(T.TEXT if v else "#3a4252"))
            p.drawText(r, Qt.AlignCenter, str(v))


class DmxMonitor(QWidget):
    def __init__(self, ctl: AppController, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        lay = QVBoxLayout(self); lay.setContentsMargins(14, 14, 14, 14); lay.setSpacing(8)
        top = QHBoxLayout()
        t = QLabel("MONITEUR DMX — valeurs émises (lecture seule)"); t.setObjectName("section"); top.addWidget(t); top.addStretch(1)
        self.uni = QComboBox(); [self.uni.addItem(f"Univers {i + 1}", i) for i in range(4)]; top.addWidget(self.uni)
        lay.addLayout(top)
        self.grid = _Grid(ctl); lay.addWidget(self.grid, 1)
        self.info = QLabel(" "); self.info.setObjectName("muted"); lay.addWidget(self.info)
        self.uni.currentIndexChanged.connect(lambda: setattr(self.grid, "uni", self.uni.currentData()))
        t = QTimer(self); t.setInterval(50); t.timeout.connect(self._tick); t.start()

    def _tick(self):
        if not self.isVisible():
            return
        self.grid.update()
        h, u = self.grid.hover, self.grid.uni
        if h >= 0:
            owner = next((f for f in self.ctl.console.patch.fixtures if f.universe == u and f.address <= h + 1 <= f.end_address), None)
            who = f" — {owner.name} ({owner.channels[h + 1 - owner.address]})" if owner else ""
            self.info.setText(f"Canal {h + 1} = {self.ctl.console.universes[u].get(h + 1)}{who}")
        else:
            self.info.setText(" ")


class DmxTester(QWidget):
    PER_PAGE = 24

    def __init__(self, ctl: AppController, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.page = 0
        lay = QVBoxLayout(self); lay.setContentsMargins(14, 14, 14, 14); lay.setSpacing(10)
        top = QHBoxLayout()
        t = QLabel("TESTEUR DMX — faders directs"); t.setObjectName("section"); top.addWidget(t); top.addStretch(1)
        self.enable = QCheckBox("Activer le testeur (masque le show)"); top.addWidget(self.enable)
        self.uni = QComboBox(); [self.uni.addItem(f"Univers {i + 1}", i) for i in range(4)]; top.addWidget(self.uni)
        lay.addLayout(top)
        warn = QLabel("Écrit directement sur les canaux DMX : le rendu du show est suspendu tant que le testeur est activé.")
        warn.setObjectName("muted"); lay.addWidget(warn)
        self.row = QHBoxLayout(); self.row.setSpacing(2)
        holder = QWidget(); holder.setLayout(self.row); lay.addWidget(holder, 1)
        self.faders: list[Fader] = []
        for i in range(self.PER_PAGE):
            f = Fader("", T.ACCENT); f.valueChanged.connect(lambda v, i=i: self._moved(i, v)); self.faders.append(f); self.row.addWidget(f)
        nav = QHBoxLayout()
        self.prev, self.next = QPushButton("◀"), QPushButton("▶")
        self.lbl = QLabel(""); self.lbl.setAlignment(Qt.AlignCenter)
        self.zero = QPushButton("Tout à 0"); self.full = QPushButton("Page à 100 %")
        nav.addWidget(self.zero); nav.addWidget(self.full); nav.addStretch(1); nav.addWidget(self.prev); nav.addWidget(self.lbl); nav.addWidget(self.next)
        lay.addLayout(nav)
        self.enable.toggled.connect(self._toggle)
        self.uni.currentIndexChanged.connect(self._refresh)
        self.prev.clicked.connect(lambda: self._goto(self.page - 1)); self.next.clicked.connect(lambda: self._goto(self.page + 1))
        self.zero.clicked.connect(self._all_zero); self.full.clicked.connect(self._page_full)
        self._refresh()

    def _goto(self, p):
        self.page = min(max(p, 0), 512 // self.PER_PAGE); self._refresh()

    def _base(self): return self.page * self.PER_PAGE + 1

    def _refresh(self):
        u = self.uni.currentData()
        for i, f in enumerate(self.faders):
            ch = self._base() + i
            f.setVisible(ch <= 512); f.label = str(ch)
            f.setValue(self.ctl.console.direct.get((u, ch), 0) / 255)
        last = min(512, self._base() + self.PER_PAGE - 1)
        self.lbl.setText(f"  Canaux {self._base()}–{last}  ")

    def _toggle(self, on):
        self.ctl.console.tester_active = on
        if not on: self.ctl.console.release_direct()
        self.ctl.log("warn" if on else "info", "DMX Tester " + ("activé : show suspendu." if on else "désactivé."))
        self._refresh()

    def _moved(self, i, v):
        if not self.enable.isChecked():
            self.enable.setChecked(True)
        self.ctl.console.set_direct(self.uni.currentData(), self._base() + i, round(v * 255))

    def _all_zero(self):
        self.ctl.console.release_direct(); self._refresh()

    def _page_full(self):
        if not self.enable.isChecked(): self.enable.setChecked(True)
        for i in range(self.PER_PAGE):
            if self._base() + i <= 512: self.ctl.console.set_direct(self.uni.currentData(), self._base() + i, 255)
        self._refresh()
