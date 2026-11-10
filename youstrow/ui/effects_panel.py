"""Panneau d'effets (déclencheurs) et éditeur d'effets par couches."""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton,
                               QTableWidget, QVBoxLayout, QWidget, QGridLayout, QHeaderView)

from ..controller import AppController
from ..engine.effects import SHAPES, TARGETS, Effect, EffectLayer

TARGET_FR = {"dimmer": "Intensité", "hue": "Teinte", "red": "Rouge", "green": "Vert", "blue": "Bleu", "pan": "Pan",
             "tilt": "Tilt", "strobe": "Strobe"}
SHAPE_FR = {"sine": "Sinus", "triangle": "Triangle", "square": "Carré", "saw": "Dent de scie", "ramp": "Rampe inverse",
            "random": "Aléatoire"}


class EffectEditor(QDialog):
    def __init__(self, effect: Effect, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Éditeur d'effet"); self.setMinimumSize(760, 380)
        self.effect = deepcopy(effect)
        lay = QVBoxLayout(self); lay.setContentsMargins(18, 16, 18, 16); lay.setSpacing(10)
        row = QHBoxLayout(); row.addWidget(QLabel("Nom")); self.name = QLineEdit(effect.name); row.addWidget(self.name, 1); lay.addLayout(row)
        info = QLabel("Chaque couche module un paramètre : forme × vitesse (Hz) × taille × décalage entre appareils × phase.")
        info.setObjectName("muted"); lay.addWidget(info)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Cible", "Forme", "Vitesse (Hz)", "Taille", "Décalage", "Phase"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.table.verticalHeader().setVisible(False)
        lay.addWidget(self.table, 1)
        b = QHBoxLayout()
        add, rem, ok, ko = QPushButton("＋ Couche"), QPushButton("Supprimer la couche"), QPushButton("Enregistrer"), QPushButton("Annuler")
        ok.setObjectName("primary"); b.addWidget(add); b.addWidget(rem); b.addStretch(1); b.addWidget(ko); b.addWidget(ok); lay.addLayout(b)
        add.clicked.connect(lambda: self._add(EffectLayer())); rem.clicked.connect(self._remove)
        ok.clicked.connect(self._accept); ko.clicked.connect(self.reject)
        for l in self.effect.layers: self._add(l)

    def _add(self, l: EffectLayer):
        r = self.table.rowCount(); self.table.insertRow(r)
        c1, c2 = QComboBox(), QComboBox()
        for t in TARGETS: c1.addItem(TARGET_FR[t], t)
        for s in SHAPES: c2.addItem(SHAPE_FR[s], s)
        c1.setCurrentIndex(TARGETS.index(l.target)); c2.setCurrentIndex(SHAPES.index(l.shape))
        self.table.setCellWidget(r, 0, c1); self.table.setCellWidget(r, 1, c2)
        for col, (val, lo, hi, st) in enumerate(((l.rate, 0.01, 20, 0.1), (l.size, 0, 1, 0.05), (l.spread, 0, 1, 0.05), (l.phase, 0, 1, 0.05)), 2):
            s = QDoubleSpinBox(); s.setRange(lo, hi); s.setSingleStep(st); s.setDecimals(2); s.setValue(val); self.table.setCellWidget(r, col, s)

    def _remove(self):
        r = self.table.currentRow()
        if r >= 0: self.table.removeRow(r)

    def _accept(self):
        layers = []
        for r in range(self.table.rowCount()):
            w = [self.table.cellWidget(r, c) for c in range(6)]
            layers.append(EffectLayer(w[0].currentData(), w[1].currentData(), w[2].value(), w[3].value(), w[4].value(), w[5].value()))
        self.effect = Effect(self.name.text().strip() or "Effet", layers)
        self.accept()


class EffectsPanel(QWidget):
    effectsChanged = Signal()

    def __init__(self, ctl: AppController, selection, parent=None):
        super().__init__(parent)
        self.ctl, self.selection = ctl, selection
        self.buttons: dict[str, QPushButton] = {}
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(6)
        top = QHBoxLayout(); t = QLabel("EFFETS"); t.setObjectName("section"); top.addWidget(t); top.addStretch(1)
        new = QPushButton("＋"); new.setFixedWidth(34); new.setToolTip("Nouvel effet"); top.addWidget(new)
        stop = QPushButton("Stop"); stop.setToolTip("Arrêter tous les effets"); top.addWidget(stop)
        lay.addLayout(top)
        self.grid = QGridLayout(); self.grid.setSpacing(6); lay.addLayout(self.grid)
        new.clicked.connect(self._new); stop.clicked.connect(self._stop_all)
        self.rebuild()

    def rebuild(self):
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w: w.deleteLater()
        self.buttons.clear()
        for i, e in enumerate(self.ctl.effects):
            b = QPushButton(e.name); b.setCheckable(True); b.setChecked(e.name in self.ctl.console.running)
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.toggled.connect(lambda on, e=e: self._toggle(e, on))
            b.customContextMenuRequested.connect(lambda pos, e=e, b=b: self._menu(e, b.mapToGlobal(pos)))
            self.buttons[e.name] = b; self.grid.addWidget(b, i // 2, i % 2)
        self.effectsChanged.emit()

    def sync(self):
        """Recale les boutons sur les effets réellement en cours (lancés par une piste, le MIDI…)."""
        for name, b in self.buttons.items():
            on = name in self.ctl.console.running
            if b.isChecked() != on:
                b.blockSignals(True); b.setChecked(on); b.blockSignals(False)

    def _toggle(self, e: Effect, on: bool):
        c = self.ctl.console
        if on:
            ids = self.selection() or None
            c.start_effect(e, 1.0, self.ctl.fx_speed, ids)
            self.ctl.log("info", f"Effet « {e.name} » démarré" + (f" sur {len(ids)} appareil(s)" if ids else " sur tout le plan"))
        else:
            c.stop_effect(e.name)
        self.ctl.touch()

    def _stop_all(self):
        self.ctl.console.stop_all_effects()
        for b in self.buttons.values():
            b.blockSignals(True); b.setChecked(False); b.blockSignals(False)
        self.ctl.touch()

    def _new(self):
        dlg = EffectEditor(Effect("Nouvel effet", [EffectLayer()]), self)
        if dlg.exec():
            self.ctl.effects.append(dlg.effect); self.ctl.touch(); self.rebuild()

    def _menu(self, e: Effect, pos):
        m = QMenu(self); a1 = m.addAction("Modifier…"); a2 = m.addAction("Supprimer")
        act = m.exec(pos)
        if act == a1:
            dlg = EffectEditor(e, self)
            if dlg.exec():
                self.ctl.console.stop_effect(e.name)
                self.ctl.effects[self.ctl.effects.index(e)] = dlg.effect; self.ctl.touch(); self.rebuild()
        elif act == a2:
            self.ctl.console.stop_effect(e.name); self.ctl.effects.remove(e); self.ctl.touch(); self.rebuild()
