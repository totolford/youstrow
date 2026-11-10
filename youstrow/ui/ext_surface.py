"""Surface EXT : surface d'exécuteurs configurable (façon grandMA) — blocs placés sur une grille magnétique.

Deux modes : **Édition** (palette à gauche, clic = ajoute un bloc, clic droit sur un bloc = le supprime) et **Live**
(les blocs déclenchent de vraies actions : couleur, strobe, effet, mémoire, faders, blackout, clear). La disposition
est enregistrée dans le show (`ctl.ext_layout`). Peut être détachée sur un autre écran (voir panels.PanelHost)."""
from __future__ import annotations

import time

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QSlider, QVBoxLayout, QWidget)

from ..controller import AppController
from ..engine.memories import PALETTE
from . import theme as T

CELL_W, CELL_H, GAP, MARGIN = 100, 92, 8, 16
GRID_COLS, GRID_ROWS = 14, 8
BANKS = ["Couleurs", "Strobe", "Effets", "Mémoires", "Faders", "Système"]


def specs_for(ctl: AppController, bank: str) -> list[dict]:
    if bank == "Couleurs":
        return [{"type": "color", "label": n, "arg": list(rgb), "gw": 1, "gh": 1} for n, rgb in PALETTE]
    if bank == "Strobe":
        return [{"type": "strobe", "label": "Strobe", "gw": 1, "gh": 1}]
    if bank == "Effets":
        return [{"type": "effect", "label": e.name, "arg": e.name, "gw": 1, "gh": 1} for e in ctl.effects]
    if bank == "Mémoires":
        return [{"type": "mem", "label": m.name, "arg": [p, r, c], "gw": 1, "gh": 1} for (p, r, c), m in sorted(ctl.bank.slots.items())][:96]
    if bank == "Faders":
        return ([{"type": "fader", "label": "MASTER", "arg": "master", "gw": 1, "gh": 3}] +
                [{"type": "fader", "label": f"G{g}", "arg": f"group:{g}", "gw": 1, "gh": 3} for g in range(1, 9)] +
                [{"type": "fader", "label": "FX", "arg": "fx", "gw": 1, "gh": 3}])
    return [{"type": "blackout", "label": "Blackout", "gw": 1, "gh": 1}, {"type": "clear", "label": "CLEAR", "gw": 1, "gh": 1},
            {"type": "clock", "label": "Horloge", "gw": 2, "gh": 1}]


