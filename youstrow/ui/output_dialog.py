"""Assistant « Sortie DMX » : détecter, choisir, connecter, diagnostiquer, tester."""
from __future__ import annotations

from PySide6.QtCore import QThread, QTimer, Signal, Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                               QPushButton, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from ..controller import OUTPUT_TYPES, AppController, detect_hardware
from ..engine.outputs.artnet import discover_nodes


class _Scan(QThread):
    done = Signal(object)

    def __init__(self, fn):
        super().__init__(); self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn())
        except Exception as e:  # noqa: BLE001
            self.done.emit(e)


class OutputDialog(QDialog):
    def __init__(self, ctl: AppController, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.setWindowTitle("Sortie DMX")
        self.setMinimumWidth(620)
        self._scan = None
        lay = QVBoxLayout(self); lay.setSpacing(12); lay.setContentsMargins(20, 18, 20, 18)
        h = QLabel("Sortie DMX"); h.setObjectName("h1"); lay.addWidget(h)
        sub = QLabel("Choisissez votre interface. Sans matériel, laissez « Aucune » : le plan de feu et le moniteur "
                     "simulent la sortie."); sub.setObjectName("muted"); sub.setWordWrap(True); lay.addWidget(sub)

        form = QFormLayout(); form.setLabelAlignment(Qt.AlignLeft); form.setSpacing(10)
        self.type = QComboBox()
        for k, v in OUTPUT_TYPES.items():
            self.type.addItem(v, k)
        form.addRow("Interface", self.type)
        self.pages = QStackedWidget()
        form.addRow(self.pages)
        self.fps = QSpinBox(); self.fps.setRange(1, 44); self.fps.setSuffix(" images/s")
        form.addRow("Cadence", self.fps)
        lay.addLayout(form)

        # pages : 0 none, 1 d2xx, 2 com, 3 pro, 4 artnet
        self.pages.addWidget(self._info("Aucune sortie physique : l'application tourne en simulation."))
        p1 = QWidget(); l1 = QHBoxLayout(p1); l1.setContentsMargins(0, 0, 0, 0)
        self.ftdi = QComboBox(); l1.addWidget(self.ftdi, 1)
        self.pages.addWidget(p1)
        p2 = QWidget(); l2 = QHBoxLayout(p2); l2.setContentsMargins(0, 0, 0, 0)
        self.com = QComboBox(); l2.addWidget(self.com, 1)
        self.pages.addWidget(p2)
        p3 = QWidget(); l3 = QHBoxLayout(p3); l3.setContentsMargins(0, 0, 0, 0)
        self.com_pro = QComboBox(); l3.addWidget(self.com_pro, 1)
        self.pages.addWidget(p3)
        p4 = QWidget(); l4 = QFormLayout(p4); l4.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout(); self.ip = QLineEdit(); self.nodes = QComboBox(); self.nodes.setMinimumWidth(180)
        self.find_nodes = QPushButton("Rechercher"); row.addWidget(self.ip, 1); row.addWidget(self.nodes); row.addWidget(self.find_nodes)
        l4.addRow("Adresse IP du node", row)
        self.unis = []
        urow = QHBoxLayout()
        for i in range(4):
            sp = QSpinBox(); sp.setRange(0, 32767); self.unis.append(sp)
            urow.addWidget(QLabel(f"U{i + 1}→")); urow.addWidget(sp)
        l4.addRow("Univers Art-Net", urow)
        self.pages.addWidget(p4)

        self.refresh_btn = QPushButton("Actualiser la détection")
        lay.addWidget(self.refresh_btn)
        self.diag = QPlainTextEdit(); self.diag.setReadOnly(True); self.diag.setFixedHeight(130); lay.addWidget(self.diag)

        self.status = QLabel(""); self.status.setWordWrap(True); lay.addWidget(self.status)
        btns = QHBoxLayout()
        self.test_btn = QPushButton("Test 100 % (3 s)"); self.test_btn.setObjectName("danger")
        self.connect_btn = QPushButton("Connecter"); self.connect_btn.setObjectName("primary")
        self.disconnect_btn = QPushButton("Déconnecter")
        close = QPushButton("Fermer")
        btns.addWidget(self.test_btn); btns.addStretch(1); btns.addWidget(self.disconnect_btn); btns.addWidget(self.connect_btn); btns.addWidget(close)
        lay.addLayout(btns)

        self.type.currentIndexChanged.connect(self._type_changed)
        self.refresh_btn.clicked.connect(self.refresh)
        self.find_nodes.clicked.connect(self._find_nodes)
        self.nodes.activated.connect(lambda i: self.ip.setText(self.nodes.itemData(i) or self.ip.text()))
        self.connect_btn.clicked.connect(self._connect)
        self.disconnect_btn.clicked.connect(self.ctl.disconnect_output)
        self.test_btn.clicked.connect(self._test100)
        close.clicked.connect(self.accept)
        self.ctl.outputChanged.connect(self._update_status)
        self._timer = QTimer(self); self._timer.setInterval(500); self._timer.timeout.connect(self._update_status); self._timer.start()
        self._load()
        self.refresh()
        self._update_status()

    @staticmethod
    def _info(t):
        l = QLabel(t); l.setObjectName("muted"); l.setWordWrap(True); return l

    # ------------------------------------------------------------------
    def _load(self):
        c = self.ctl.settings.data["output"]
        i = self.type.findData(c.get("type", "none")); self.type.setCurrentIndex(max(0, i))
        self.fps.setValue(int(c.get("fps", 30)))
        self.ip.setText(c.get("ip", "255.255.255.255"))
        um = c.get("universe_map", {"0": 0})
        for i, sp in enumerate(self.unis):
            sp.setValue(int(um.get(str(i), i)))
        self._type_changed()

    def _type_changed(self):
        self.pages.setCurrentIndex(self.type.currentIndex())
        t = self.type.currentData()
        self.fps.setMaximum(44 if t.startswith("open_dmx") else 44)
        self.test_btn.setEnabled(t != "none")

    def refresh(self):
        hw = detect_hardware()
        cur_ser = self.ctl.settings.data["output"].get("serial", "")
        self.ftdi.clear()
        for d in hw["ftdi"]:
            self.ftdi.addItem(f"{d.description or 'FTDI'}  ·  {d.serial or '?'}" + ("  (déjà ouvert)" if d.in_use else ""), d.serial)
        if not hw["ftdi"]:
            self.ftdi.addItem("Aucune puce FTDI détectée", "")
        for combo, key in ((self.com, "port"), (self.com_pro, "port")):
            combo.clear()
            for dev, desc, ser in hw["com"]:
                combo.addItem(f"{dev}  ·  {desc}", dev)
            if not hw["com"]:
                combo.addItem("Aucun port COM", "")
            i = combo.findData(self.ctl.settings.data["output"].get(key, ""))
            if i >= 0: combo.setCurrentIndex(i)
        i = self.ftdi.findData(cur_ser)
        if i >= 0: self.ftdi.setCurrentIndex(i)
        lines = [f"Driver FTDI D2XX : {'disponible' if hw['d2xx_available'] else 'INTROUVABLE'}",
                 f"Puces FTDI détectées : {len(hw['ftdi'])}"]
        for d in hw["ftdi"]:
            lines.append(f"   • {d.description} — n° série {d.serial}" + (" — DÉJÀ OUVERTE (autre logiciel ?)" if d.in_use else ""))
        lines.append(f"Ports COM : {', '.join(p[0] + ' (' + p[1] + ')' for p in hw['com']) or 'aucun'}")
        if not hw["ftdi"]:
            lines += ["", "Pas d'Open DMX détecté. Vérifiez : câble USB, driver FTDI « CDM » installé (Gestionnaire de",
                      "périphériques), et qu'aucun autre logiciel DMX (QLC+, une autre instance de YouStrow…) n'utilise la puce."]
        self.diag.setPlainText("\n".join(lines))

    def _find_nodes(self):
        self.find_nodes.setEnabled(False); self.find_nodes.setText("Recherche…")
        self._scan = _Scan(lambda: discover_nodes(2.0)); self._scan.done.connect(self._nodes_found); self._scan.start()

    def _nodes_found(self, res):
        self.find_nodes.setEnabled(True); self.find_nodes.setText("Rechercher")
        self.nodes.clear()
        if isinstance(res, Exception):
            self.diag.appendPlainText(f"\nRecherche Art-Net : {res}"); return
        for n in res:
            self.nodes.addItem(f"{n.short_name or n.long_name} ({n.ip})", n.ip)
        if res:
            self.ip.setText(res[0].ip)
        self.diag.appendPlainText(f"\nNodes Art-Net trouvés : {len(res)}" + "".join(f"\n   • {n.short_name} {n.ip}" for n in res))

    def _config(self) -> dict:
        t = self.type.currentData()
        return {"type": t, "fps": self.fps.value(), "serial": self.ftdi.currentData() or "",
                "port": (self.com.currentData() if t == "open_dmx_com" else self.com_pro.currentData()) or "",
                "ip": self.ip.text().strip() or "255.255.255.255",
                "universe_map": {str(i): sp.value() for i, sp in enumerate(self.unis)}}

    def _connect(self):
        cfg = self._config()
        if cfg["type"] == "open_dmx_d2xx" and not self.ftdi.currentData() and self.ftdi.count() and "Aucune" in self.ftdi.currentText():
            QMessageBox.warning(self, "Sortie DMX", "Aucune puce FTDI n'est détectée. Branchez l'interface puis « Actualiser ».")
            return
        self.ctl.connect_output(cfg)
        self.ctl.settings.save()

    def _test100(self):
        if not self.ctl.output:
            QMessageBox.information(self, "Test", "Connectez d'abord la sortie."); return
        if QMessageBox.question(self, "Test 100 %",
                                "Ceci envoie 255 sur les 512 canaux pendant 3 secondes : les appareils branchés vont "
                                "s'allumer à fond (strobe, mouvements, fumée…).\n\nContinuer ?") != QMessageBox.Yes:
            return
        c = self.ctl.console
        c.tester_active = True
        for ch in range(1, 513):
            c.set_direct(0, ch, 255)
        self.ctl.log("warn", "Test 100 % : 512 canaux à 255 pendant 3 s.")

        def end():
            c.release_direct(); c.tester_active = False
            self.ctl.log("info", "Test 100 % terminé.")
        QTimer.singleShot(3000, end)

    def _update_status(self):
        o = self.ctl.output
        if not o:
            self.status.setText("● Non connectée (simulation)"); self.status.setStyleSheet("color:#7d8697")
        else:
            s = o.status
            txt = {"running": f"● Connectée — {o.name} — {s.fps:.0f} images/s — {s.frames_sent} trames",
                   "connecting": "● Connexion…", "error": f"● Erreur : {s.message}  (nouvelle tentative chaque seconde)",
                   "stopped": "● Arrêtée"}.get(s.state, s.state)
            col = {"running": "#2ee59d", "error": "#ff4d6a", "connecting": "#ffb020"}.get(s.state, "#7d8697")
            self.status.setText(txt); self.status.setStyleSheet(f"color:{col}")
        self.disconnect_btn.setEnabled(o is not None)
