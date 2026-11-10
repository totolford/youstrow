"""Surface de pads (mémoires) : grille 8×8, REC, pages. Un pad = une mémoire enregistrée (voir engine/memories.py)."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from ..controller import AppController
from ..engine.memories import COLS, ROWS
from . import theme as T


class PadSurface(QWidget):
    pressed = Signal(int, int)
    cleared = Signal(int, int)
    rowPressed = Signal(int)

    def __init__(self, ctl: AppController, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMouseTracking(True)
        self.hover = None

    def hasHeightForWidth(self): return True
    def heightForWidth(self, w): return int(w * 0.98)

    def _cell(self) -> float:
        return (self.width() - 26) / COLS

    def _hit(self, pos):
        c = self._cell()
        return int(pos.y() // c), int(pos.x() // c)

    def mousePressEvent(self, e):
        r, c = self._hit(e.position())
        if 0 <= r < ROWS and 0 <= c < COLS:
            (self.cleared if e.button() == Qt.RightButton else self.pressed).emit(r, c)
        elif 0 <= r < ROWS and c >= COLS:
            self.rowPressed.emit(r)

    def mouseMoveEvent(self, e):
        r, c = self._hit(e.position()); h = (r, c) if 0 <= r < ROWS and 0 <= c < COLS else None
        if h != self.hover:
            self.hover = h; self.update()
            m = self.ctl.bank.get(self.ctl.page, *h) if h else None
            self.setToolTip(f"{m.name}" if m else "Pad vide — REC puis clic pour enregistrer")

    def leaveEvent(self, _):
        self.hover = None; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        cell = self._cell(); pad = cell - 5
        bank, page = self.ctl.bank, self.ctl.page
        for r in range(ROWS):
            for c in range(COLS):
                m = bank.get(page, r, c)
                on = m is not None and bank.active_row(page, c) == r
                rect = QRectF(c * cell + 2.5, r * cell + 2.5, pad, pad)
                if m is None:
                    base, fillc = QColor(T.RAISED), QColor(T.RAISED)
                else:
                    base = QColor(*m.color)
                    fillc = base if on else QColor(int(base.red() * .2 + 8), int(base.green() * .2 + 9), int(base.blue() * .2 + 12))
                if on:
                    glow = QColor(base); glow.setAlpha(95)
                    p.setPen(Qt.NoPen); p.setBrush(glow); p.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), 11, 11)
                g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
                g.setColorAt(0, fillc.lighter(125 if on else 112)); g.setColorAt(1, fillc)
                edge = QColor(255, 255, 255, 90 if on else (40 if self.hover == (r, c) else 14))
                p.setPen(QPen(edge, 1)); p.setBrush(g); p.drawRoundedRect(rect, 9, 9)
                if self.ctl.recording and m is None:      # en REC, les pads vides clignotent doucement
                    p.setPen(QPen(QColor(T.DANGER), 1, Qt.DashLine)); p.setBrush(Qt.NoBrush); p.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 7, 7)
            led = QColor(*T.PALETTE_ROWS[r][1]).darker(250)
            p.setPen(Qt.NoPen); p.setBrush(led); p.drawRoundedRect(QRectF(COLS * cell + 4, r * cell + cell / 2 - 5, 12, 10), 4, 4)


class MemoryPanel(QWidget):
    """Carte « Mémoires » : en-tête (REC, pages) + surface de pads + légende."""

    def __init__(self, ctl: AppController, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        card = QWidget(); card.setObjectName("card"); card.setAttribute(Qt.WA_StyledBackground, True)
        card.setStyleSheet(f"QWidget#card{{background:{T.PANEL};border:1px solid {T.BORDER};border-radius:{T.R_LG}px;}}")
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.addWidget(card)
        cl = QVBoxLayout(card); cl.setContentsMargins(16, 14, 16, 14); cl.setSpacing(12)
        head = QHBoxLayout(); head.setSpacing(8)
        t = QLabel("MÉMOIRES"); t.setObjectName("section"); head.addWidget(t); head.addStretch(1)
        self.rec = QPushButton("REC"); self.rec.setObjectName("danger"); self.rec.setCheckable(True); self.rec.setToolTip("REC puis clic sur un pad : enregistre l'état courant")
        self.prev = QPushButton("◀"); self.prev.setObjectName("ghost"); self.next = QPushButton("▶"); self.next.setObjectName("ghost")
        self.page_lbl = QLabel("PAGE 1"); self.page_lbl.setStyleSheet(f"color:{T.TEXT};font-weight:600;")
        for w in (self.rec, self.prev, self.page_lbl, self.next):
            head.addWidget(w)
        cl.addLayout(head)
        self.pads = PadSurface(ctl); cl.addWidget(self.pads)
        cap = QLabel("Colonne = groupe · REC puis pad = enregistrer · clic droit = vider · re-clic = éteindre")
        cap.setObjectName("muted"); cap.setWordWrap(True); cl.addWidget(cap)
        self.pads.pressed.connect(ctl.pad_press); self.pads.cleared.connect(ctl.pad_clear); self.pads.rowPressed.connect(ctl.row_press)
        self.rec.clicked.connect(ctl.toggle_rec)
        self.prev.clicked.connect(lambda: ctl.set_page(ctl.page - 1)); self.next.clicked.connect(lambda: ctl.set_page(ctl.page + 1))
        ctl.memoriesChanged.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self.page_lbl.setText(f"PAGE {self.ctl.page + 1}")
        self.rec.blockSignals(True); self.rec.setChecked(self.ctl.recording); self.rec.blockSignals(False)
        self.pads.update()