class Block(QFrame):
    removed = Signal(object)

    def __init__(self, ctl: AppController, spec: dict, edit_mode):
        super().__init__()
        self.ctl, self.spec, self._edit = ctl, spec, edit_mode
        self.state = False
        self.setCursor(Qt.PointingHandCursor)
        self.lbl = QLabel(spec["label"], self); self.lbl.setAlignment(Qt.AlignCenter); self.lbl.setStyleSheet("background:transparent;font-weight:500;")
        self.slider = None
        if spec["type"] == "fader":
            self.slider = QSlider(Qt.Vertical, self); self.slider.setRange(0, 100); self.slider.setValue(self._fader_value())
            self.slider.setStyleSheet(f"QSlider::groove:vertical{{width:8px;background:{T.RAISED_HI};border-radius:4px}}"
                                      f"QSlider::sub-page:vertical{{background:{T.BRAND if spec['arg'] == 'master' else T.ACCENT};border-radius:4px}}"
                                      f"QSlider::handle:vertical{{height:16px;width:36px;margin:0 -14px;border-radius:6px;background:#f5f7fa}}")
            self.slider.valueChanged.connect(self._fader_moved)
        if spec["type"] == "clock":
            self.lbl.setStyleSheet(f"background:transparent;font-size:22px;font-weight:600;color:{T.TEXT};")

    def _fader_value(self) -> int:
        a, c = self.spec["arg"], self.ctl.console
        return round((c.master if a == "master" else c.group_levels.get(int(a.split(":")[1]), 1.0) if a.startswith("group") else
                      min(max((self.ctl.fx_speed / 4.0), 0.0), 1.0)) * 100)

    def _fader_moved(self, v):
        a, c = self.spec["arg"], self.ctl.console
        if a == "master": c.master = v / 100
        elif a.startswith("group"): c.group_levels[int(a.split(":")[1])] = v / 100
        else: self.ctl.set_fx_speed(max(0.1, v / 100 * 4.0))
        self.ctl.dirty = True

    def resizeEvent(self, _):
        r = self.rect()
        if self.slider:
            self.lbl.setGeometry(0, r.height() - 26, r.width(), 22)
            self.slider.setGeometry(r.width() // 2 - 4, 10, 8, r.height() - 44)
        else:
            self.lbl.setGeometry(0, r.height() // 2, r.width(), 24)

    def mousePressEvent(self, e):
        if self._edit():
            if e.button() == Qt.RightButton:
                self.removed.emit(self)
            return
        if self.slider or e.button() != Qt.LeftButton:
            return
        self.fire()

    def fire(self):
        t, a, c = self.spec["type"], self.spec.get("arg"), self.ctl.console
        if t == "color":
            c.set_color(tuple(a)); c.set_dimmer(1.0); self.ctl.touch()
        elif t == "strobe":
            on = not any(s.strobe > 0 for s in c.states.values()); c.set_strobe(1.0 if on else 0.0); self.ctl.touch()
        elif t == "effect":
            eff = self.ctl.effects_by_name().get(a)
            if eff:
                (c.stop_effect(a) if a in c.running else c.start_effect(eff, 1.0, self.ctl.fx_speed)); self.ctl.touch()
        elif t == "mem":
            self.ctl.bank.recall(a[0], a[1], a[2], c, self.ctl.effects_by_name()); self.ctl.touch(); self.ctl.memoriesChanged.emit()
        elif t == "blackout":
            c.blackout = not c.blackout
        elif t == "clear":
            c.stop_all_effects(); c.states.clear(); self.ctl.touch()

    def sync(self):
        t, a, c = self.spec["type"], self.spec.get("arg"), self.ctl.console
        on = False
        if t == "effect":
            on = a in c.running
        elif t == "blackout":
            on = c.blackout
        elif t == "strobe":
            on = any(s.strobe > 0 for s in c.states.values())
        elif t == "mem":
            on = self.ctl.bank.active_row(a[0], a[2]) == a[1]
        elif t == "color":
            on = bool(c.states) and any(tuple(s.color) == tuple(a) and s.dimmer > 0 for s in c.states.values())
        if t == "clock":
            self.lbl.setText(time.strftime("%H:%M:%S"))
        if t == "fader" and not self.slider.isSliderDown():
            self.slider.blockSignals(True); self.slider.setValue(self._fader_value()); self.slider.blockSignals(False)
        if on != self.state:
            self.state = on; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        t = self.spec["type"]
        p.setPen(QColor(T.ACCENT if self.state else T.BORDER)); p.setBrush(QColor(T.ACCENT_DIM if self.state else T.RAISED))
        p.drawRoundedRect(r, 12, 12)
        if t in ("color", "effect", "mem", "strobe"):
            col = QColor(*self.spec["arg"]) if t == "color" else QColor(T.VIOLET if t == "effect" else (T.BRAND if t == "mem" else "#FFFFFF"))
            bar = QRect(r.center().x() - 17, r.top() + 14, 34, 8)
            if self.state:
                g = QColor(col); g.setAlpha(80); p.setPen(Qt.NoPen); p.setBrush(g); p.drawRoundedRect(bar.adjusted(-4, -4, 4, 4), 8, 8)
            p.setPen(Qt.NoPen); p.setBrush(col); p.drawRoundedRect(bar, 4, 4)
        self.lbl.setStyleSheet(f"background:transparent;font-weight:500;color:{T.ACCENT if self.state else T.TEXT};" +
                               ("font-size:22px;font-weight:600;" if t == "clock" else ""))


class Canvas(QWidget):
    def __init__(self, ctl: AppController, edit_mode):
        super().__init__()
        self.ctl, self.edit_mode, self.blocks = ctl, edit_mode, []
        self.setMinimumSize(MARGIN * 2 + GRID_COLS * (CELL_W + GAP), MARGIN * 2 + GRID_ROWS * (CELL_H + GAP))

    def rebuild(self):
        for b in self.blocks:
            b.deleteLater()
        self.blocks = []
        for spec in self.ctl.ext_layout:
            self._make(spec)

    def _make(self, spec):
        b = Block(self.ctl, spec, self.edit_mode); b.setParent(self); b.removed.connect(self.remove)
        gw, gh = spec.get("gw", 1), spec.get("gh", 1)
        b.setGeometry(MARGIN + spec["gx"] * (CELL_W + GAP), MARGIN + spec["gy"] * (CELL_H + GAP), gw * CELL_W + (gw - 1) * GAP, gh * CELL_H + (gh - 1) * GAP)
        b.show(); self.blocks.append(b)

    def free_cell(self, gw, gh):
        occ = {(s["gx"] + i, s["gy"] + j) for s in self.ctl.ext_layout for i in range(s.get("gw", 1)) for j in range(s.get("gh", 1))}
        for y in range(GRID_ROWS - gh + 1):
            for x in range(GRID_COLS - gw + 1):
                if all((x + i, y + j) not in occ for i in range(gw) for j in range(gh)):
                    return x, y
        return None

    def add(self, spec: dict) -> bool:
        pos = self.free_cell(spec.get("gw", 1), spec.get("gh", 1))
        if pos is None:
            return False
        s = {**spec, "gx": pos[0], "gy": pos[1]}
        self.ctl.ext_layout.append(s); self._make(s); self.ctl.dirty = True
        return True

    def remove(self, block):
        if block.spec in self.ctl.ext_layout:
            self.ctl.ext_layout.remove(block.spec)
        self.blocks.remove(block); block.deleteLater(); self.ctl.dirty = True

    def paintEvent(self, _):
        p = QPainter(self)
        p.setPen(Qt.NoPen); p.setBrush(QColor(255, 255, 255, 18))
        for x in range(GRID_COLS):
            for y in range(GRID_ROWS):
                p.drawEllipse(MARGIN + x * (CELL_W + GAP) + CELL_W // 2 - 1, MARGIN + y * (CELL_H + GAP) + CELL_H // 2 - 1, 2, 2)


class ExtSurface(QWidget):
    def __init__(self, ctl: AppController, parent=None):
        super().__init__(parent)
        self.ctl, self.edit = ctl, False
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(12)
        tb = QHBoxLayout(); tb.setSpacing(8)
        self.b_edit, self.b_live = QPushButton("Édition"), QPushButton("Live")
        for b in (self.b_edit, self.b_live):
            b.setCheckable(True); tb.addWidget(b)
        self.b_live.setChecked(True)
        self.bank_btns = {}
        tb.addSpacing(12)
        for name in BANKS:
            b = QPushButton(name); b.setObjectName("ghost"); b.setCheckable(True); b.clicked.connect(lambda _=False, n=name: self.set_bank(n)); tb.addWidget(b); self.bank_btns[name] = b
        tb.addStretch(1)
        self.hint = QLabel(""); self.hint.setObjectName("muted"); tb.addWidget(self.hint)
        lay.addLayout(tb)
        body = QHBoxLayout(); body.setSpacing(12)
        self.pal = QListWidget(); self.pal.setFixedWidth(230); self.pal.itemClicked.connect(self._add_item); body.addWidget(self.pal)
        card = QFrame(); card.setObjectName("card"); cl = QVBoxLayout(card); cl.setContentsMargins(0, 0, 0, 0)
        self.canvas = Canvas(ctl, lambda: self.edit)
        from PySide6.QtWidgets import QScrollArea
        sa = QScrollArea(); sa.setWidgetResizable(False); sa.setWidget(self.canvas); sa.setFrameShape(QFrame.NoFrame); cl.addWidget(sa)
        body.addWidget(card, 1)
        lay.addLayout(body, 1)
        self.b_edit.clicked.connect(lambda: self.set_edit(True)); self.b_live.clicked.connect(lambda: self.set_edit(False))
        self.bank = "Couleurs"; self.bank_btns["Couleurs"].setChecked(True)
        ctl.playlistChanged.connect(self.reload); ctl.memoriesChanged.connect(self._fill_palette)
        self._t = QTimer(self); self._t.setInterval(200); self._t.timeout.connect(self._sync); self._t.start()
        self.set_edit(False); self.reload()

    def reload(self):
        self.canvas.rebuild(); self._fill_palette()

    def set_edit(self, on: bool):
        self.edit = on
        self.b_edit.setChecked(on); self.b_live.setChecked(not on)
        self.pal.setVisible(on)
        self.hint.setText("Clic sur un élément de la palette = ajouter · clic droit sur un bloc = supprimer" if on else "Mode Live : les blocs agissent sur la lumière")

    def set_bank(self, name: str):
        self.bank = name
        for n, b in self.bank_btns.items():
            b.setChecked(n == name)
        self._fill_palette()

    def _fill_palette(self):
        self.pal.clear()
        for spec in specs_for(self.ctl, self.bank):
            it = QListWidgetItem(spec["label"]); it.setData(Qt.UserRole, spec); self.pal.addItem(it)

    def _add_item(self, it):
        if not self.canvas.add(dict(it.data(Qt.UserRole))):
            self.ctl.log("warn", "Surface EXT : plus de place libre sur la grille.")

    def _sync(self):
        if self.isVisible():
            for b in self.canvas.blocks:
                b.sync()
