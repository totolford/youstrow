"""Patch DMX : bibliothèque d'appareils + tableau des appareils patchés (widget intégrable)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QListWidget, QMessageBox, QPushButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..controller import AppController
from ..fixtures.model import CHANNEL_LABELS_FR, PatchError, search_library
from ..fixtures.rig import STANDS, line_report, stand_warnings

COLS = ["ID", "Nom", "Modèle / mode", "Univers", "Adresse", "Fin", "Groupe", "Splitter", "Pied", "Haut. cm"]


class PatchView(QWidget):
    def __init__(self, ctl: AppController, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self._results = []
        self._loading = False
        root = QVBoxLayout(self); root.setContentsMargins(14, 14, 14, 14); root.setSpacing(12)

        # ---- bandeau du haut : ajouter un appareil
        top_card = QFrame(); top_card.setObjectName("card")
        tc = QHBoxLayout(top_card); tc.setContentsMargins(14, 12, 14, 12); tc.setSpacing(16)
        lcol = QVBoxLayout(); lcol.setSpacing(6)
        t = QLabel("AJOUTER UN APPAREIL"); t.setObjectName("section"); lcol.addWidget(t)
        self.search = QLineEdit(); self.search.setPlaceholderText("Rechercher (marque, modèle, type)…"); lcol.addWidget(self.search)
        self.results = QListWidget(); self.results.setFixedHeight(140); lcol.addWidget(self.results)
        tc.addLayout(lcol, 3)
        rcol = QVBoxLayout(); rcol.setSpacing(6)
        self.mode = QComboBox(); rcol.addWidget(self.mode)
        self.chan_label = QLabel(""); self.chan_label.setObjectName("muted"); self.chan_label.setWordWrap(True); rcol.addWidget(self.chan_label)
        g = QGridLayout(); g.setSpacing(6)
        self.count = QSpinBox(); self.count.setRange(1, 64); self.count.setValue(1)
        self.uni = QComboBox(); [self.uni.addItem(f"Univers {i + 1}", i) for i in range(4)]
        self.addr = QSpinBox(); self.addr.setRange(0, 512); self.addr.setSpecialValueText("auto")
        self.group = QComboBox(); self.group.addItem("Aucun", 0); [self.group.addItem(f"Groupe {i}", i) for i in range(1, 9)]
        for i, (lab, w) in enumerate((("Quantité", self.count), ("Univers", self.uni), ("Adresse", self.addr), ("Groupe", self.group))):
            g.addWidget(QLabel(lab), i // 2, (i % 2) * 2); g.addWidget(w, i // 2, (i % 2) * 2 + 1)
        rcol.addLayout(g); rcol.addStretch(1)
        self.add_btn = QPushButton("Patcher"); self.add_btn.setObjectName("primary"); rcol.addWidget(self.add_btn)
        tc.addLayout(rcol, 2)
        root.addWidget(top_card)

        # ---- tableau
        top = QHBoxLayout(); title = QLabel("APPAREILS PATCHÉS"); title.setObjectName("section"); top.addWidget(title); top.addStretch(1)
        self.summary = QLabel(""); self.summary.setObjectName("muted"); top.addWidget(self.summary)
        root.addLayout(top)
        self.table = QTableWidget(0, len(COLS)); self.table.setHorizontalHeaderLabels(COLS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True); self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader(); hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Interactive); self.table.setColumnWidth(1, 125)
        hh.setSectionResizeMode(2, QHeaderView.Stretch); hh.setMinimumSectionSize(48)
        root.addWidget(self.table, 1)
        row = QHBoxLayout()
        self.del_btn = QPushButton("Supprimer la sélection"); self.del_btn.setObjectName("danger")
        self.inv_pan = QPushButton("Inverser Pan"); self.inv_tilt = QPushButton("Inverser Tilt")
        self.rig_btn = QPushButton("Fiche de câblage"); self.rig_btn.setToolTip("Sorties du splitter Showtec DB-1-8, pieds, avertissements")
        row.addWidget(self.del_btn); row.addWidget(self.rig_btn); row.addStretch(1); row.addWidget(self.inv_pan); row.addWidget(self.inv_tilt)
        root.addLayout(row)

        self.search.textChanged.connect(self._search)
        self.results.currentRowChanged.connect(self._pick)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.add_btn.clicked.connect(self._add)
        self.del_btn.clicked.connect(self._delete)
        self.rig_btn.clicked.connect(self._rig)
        self.table.itemChanged.connect(self._edited)
        self.inv_pan.clicked.connect(lambda: self._invert("pan"))
        self.inv_tilt.clicked.connect(lambda: self._invert("tilt"))
        ctl.patchChanged.connect(self.reload)
        self._search("")
        self.reload()

    # --------------------------------------------------------- bibliothèque
    def _search(self, text):
        self._results = search_library(text, 300)
        self.results.clear()
        for d in self._results:
            self.results.addItem(f"{d.label}   ·   {d.fixture_type}")
        if self._results:
            self.results.setCurrentRow(0)

    def _pick(self, row):
        self.mode.clear()
        if 0 <= row < len(self._results):
            for m in self._results[row].modes:
                self.mode.addItem(f"{m.name}  ({len(m.channels)} canaux)")
        self._mode_changed()

    def _mode_changed(self):
        r, m = self.results.currentRow(), self.mode.currentIndex()
        if 0 <= r < len(self._results) and 0 <= m < len(self._results[r].modes):
            self.chan_label.setText(" · ".join(CHANNEL_LABELS_FR.get(c, c) for c in self._results[r].modes[m].channels))

    def _add(self):
        r, m = self.results.currentRow(), self.mode.currentIndex()
        if r < 0 or m < 0:
            return
        d = self._results[r]
        try:
            added = self.ctl.console.patch.add_many(d, d.modes[m], self.count.value(), self.uni.currentData(), self.addr.value() or None)
        except PatchError as e:
            QMessageBox.warning(self, "Patch", str(e)); return
        for f in added:
            f.group = self.group.currentData()
            self.ctl.console.state(f.id).color = (255, 255, 255)   # un appareil neuf s'allume en blanc : on voit tout de suite qu'il répond
        self.ctl.log("ok", f"Patch : {len(added)} × {d.label} (U{added[0].universe + 1}.{added[0].address})")
        self.ctl.patch_touch()

    # -------------------------------------------------------------- tableau
    def reload(self):
        self._loading = True
        fx = self.ctl.console.patch.fixtures
        self.table.setRowCount(len(fx))
        for i, f in enumerate(sorted(fx, key=lambda f: (f.universe, f.address))):
            vals = [f.id, f.name, f"{f.model} — {f.mode}", f.universe + 1, f.address, f.end_address, f.group or "", f.line or "", f.stand, f.height_cm or ""]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v)); it.setData(Qt.UserRole, f.id)
                if c in (0, 2, 5):
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    if c != 2: it.setForeground(Qt.gray)
                self.table.setItem(i, c, it)
        used = sum(f.footprint for f in fx)
        self.summary.setText(f"{len(fx)} appareils · {used} canaux")
        self._loading = False

    def _selected_ids(self):
        return sorted({self.table.item(i.row(), 0).data(Qt.UserRole) for i in self.table.selectedIndexes()})

    def _edited(self, item):
        if self._loading:
            return
        f = self.ctl.console.patch.get(item.data(Qt.UserRole))
        if not f: return
        old = (f.name, f.universe, f.address, f.group, f.line, f.stand, f.height_cm)
        try:
            col, txt = item.column(), item.text().strip()
            if col == 1: f.name = txt or f.name
            elif col == 3: f.universe = int(txt) - 1
            elif col == 4: f.address = int(txt)
            elif col == 6: f.group = int(txt) if txt else 0
            elif col == 7: f.line = int(txt) if txt else 0
            elif col == 8:
                if txt and txt not in STANDS: raise PatchError('Pieds connus : ' + ', '.join(STANDS))
                f.stand = txt
            elif col == 9: f.height_cm = int(txt) if txt else 0
            if not 0 <= f.universe < 4: raise PatchError("Univers : 1 à 4")
            if not 0 <= f.group <= 8: raise PatchError("Groupe : 0 à 8")
            if not 0 <= f.line <= 8: raise PatchError("Sortie du splitter : 1 à 8 (0 = aucune)")
            if f.height_cm < 0: raise PatchError("Hauteur négative")
            if f.address < 1 or f.end_address > 512: raise PatchError(f"Adresses {f.address}-{f.end_address} hors de 1..512")
            c = self.ctl.console.patch.conflicts(f)
            if c: raise PatchError(f"Chevauche {c[0].name} ({c[0].address}-{c[0].end_address})")
        except (ValueError, PatchError) as e:
            f.name, f.universe, f.address, f.group, f.line, f.stand, f.height_cm = old
            QMessageBox.warning(self, "Patch", str(e) if isinstance(e, PatchError) else "Valeur numérique attendue")
        self.ctl.patch_touch()

    def _rig(self):
        lines = line_report(self.ctl.console.patch) + [''] + (stand_warnings(self.ctl.console.patch) or ['Pieds : aucun avertissement'])
        box = QMessageBox(self); box.setWindowTitle('Fiche de câblage'); box.setText('\n'.join(lines)); box.exec()

    def _delete(self):
        ids = self._selected_ids()
        if not ids: return
        for i in ids:
            self.ctl.console.patch.remove(i); self.ctl.console.states.pop(i, None)
        self.ctl.patch_touch()

    def _invert(self, which):
        for i in self._selected_ids():
            f = self.ctl.console.patch.get(i)
            if f: setattr(f, "invert_" + which, not getattr(f, "invert_" + which))
        self.ctl.log("info", f"Inversion {which.capitalize()} appliquée à la sélection.")
        self.ctl.touch()
