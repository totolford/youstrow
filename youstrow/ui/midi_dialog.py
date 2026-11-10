"""Fenêtre MIDI : connexion, profil APC mini, apprentissage, tableau des liaisons."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from ..controller import AppController
from ..engine import midi as M


class MidiDialog(QDialog):
    def __init__(self, ctl: AppController, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.setWindowTitle("MIDI"); self.setMinimumSize(680, 560)
        lay = QVBoxLayout(self); lay.setContentsMargins(20, 18, 20, 18); lay.setSpacing(10)
        h = QLabel("Contrôleur MIDI"); h.setObjectName("h1"); lay.addWidget(h)
        sub = QLabel("Branchez votre contrôleur (ex. AKAI APC mini), choisissez son port, puis utilisez le profil prédéfini "
                     "ou « Apprendre » pour lier n'importe quel bouton/fader à une action."); sub.setObjectName("muted"); sub.setWordWrap(True); lay.addWidget(sub)

        r1 = QHBoxLayout(); r1.addWidget(QLabel("Entrée")); self.inp = QComboBox(); r1.addWidget(self.inp, 1)
        r1.addWidget(QLabel("Retour LED")); self.out = QComboBox(); r1.addWidget(self.out, 1); lay.addLayout(r1)
        r2 = QHBoxLayout()
        self.refresh_btn = QPushButton("Actualiser"); self.connect_btn = QPushButton("Connecter"); self.connect_btn.setObjectName("primary")
        self.disc_btn = QPushButton("Déconnecter"); self.apc_btn = QPushButton("Profil AKAI APC mini")
        for b in (self.refresh_btn, self.apc_btn): r2.addWidget(b)
        r2.addStretch(1); r2.addWidget(self.disc_btn); r2.addWidget(self.connect_btn); lay.addLayout(r2)
        self.status = QLabel(""); lay.addWidget(self.status)
        self.activity = QLabel("Dernier message : —"); self.activity.setObjectName("muted"); lay.addWidget(self.activity)

        lr = QHBoxLayout(); lr.addWidget(QLabel("Apprendre :")); self.action = QComboBox(); lr.addWidget(self.action, 1)
        self.learn_btn = QPushButton("Apprendre"); lr.addWidget(self.learn_btn); lay.addLayout(lr)
        self.table = QTableWidget(0, 3); self.table.setHorizontalHeaderLabels(["Action", "Contrôle", "Canal"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True); self.table.setEditTriggers(QTableWidget.NoEditTriggers); self.table.setSelectionBehavior(QTableWidget.SelectRows)
        lay.addWidget(self.table, 1)
        r3 = QHBoxLayout(); self.del_btn = QPushButton("Supprimer la liaison"); self.del_btn.setObjectName("danger"); close = QPushButton("Fermer")
        r3.addWidget(self.del_btn); r3.addStretch(1); r3.addWidget(close); lay.addLayout(r3)

        self.refresh_btn.clicked.connect(self.refresh); self.connect_btn.clicked.connect(self._connect); self.disc_btn.clicked.connect(self.ctl.disconnect_midi)
        self.apc_btn.clicked.connect(self._apc); self.learn_btn.clicked.connect(self._learn); self.del_btn.clicked.connect(self._delete)
        close.clicked.connect(self.accept)
        ctl.midiChanged.connect(self._update); ctl.midiActivity.connect(lambda t: self.activity.setText("Dernier message : " + t))
        self.names = [e.name for e in ctl.effects]
        for a in M.FADER_ACTIONS + M.BUTTON_ACTIONS:
            if a.startswith("pad:"): continue                 # 64 pads : trop long pour la liste, apprentissage par pad depuis le profil
            self.action.addItem(("🎚 " if M.is_fader(a) else "🔘 ") + M.action_label(a, self.names), a)
        self.refresh(); self._update()

    def refresh(self):
        mc = self.ctl.settings.data["midi"]
        ins, outs = M.list_inputs(), M.list_outputs()
        self.inp.clear(); self.inp.addItems(ins or ["Aucune entrée MIDI détectée"])
        self.out.clear(); self.out.addItem("(aucun)", ""); [self.out.addItem(o, o) for o in outs]
        if mc.get("in") in ins: self.inp.setCurrentText(mc["in"])
        else:
            apc = next((i for i, n in enumerate(ins) if "apc" in n.lower()), -1)
            if apc >= 0: self.inp.setCurrentIndex(apc)
        i = self.out.findData(mc.get("out", ""))
        if i < 0:
            i = next((k for k in range(self.out.count()) if "apc" in self.out.itemText(k).lower()), 0)
        self.out.setCurrentIndex(max(0, i))

    def _connect(self):
        if not M.list_inputs():
            QMessageBox.information(self, "MIDI", "Aucune entrée MIDI détectée. Branchez le contrôleur puis « Actualiser »."); return
        try:
            self.ctl.connect_midi(self.inp.currentText(), self.out.currentData() or "")
            self.ctl.settings.save()
        except M.MidiError as e:
            QMessageBox.warning(self, "MIDI", str(e))

    def _apc(self):
        self.ctl.apply_apc_profile(); self.ctl.log("ok", "MIDI : profil AKAI APC mini appliqué (pads 8×8, faders 1-8, master).")

    def _learn(self):
        if self.ctl.learn_action:
            self.ctl.start_learn(None); return
        self.ctl.start_learn(self.action.currentData())

    def _delete(self):
        r = self.table.currentRow()
        if r >= 0:
            del self.ctl.bindings[r]; self.ctl.settings.data["midi"]["profile"] = "custom"; self.ctl.save_bindings()

    def _update(self):
        c = self.ctl.midi
        self.status.setText(f"● Connecté — {c.in_name}" if c.connected else "● Non connecté")
        self.status.setStyleSheet("color:#2ee59d" if c.connected else "color:#7d8697")
        learning = self.ctl.learn_action
        self.learn_btn.setText("Annuler (bougez un contrôle…)" if learning else "Apprendre")
        self.table.setRowCount(len(self.ctl.bindings))
        for r, b in enumerate(self.ctl.bindings):
            self.table.setItem(r, 0, QTableWidgetItem(M.action_label(b.action, self.names)))
            self.table.setItem(r, 1, QTableWidgetItem(f"{'Note' if b.kind == 'note' else 'CC'} {b.number}"))
            self.table.setItem(r, 2, QTableWidgetItem(str(b.channel) if b.channel else "tous"))

    def done(self, r):
        self.ctl.start_learn(None); super().done(r)
