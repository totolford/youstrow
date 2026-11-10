"""Panneau Rig (maquette Figma « Patch & Rig ») : sorties du splitter Showtec DB-1-8 et pieds Stairville BLS-315 Pro."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..controller import AppController
from ..fixtures.rig import MAX_DEVICES_PER_LINE, SPLITTERS, STANDS
from . import theme as T


def _row(title: str, sub: str, ok: bool, badge: str, right: str, warn: bool = False) -> QFrame:
    f = QFrame()
    bg, bd = (T.DANGER_DIM, T.DANGER) if warn else ((T.RAISED, T.BORDER_HI) if ok else (T.PANEL, T.BORDER))
    f.setStyleSheet(f"QFrame{{background:{bg};border:1px solid {bd};border-radius:10px;}} QLabel{{border:none;background:transparent;}}")
    h = QHBoxLayout(f); h.setContentsMargins(12, 9, 12, 9); h.setSpacing(12)
    if badge:
        b = QLabel(badge); b.setFixedSize(28, 28); b.setAlignment(Qt.AlignCenter)
        b.setStyleSheet(f"background:{T.ACCENT_DIM if ok else T.RAISED_HI};color:{T.ACCENT if ok else T.MUTED};border-radius:8px;font-weight:600;")
        h.addWidget(b)
    c = QVBoxLayout(); c.setSpacing(1)
    t = QLabel(title); t.setStyleSheet(f"color:{T.TEXT if ok else T.MUTED};font-weight:500;"); c.addWidget(t)
    if sub:
        s = QLabel(sub); s.setStyleSheet(f"color:{T.TEXT2};font-size:11px;"); c.addWidget(s)
    h.addLayout(c, 1)
    r = QLabel(right); r.setStyleSheet(f"color:{T.DANGER if warn else T.MUTED};font-size:11px;"); h.addWidget(r)
    return f


class RigPanel(QWidget):
    def __init__(self, ctl: AppController, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.lay = QVBoxLayout(self); self.lay.setContentsMargins(0, 0, 0, 0); self.lay.setSpacing(16)
        self.split_card, self.stand_card = QFrame(), QFrame()
        for c in (self.split_card, self.stand_card):
            c.setObjectName("card"); self.lay.addWidget(c)
        self.lay.addStretch(1)
        ctl.patchChanged.connect(self.refresh); ctl.stateChanged.connect(self.refresh)
        self.refresh()

    @staticmethod
    def _clear(layout):
        while layout.count():
            w = layout.takeAt(0).widget()
            if w:
                w.deleteLater()

    def refresh(self):
        patch = self.ctl.console.patch
        sp = SPLITTERS["Showtec DB-1-8"]
        # ---------- splitter
        if self.split_card.layout() is None:
            QVBoxLayout(self.split_card)
        l = self.split_card.layout(); self._clear(l); l.setContentsMargins(16, 14, 16, 14); l.setSpacing(10)
        used = {f.line for f in patch.fixtures if f.line}
        head = QLabel(f"SPLITTER · {sp.name.upper()}  ·  {len(used)} sortie(s) utilisée(s)"); head.setObjectName("section"); l.addWidget(head)
        l.addWidget(_row("ENTRÉE  ·  interface DMX → XLR 3/5 broches", "", True, "", ""))
        for n in range(1, sp.outputs + 1):
            fx = [f for f in patch.fixtures if f.line == n]
            if fx:
                warn = len(fx) > MAX_DEVICES_PER_LINE
                names = ", ".join(f.name for f in fx[:3]) + ("…" if len(fx) > 3 else "")
                l.addWidget(_row(f"{len(fx)} appareil(s) · {sum(f.footprint for f in fx)} canaux", names, True, str(n),
                                 f"> {MAX_DEVICES_PER_LINE} !" if warn else "120 Ω", warn))
            else:
                l.addWidget(_row("libre", "", False, str(n), "—"))
        direct = [f for f in patch.fixtures if not f.line]
        if direct:
            l.addWidget(_row(f"{len(direct)} appareil(s) en ligne directe (sans splitter)", "", True, "", ""))
        n = QLabel(f"Un terminateur 120 Ω en bout de CHAQUE ligne utilisée. Limite : {MAX_DEVICES_PER_LINE} appareils par sortie."); n.setObjectName("muted"); n.setWordWrap(True); l.addWidget(n)
        # ---------- pieds
        if self.stand_card.layout() is None:
            QVBoxLayout(self.stand_card)
        s = self.stand_card.layout(); self._clear(s); s.setContentsMargins(16, 14, 16, 14); s.setSpacing(8)
        st = next(iter(STANDS.values()))
        on = [f for f in patch.fixtures if f.stand]
        h = QLabel(f"PIEDS · {st.name.upper()} ({st.min_cm}–{st.max_cm} CM)  ·  {len(on)} appareil(s)"); h.setObjectName("section"); s.addWidget(h)
        if not on:
            m = QLabel("Aucun appareil sur pied. Renseignez « Pied » et « Haut. cm » dans le tableau du patch."); m.setObjectName("muted"); m.setWordWrap(True); s.addWidget(m)
        for f in on:
            m = STANDS.get(f.stand)
            bad = bool(m and f.height_cm and not m.min_cm <= f.height_cm <= m.max_cm)
            s.addWidget(_row(f.name, "", True, "", (f"{f.height_cm} cm — hors plage" if bad else (f"{f.height_cm} cm" if f.height_cm else "hauteur ?")), bad))
