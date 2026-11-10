"""Fenêtre principale."""
from __future__ import annotations

import colorsys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPlainTextEdit,
                               QPushButton, QSlider, QTabWidget, QVBoxLayout, QWidget)

from .. import __version__
from ..controller import AppController
from ..storage.files import SHOW_EXT
from . import theme as T
from ..engine import midi as midi_mod
from .dmx_tools import DmxMonitor, DmxTester
from .media_panel import MediaPanel
from .midi_dialog import MidiDialog
from .effects_panel import EffectsPanel
from .output_dialog import OutputDialog
from .patch_view import PatchView
from .widgets import Fader, GradientSlider, PadGrid, PositionPad, StagePlan


def card(layout) -> QFrame:
    f = QFrame(); f.setObjectName("card"); f.setLayout(layout); return f


def section(text) -> QLabel:
    l = QLabel(text); l.setObjectName("section"); return l


class MainWindow(QMainWindow):
    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        self.setWindowTitle("YouStrow")
        self.resize(1480, 880)
        self.setMinimumSize(1366, 760)
        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        grid = QHBoxLayout(root); grid.setContentsMargins(14, 6, 14, 14); grid.setSpacing(12)

        # ================= colonne gauche : pads + faders + journal
        left = QVBoxLayout(); left.setSpacing(10)
        pads_l = QVBoxLayout(); pads_l.setContentsMargins(14, 12, 14, 12); pads_l.setSpacing(8)
        head = QHBoxLayout(); head.addWidget(section("COULEURS PAR GROUPE")); head.addStretch(1)
        self.clear_btn = QPushButton("CLEAR"); self.clear_btn.setToolTip("Éteint tout et arrête les effets"); head.addWidget(self.clear_btn)
        pads_l.addLayout(head)
        self.pads = PadGrid(); pads_l.addWidget(self.pads)
        cap = QLabel("Chaque colonne = un groupe d'appareils (1 à 8). Voyant à droite = toute la ligne."); cap.setObjectName("muted"); cap.setWordWrap(True)
        pads_l.addWidget(cap)
        left.addWidget(card(pads_l))

        fad_l = QVBoxLayout(); fad_l.setContentsMargins(14, 12, 14, 12)
        fad_l.addWidget(section("NIVEAUX DES GROUPES"))
        fr = QHBoxLayout(); fr.setSpacing(0)
        self.group_faders = []
        for g in range(1, 9):
            f = Fader(f"G{g}", T.ACCENT, 1.0, 1.0); f.valueChanged.connect(lambda v, g=g: self._group_level(g, v)); self.group_faders.append(f); fr.addWidget(f)
        self.fx_fader = Fader("Vit. FX", T.BRAND, 0.5, 0.5); self.fx_fader.valueChanged.connect(self._fx_speed); fr.addSpacing(6); fr.addWidget(self.fx_fader)
        fad_l.addLayout(fr)
        left.addWidget(card(fad_l), 1)

        self.journal = QPlainTextEdit(); self.journal.setReadOnly(True); self.journal.setMaximumBlockCount(500); self.journal.setFixedHeight(120)
        jl = QVBoxLayout(); jl.setContentsMargins(10, 8, 10, 8); jl.addWidget(section("JOURNAL")); jl.addWidget(self.journal)
        left.addWidget(card(jl))
        lw = QWidget(); lw.setLayout(left); lw.setFixedWidth(360); grid.addWidget(lw)

        # ================= centre : onglets
        self.tabs = QTabWidget()
        self.media = MediaPanel(ctl); self.tabs.addTab(self.media, "Média")
        self.patch_view = PatchView(ctl)
        self.tabs.addTab(self.patch_view, "Patch DMX")
        self.tester = DmxTester(ctl); self.tabs.addTab(self.tester, "Testeur DMX")
        self.monitor = DmxMonitor(ctl); self.tabs.addTab(self.monitor, "Moniteur DMX")
        grid.addWidget(self.tabs, 1)

        # ================= colonne droite : plan + couleur + effets
        right = QVBoxLayout(); right.setSpacing(10)
        self.plan = StagePlan(ctl)
        pl = QVBoxLayout(); pl.setContentsMargins(10, 10, 10, 10)
        ph = QHBoxLayout(); ph.addWidget(section("PLAN DE FEU")); ph.addStretch(1)
        self.sel_all = QPushButton("SELEC. TOUT"); self.sel_none = QPushButton("DÉSÉLEC.")
        ph.addWidget(self.sel_all); ph.addWidget(self.sel_none); pl.addLayout(ph); pl.addWidget(self.plan, 1)
        self.sel_lbl = QLabel("Aucune sélection : les réglages s'appliquent à tous les appareils."); self.sel_lbl.setObjectName("muted"); pl.addWidget(self.sel_lbl)
        right.addWidget(card(pl), 1)

        colrow = QHBoxLayout(); colrow.setContentsMargins(14, 12, 14, 12); colrow.setSpacing(14)
        col = QVBoxLayout(); col.setSpacing(2)
        def labelled(name):
            r = QHBoxLayout(); r.addWidget(QLabel(name)); r.addStretch(1); v = QLabel(""); v.setObjectName("muted"); r.addWidget(v); col.addLayout(r); return v
        self.hue_lbl = labelled("Couleur")
        self.hue = GradientSlider([(i / 6, QColor.fromHsvF(i / 6 if i < 6 else 0.999, 1, 1).name()) for i in range(7)]); col.addWidget(self.hue)
        self.sat_lbl = labelled("Saturation")
        self.sat = GradientSlider([(0, "#ffffff"), (1, "#ff0000")]); self.sat.setValue(1.0); col.addWidget(self.sat)
        self.dim_lbl = labelled("Luminosité")
        self.dim = GradientSlider([(0, "#000000"), (1, "#ff0000")]); self.dim.setValue(1.0); col.addWidget(self.dim)
        self.strobe_lbl = labelled("Strobe")
        self.strobe = GradientSlider([(0, "#242933"), (1, "#ffffff")]); col.addWidget(self.strobe)
        self.hue_lbl.setText("0°"); self.sat_lbl.setText("100%"); self.dim_lbl.setText("100%"); self.strobe_lbl.setText("off")
        colrow.addLayout(col, 1)
        xyc = QVBoxLayout(); xyc.setSpacing(4); xyc.addWidget(section("PAN / TILT"))
        self.xy = PositionPad(); self.xy.setFixedSize(132, 132); xyc.addWidget(self.xy); xyc.addStretch(1)
        colrow.addLayout(xyc)
        right.addWidget(card(colrow))

        efl = QVBoxLayout(); efl.setContentsMargins(14, 12, 14, 12)
        self.effects = EffectsPanel(ctl, lambda: sorted(self.plan.selected)); efl.addWidget(self.effects)
        right.addWidget(card(efl))
        rw = QWidget(); rw.setLayout(right); rw.setFixedWidth(420); grid.addWidget(rw)

        self._build_menu()
        self._build_header()
        self._wire()
        ctl.actionTriggered.connect(self.apply_action)
        ctl.stateChanged.connect(self.effects.sync)
        self.effects.effectsChanged.connect(self.media._refresh_light_cells)
        self._led_cache: dict[int, int] = {}
        self._led_timer = QTimer(self); self._led_timer.setInterval(200); self._led_timer.timeout.connect(self._sync_leds); self._led_timer.start()
        self._sync_pads()
        ctl.logged.connect(self._log)
        ctl.outputChanged.connect(self._update_output_chip)
        ctl.showChanged.connect(self._update_title)
        ctl.patchChanged.connect(self._on_patch_changed)
        self._update_output_chip(); self._update_title(""); self._on_patch_changed()
        self._pad_color: dict[int, int] = {}

    # ------------------------------------------------------------ en-tête
    def _build_header(self):
        corner = self._corner = QWidget(); l = QHBoxLayout(corner); l.setContentsMargins(0, 0, 8, 0); l.setSpacing(10)
        self.out_chip = QPushButton("DMX : —"); self.out_chip.setToolTip("Ouvrir la configuration de la sortie DMX")
        self.out_chip.clicked.connect(self.open_output)
        self.blackout = QPushButton("BLACKOUT"); self.blackout.setCheckable(True); self.blackout.setObjectName("danger")
        self.blackout.toggled.connect(self._blackout)
        l.addWidget(QLabel("MASTER"))
        self.master = QSlider(Qt.Horizontal); self.master.setRange(0, 100); self.master.setValue(100); self.master.setFixedWidth(150)
        self.master.setStyleSheet(f"QSlider::groove:horizontal{{height:6px;background:{T.RAISED_HI};border-radius:3px}}"
                                  f"QSlider::sub-page:horizontal{{background:{T.BRAND};border-radius:3px}}"
                                  f"QSlider::handle:horizontal{{width:16px;height:16px;margin:-5px 0;border-radius:8px;background:#f5f7fa}}")
        self.master.valueChanged.connect(lambda v: setattr(self.ctl.console, "master", v / 100))
        l.addWidget(self.master); l.addWidget(self.blackout); l.addWidget(self.out_chip)
        self.menuBar().setCornerWidget(corner, Qt.TopRightCorner)

    def _build_menu(self):
        mb = self.menuBar()
        f = mb.addMenu("Fichier")
        self._act(f, "Nouveau show", self.new_show, QKeySequence.New)
        self._act(f, "Ouvrir…", self.open_show, QKeySequence.Open)
        self.recent_menu = f.addMenu("Récents"); self._fill_recent()
        f.addSeparator()
        self._act(f, "Enregistrer", self.save_show, QKeySequence.Save)
        self._act(f, "Enregistrer sous…", self.save_show_as, QKeySequence("Ctrl+Shift+S"))
        f.addSeparator(); self._act(f, "Quitter", self.close, QKeySequence.Quit)
        e = mb.addMenu("Édition")
        self._act(e, "Patch DMX", lambda: self.tabs.setCurrentWidget(self.patch_view))
        self._act(e, "Testeur DMX", lambda: self.tabs.setCurrentWidget(self.tester))
        self._act(e, "Moniteur DMX", lambda: self.tabs.setCurrentWidget(self.monitor))
        c = mb.addMenu("Connexion")
        self._act(c, "Sortie DMX…", self.open_output, QKeySequence("Ctrl+D"))
        self._act(c, "MIDI…", self.open_midi, QKeySequence("Ctrl+M"))
        a = mb.addMenu("À propos")
        self._act(a, "À propos de YouStrow", lambda: QMessageBox.about(
            self, "YouStrow", f"YouStrow — version {__version__}\nContrôleur lumière DMX.\n\n"
                             "Sorties : ENTTEC Open DMX USB (D2XX / COM), ENTTEC DMX USB PRO, Art-Net."))

    def _act(self, menu, text, slot, key=None):
        a = QAction(text, self)
        if key: a.setShortcut(key)
        a.triggered.connect(lambda *_: slot())
        menu.addAction(a); return a

    def _fill_recent(self):
        self.recent_menu.clear()
        for p in self.ctl.settings.data.get("recent", []):
            a = self.recent_menu.addAction(Path(p).name); a.triggered.connect(lambda _=False, p=p: self._open_path(p))
        self.recent_menu.setEnabled(bool(self.ctl.settings.data.get("recent")))

    # -------------------------------------------------------------- liens
    def _wire(self):
        self.pads.padClicked.connect(self._pad)
        self.pads.rowClicked.connect(self._pad_row)
        self.clear_btn.clicked.connect(self._clear)
        self.sel_all.clicked.connect(lambda: self.plan.select([f.id for f in self.ctl.console.patch.fixtures]))
        self.sel_none.clicked.connect(lambda: self.plan.select([]))
        self.plan.selectionChanged.connect(self._selection_changed)
        self.plan.fixtureMoved.connect(self.ctl.touch)
        self.hue.valueChanged.connect(self._color_changed); self.sat.valueChanged.connect(self._color_changed)
        self.dim.valueChanged.connect(self._dimmer)
        self.strobe.valueChanged.connect(self._strobe)
        self.xy.moved.connect(self._xy)

    def _targets(self):
        return sorted(self.plan.selected) or None

    def _group_ids(self, g):
        return [f.id for f in self.ctl.console.patch.fixtures if f.group == g]

    # --------------------------------------------------------------- pads
    def _sync_pads(self):
        groups = {f.group for f in self.ctl.console.patch.fixtures if f.group}
        self.pads.enabled_cols = {g - 1 for g in groups} if groups else set(range(8))
        self.pads.update()

    def _pad(self, row, col):
        g = col + 1
        ids = self._group_ids(g)
        if not ids and any(f.group for f in self.ctl.console.patch.fixtures):
            return
        on = self.pads.active.get(col) == row
        if on:
            del self.pads.active[col]
            self.ctl.console.set_color((0, 0, 0), ids or None)
        else:
            self.pads.active[col] = row
            self.ctl.console.set_color(T.PALETTE_ROWS[row][1], ids or None)
            self.ctl.console.set_dimmer(max(self.dim.value(), 0.05), ids or None)
        self.pads.update(); self.ctl.touch()

    def _pad_row(self, row):
        for c in sorted(self.pads.enabled_cols):
            self._pad_set(row, c)
        self.pads.update(); self.ctl.touch()

    def _pad_set(self, row, col):
        ids = self._group_ids(col + 1)
        self.pads.active[col] = row
        self.ctl.console.set_color(T.PALETTE_ROWS[row][1], ids or None)
        self.ctl.console.set_dimmer(max(self.dim.value(), 0.05), ids or None)

    def _clear(self):
        c = self.ctl.console
        c.stop_all_effects(); c.states.clear(); self.pads.active.clear(); self.pads.update()
        self.effects.rebuild(); self.ctl.touch()
        self.ctl.log("info", "CLEAR : tout éteint, effets arrêtés.")

    # --------------------------------------------------------- couleur etc.
    def _color_changed(self, *_):
        h, s = self.hue.value(), self.sat.value()
        rgb = tuple(round(c * 255) for c in colorsys.hsv_to_rgb(h, s, 1.0))
        self.hue_lbl.setText(f"{round(h * 360)}°"); self.sat_lbl.setText(f"{round(s * 100)}%")
        self.dim.set_stops([(0, "#000000"), (1, QColor(*rgb).name())])
        self.sat.set_stops([(0, "#ffffff"), (1, QColor.fromHsvF(min(h, .999), 1, 1).name())])
        self.ctl.console.set_color(rgb, self._targets())
        if self.dim.value() == 0: self.dim.setValue(1.0); self._dimmer(1.0)
        self.pads.active.clear(); self.pads.update(); self.ctl.touch()

    def _dimmer(self, v):
        self.dim_lbl.setText(f"{round(v * 100)}%")
        self.ctl.console.set_dimmer(v, self._targets()); self.ctl.touch()

    def _strobe(self, v):
        self.strobe_lbl.setText("off" if v < 0.02 else f"{round(v * 100)}%")
        self.ctl.console.set_strobe(0.0 if v < 0.02 else v, self._targets()); self.ctl.touch()

    def _xy(self, pan, tilt):
        self.ctl.console.set_position(pan, tilt, self._targets()); self.ctl.touch()

    def _group_level(self, g, v):
        self.ctl.console.group_levels[g] = v; self.ctl.dirty = True

    def _fx_speed(self, v):
        self.ctl.set_fx_speed(0.1 * (40 ** v))      # 0,1× … 4× (échelle exponentielle, 1× au milieu ≈ 0,63)

    def _blackout(self, on):
        self.ctl.console.blackout = on
        self.ctl.log("warn" if on else "info", "BLACKOUT " + ("activé" if on else "désactivé"))

    def _selection_changed(self, ids):
        n = len(ids)
        self.sel_lbl.setText("Aucune sélection : les réglages s'appliquent à tous les appareils." if not n else f"{n} appareil(s) sélectionné(s)")
        if n:
            st = self.ctl.console.state(ids[0])
            self.dim.setValue(st.dimmer); self.xy.set_position(st.pan, st.tilt)
            h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in st.color))
            self.hue.setValue(h); self.sat.setValue(s)

    # ---------------------------------------------------------- journal & état
    def _log(self, level, msg):
        col = {"ok": T.OK, "warn": T.WARN, "err": T.DANGER}.get(level, T.MUTED)
        self.journal.appendHtml(f'<span style="color:{col}">{msg}</span>')

    def _update_output_chip(self):
        o = self.ctl.output
        if not o:
            txt, col = "DMX : simulation", T.MUTED
        else:
            s = o.status
            txt, col = {"running": (f"DMX : {s.fps:.0f} fps", T.OK), "connecting": ("DMX : connexion…", T.WARN),
                        "error": ("DMX : erreur", T.DANGER)}.get(s.state, ("DMX : arrêté", T.MUTED))
        self.out_chip.setText("●  " + txt)
        self.out_chip.setStyleSheet(f"QPushButton{{color:{col};}}")

    def _update_title(self, path):
        name = Path(path).name if path else "Sans titre"
        self.setWindowTitle(f"YouStrow — {name}")
        self._fill_recent()

    def _on_patch_changed(self):
        self._sync_pads()
        ids = {f.id for f in self.ctl.console.patch.fixtures}
        self.plan.selected &= ids
        self.plan.update()

    # ------------------------------------------------------------- actions
    def open_output(self):
        OutputDialog(self.ctl, self).exec()

    def open_midi(self):
        MidiDialog(self.ctl, self).exec()

    # ------------------------------------------------------------ MIDI
    def apply_action(self, action: str, value: float):
        """Exécute une action venue du MIDI (thread GUI). Les faders passent par les mêmes widgets que la souris."""
        p = action.split(':')
        try:
            if action == 'master': self.master.setValue(round(value * 100))
            elif p[0] == 'group_level': self.group_faders[int(p[1]) - 1].setValue(value, True)
            elif action == 'fx_speed': self.fx_fader.setValue(value, True)
            elif action == 'dimmer': self.dim.setValue(value, True)
            elif action == 'hue': self.hue.setValue(value, True)
            elif action == 'saturation': self.sat.setValue(value, True)
            elif action == 'strobe': self.strobe.setValue(value, True)
            elif action == 'blackout': self.blackout.toggle()
            elif action == 'clear': self._clear()
            elif p[0] == 'pad': self._pad(int(p[1]), int(p[2]))
            elif p[0] == 'pad_row': self._pad_row(int(p[1]))
            elif p[0] == 'effect':
                i = int(p[1])
                if i < len(self.ctl.effects): self.effects.buttons[self.ctl.effects[i].name].click()
            elif action == 'media_play': self.media.toggle_play()
            elif action == 'media_next': self.media.next()
            elif action == 'media_prev': self.media.prev()
        except (ValueError, IndexError, KeyError):
            pass

    def _sync_leds(self):
        """Retour LED de l'APC mini (best effort : seulement si une sortie MIDI est ouverte)."""
        m = self.ctl.midi
        if not (m.connected and m.out_name and self.ctl.settings.data['midi'].get('profile') == 'apc_mini'):
            self._led_cache.clear(); return
        for r in range(8):
            for c in range(8):
                note = midi_mod.apc_pad_note(r, c)
                vel = midi_mod.LED_BY_ROW[r] if self.pads.active.get(c) == r else 0
                if self._led_cache.get(note) != vel:
                    self._led_cache[note] = vel; m.note(note, vel)

    def _confirm_discard(self) -> bool:
        if not self.ctl.dirty:
            return True
        r = QMessageBox.question(self, "YouStrow", "Enregistrer les modifications du show ?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save:
            return self.save_show()
        return r == QMessageBox.Discard

    def new_show(self):
        if self._confirm_discard():
            self.ctl.new_show(); self.effects.rebuild()

    def _open_path(self, path):
        if not self._confirm_discard():
            return
        try:
            self.ctl.open_show(path); self.effects.rebuild()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Ouvrir", str(e))

    def open_show(self):
        p, _ = QFileDialog.getOpenFileName(self, "Ouvrir un show", "", f"Show YouStrow (*{SHOW_EXT});;Tous (*)")
        if p: self._open_path(p)

    def save_show(self) -> bool:
        if not self.ctl.show_path:
            return self.save_show_as()
        try:
            self.ctl.save_show(); return True
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Enregistrer", str(e)); return False

    def save_show_as(self) -> bool:
        p, _ = QFileDialog.getSaveFileName(self, "Enregistrer le show", "", f"Show YouStrow (*{SHOW_EXT})")
        if not p: return False
        if not p.endswith(SHOW_EXT): p += SHOW_EXT
        try:
            self.ctl.save_show(p); return True
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Enregistrer", str(e)); return False

    def closeEvent(self, e):
        if not self._confirm_discard():
            e.ignore(); return
        self.media.shutdown()
        self.ctl.settings.data["geometry"] = bytes(self.saveGeometry().toBase64()).decode()
        self.ctl.shutdown()
        e.accept()
