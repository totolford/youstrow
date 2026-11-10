"""Fenêtre principale — structure de la maquette Figma « YouStrow — UI » :
rail de navigation (Live · 3D · Média · Patch · EXT · DMX) + barre supérieure (menus, état, master, blackout)
+ espace de travail. Chaque grand panneau peut être détaché sur un autre écran (menu Affichage ▸ Fenêtres externes)."""
from __future__ import annotations

import colorsys
from functools import partial
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QKeySequence, QLinearGradient, QPainter
from PySide6.QtWidgets import (QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenuBar, QMessageBox,
                               QPlainTextEdit, QPushButton, QSlider, QStackedWidget, QTabWidget, QToolButton, QVBoxLayout, QWidget)

from .. import __version__
from ..controller import AppController
from ..engine import midi as midi_mod
from ..storage.files import SHOW_EXT
from . import theme as T
from .dmx_tools import DmxMonitor, DmxTester
from .effects_panel import EffectsPanel
from .ext_surface import ExtSurface
from .icons import icon
from .media_panel import MediaPanel
from .memory_pads import MemoryPanel
from .midi_dialog import MidiDialog
from .output_dialog import OutputDialog
from .panels import PanelHost, all_screens, place_on_screen, screen_label
from .patch_view import PatchView
from .plan3d import Plan3DPanel
from .rig_panel import RigPanel
from .widgets import Fader, GradientSlider, PositionPad, StagePlan

WORKSPACES = [("live", "LIVE", "zap"), ("3d", "3D", "cube"), ("media", "MÉDIA", "video"), ("patch", "PATCH", "list"),
              ("ext", "EXT", "grid"), ("dmx", "DMX", "sliders")]


class _Logo(QWidget):
    def __init__(self):
        super().__init__(); self.setFixedSize(44, 44)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        g = QLinearGradient(0, 0, 44, 44); g.setColorAt(0, QColor(T.BRAND)); g.setColorAt(1, QColor(T.DANGER))
        p.setPen(Qt.NoPen); p.setBrush(g); p.drawRoundedRect(self.rect(), 12, 12)
        p.setPen(QColor(T.BG)); f = p.font(); f.setBold(True); f.setPointSize(11); p.setFont(f); p.drawText(self.rect(), Qt.AlignCenter, "YS")


def card(title: str = "", actions=()) -> tuple[QFrame, QVBoxLayout]:
    f = QFrame(); f.setObjectName("card")
    l = QVBoxLayout(f); l.setContentsMargins(16, 14, 16, 14); l.setSpacing(12)
    if title or actions:
        h = QHBoxLayout(); h.setSpacing(8)
        t = QLabel(title); t.setObjectName("section"); h.addWidget(t); h.addStretch(1)
        for a in actions:
            h.addWidget(a)
        l.addLayout(h)
    return f, l


def popout_btn(slot) -> QPushButton:
    b = QPushButton(); b.setObjectName("ghost"); b.setIcon(icon("popout", T.TEXT2, 16)); b.setFixedSize(30, 28); b.setToolTip("Détacher sur un autre écran"); b.clicked.connect(slot)
    return b


class MainWindow(QMainWindow):
    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        self.setWindowTitle("YouStrow"); self.resize(1600, 940); self.setMinimumSize(1366, 780)
        self.hosts: list[PanelHost] = []
        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        outer = QHBoxLayout(root); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        self._build_rail(outer)
        right = QVBoxLayout(); right.setSpacing(0); outer.addLayout(right, 1)
        self._build_topbar(right)
        self.stack = QStackedWidget(); right.addWidget(self.stack, 1)
        self._build_live(); self._build_3d(); self._build_media(); self._build_patch(); self._build_ext(); self._build_dmx()
        self._build_menus()
        self._wire()
        self.goto("live")
        self._led_cache: dict[int, int] = {}
        self._sync_t = QTimer(self); self._sync_t.setInterval(200); self._sync_t.timeout.connect(self._sync); self._sync_t.start()
        ctl.logged.connect(self._log); ctl.outputChanged.connect(self._update_chips); ctl.midiChanged.connect(self._update_chips)
        ctl.showChanged.connect(self._update_title); ctl.patchChanged.connect(self._on_patch_changed)
        ctl.actionTriggered.connect(self.apply_action); ctl.stateChanged.connect(self.effects.sync)
        self.effects.effectsChanged.connect(self.media._refresh_light_cells)
        self._update_chips(); self._update_title(""); self._on_patch_changed()

    # ============================================================ structure
    def _build_rail(self, outer):
        rail = QFrame(); rail.setObjectName("rail"); rail.setFixedWidth(72)
        l = QVBoxLayout(rail); l.setContentsMargins(8, 16, 8, 8); l.setSpacing(6); l.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        l.addWidget(_Logo(), 0, Qt.AlignHCenter); l.addSpacing(12)
        self.nav, self.nav_group = {}, QButtonGroup(self); self.nav_group.setExclusive(True)
        for code, label, ic in WORKSPACES:
            b = QToolButton(); b.setText(label); b.setObjectName("nav"); b.setCheckable(True); b.setFixedSize(56, 58)
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon); b.setIcon(icon(ic, T.MUTED, 22)); b.setIconSize(QSize(22, 22))
            b.clicked.connect(partial(self.goto, code)); self.nav_group.addButton(b); l.addWidget(b); self.nav[code] = (b, ic)
        outer.addWidget(rail)

    def _build_topbar(self, right):
        top = QFrame(); top.setObjectName("topbar"); top.setFixedHeight(56)
        h = QHBoxLayout(top); h.setContentsMargins(12, 0, 16, 0); h.setSpacing(14)
        self.menubar = QMenuBar(); h.addWidget(self.menubar); h.addStretch(1)
        self.show_lbl = QLabel(""); self.show_lbl.setObjectName("muted"); h.addWidget(self.show_lbl)
        self.out_chip = QPushButton(); self.out_chip.setObjectName("ghost"); self.out_chip.clicked.connect(self.open_output); self.out_chip.setToolTip("Sortie DMX…")
        self.midi_chip = QPushButton(); self.midi_chip.setObjectName("ghost"); self.midi_chip.clicked.connect(self.open_midi); self.midi_chip.setToolTip("MIDI…")
        h.addWidget(self.out_chip); h.addWidget(self.midi_chip)
        m = QLabel("MASTER"); m.setObjectName("section"); h.addWidget(m)
        self.master = QSlider(Qt.Horizontal); self.master.setRange(0, 100); self.master.setValue(100); self.master.setFixedWidth(150)
        self.master.setStyleSheet(f"QSlider::groove:horizontal{{height:6px;background:{T.RAISED_HI};border-radius:3px}}"
                                  f"QSlider::sub-page:horizontal{{background:{T.BRAND};border-radius:3px}}"
                                  f"QSlider::handle:horizontal{{width:16px;height:16px;margin:-5px 0;border-radius:8px;background:#f5f7fa}}")
        h.addWidget(self.master)
        self.blackout = QPushButton("Blackout"); self.blackout.setObjectName("danger"); self.blackout.setCheckable(True); h.addWidget(self.blackout)
        right.addWidget(top)

    def _host(self, name, widget) -> PanelHost:
        h = PanelHost(name, widget); self.hosts.append(h); return h

    # ------------------------------------------------------------ LIVE
    def _build_live(self):
        page = QWidget(); lay = QHBoxLayout(page); lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(16)
        # colonne 1 : mémoires + journal
        c1 = QVBoxLayout(); c1.setSpacing(16)
        self.memories = MemoryPanel(self.ctl); h_mem = self._host("Mémoires (pads)", self.memories); c1.addWidget(h_mem)
        self.journal = QPlainTextEdit(); self.journal.setReadOnly(True); self.journal.setMaximumBlockCount(500)
        jc, jl = card("JOURNAL", [popout_btn(lambda: self.detach(self.h_journal))]); jl.addWidget(self.journal, 1)
        self.h_journal = self._host("Journal", jc); c1.addWidget(self.h_journal, 1)
        w1 = QWidget(); w1.setLayout(c1); w1.setFixedWidth(408); lay.addWidget(w1)
        self.memories_popout = popout_btn(lambda: self.detach(h_mem))
        # colonne 2 : plan + faders
        c2 = QVBoxLayout(); c2.setSpacing(16)
        self.plan = StagePlan(self.ctl)
        self.btn_all, self.btn_none = QPushButton("Tout"), QPushButton("Désélec."); [b.setObjectName("ghost") for b in (self.btn_all, self.btn_none)]
        seg = QFrame(); sl = QHBoxLayout(seg); sl.setContentsMargins(3, 3, 3, 3); sl.setSpacing(2)
        seg.setStyleSheet(f"QFrame{{background:{T.RAISED};border:1px solid {T.BORDER};border-radius:10px;}} QPushButton{{border:none;border-radius:8px;padding:5px 14px;background:transparent;color:{T.MUTED};}}")
        b2d = QPushButton("2D"); b2d.setStyleSheet(f"background:{T.ACCENT_DIM};color:{T.ACCENT};"); b3d = QPushButton("3D"); b3d.clicked.connect(lambda: self.goto("3d")); sl.addWidget(b2d); sl.addWidget(b3d)
        pc, pl = card("PLAN DE FEU · TEMPS RÉEL", [self.btn_all, self.btn_none, seg, popout_btn(lambda: self.detach(self.h_plan))])
        pl.addWidget(self.plan, 1)
        self.sel_lbl = QLabel("Aucune sélection : les réglages s'appliquent à tous les appareils."); self.sel_lbl.setObjectName("muted"); pl.addWidget(self.sel_lbl)
        self.h_plan = self._host("Plan de feu", pc); c2.addWidget(self.h_plan, 1)
        fc, fl = card("NIVEAUX DES GROUPES · VITESSE FX")
        fr = QHBoxLayout(); fr.setSpacing(0); self.group_faders = []
        for g in range(1, 9):
            f = Fader(f"G{g}", T.ACCENT, 1.0, 1.0); f.setMinimumHeight(150); f.valueChanged.connect(partial(self._group_level, g)); fr.addWidget(f); self.group_faders.append(f)
        self.fx_fader = Fader("FX", T.BRAND, 0.5, 0.5); self.fx_fader.setMinimumHeight(150); self.fx_fader.valueChanged.connect(self._fx_speed); fr.addSpacing(8); fr.addWidget(self.fx_fader)
        fl.addLayout(fr)
        c2.addWidget(fc)
        lay.addLayout(c2, 1)
        # colonne 3 : couleur + effets
        c3 = QVBoxLayout(); c3.setSpacing(16)
        cc, cl = card("COULEUR · INTENSITÉ")
        def labelled(name):
            r = QHBoxLayout(); r.addWidget(QLabel(name)); r.addStretch(1); v = QLabel(""); v.setObjectName("muted"); r.addWidget(v); cl.addLayout(r); return v
        self.hue_lbl = labelled("Teinte"); self.hue = GradientSlider([(i / 6, QColor.fromHsvF(i / 6 if i < 6 else 0.999, 1, 1).name()) for i in range(7)]); cl.addWidget(self.hue)
        self.sat_lbl = labelled("Saturation"); self.sat = GradientSlider([(0, "#ffffff"), (1, "#ff0000")]); self.sat.setValue(1.0); cl.addWidget(self.sat)
        self.dim_lbl = labelled("Luminosité"); self.dim = GradientSlider([(0, "#000000"), (1, "#ff0000")]); self.dim.setValue(1.0); cl.addWidget(self.dim)
        self.strobe_lbl = labelled("Strobe"); self.strobe = GradientSlider([(0, T.BORDER), (1, "#ffffff")]); cl.addWidget(self.strobe)
        self.hue_lbl.setText("0°"); self.sat_lbl.setText("100%"); self.dim_lbl.setText("100%"); self.strobe_lbl.setText("off")
        pr = QHBoxLayout(); pr.setSpacing(14)
        self.xy = PositionPad(); self.xy.setFixedSize(132, 132); pr.addWidget(self.xy)
        pt = QVBoxLayout(); t = QLabel("PAN / TILT"); t.setObjectName("section"); pt.addWidget(t)
        d = QLabel("Glissez le point pour pointer les lyres. Double-clic : centre."); d.setObjectName("muted"); d.setWordWrap(True); pt.addWidget(d); pt.addStretch(1); pr.addLayout(pt, 1)
        cl.addLayout(pr)
        c3.addWidget(cc)
        ec, el = card("")
        self.effects = EffectsPanel(self.ctl, lambda: sorted(self.plan.selected)); el.addWidget(self.effects)
        self.h_effects = self._host("Effets", ec); c3.addWidget(self.h_effects); c3.addStretch(1)
        w3 = QWidget(); w3.setLayout(c3); w3.setFixedWidth(400); lay.addWidget(w3)
        self.stack.addWidget(page)

    # ------------------------------------------------------------ 3D / Média / Patch / EXT / DMX
    def _page(self, widget, margins=16):
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(margins, margins, margins, margins); l.addWidget(widget); self.stack.addWidget(w); return w

    def _build_3d(self):
        self.p3d = Plan3DPanel(self.ctl); self.h_3d = self._host("Plan 3D", self.p3d); self._page(self.h_3d)
        self.p3d.detach_btn.clicked.connect(lambda: self.detach(self.h_3d)); self.p3d.full_btn.clicked.connect(lambda: self.detach(self.h_3d, fullscreen=True))
        saved = self.ctl.settings.data.get("scene3d")
        if saved:
            self.p3d._mark(saved)
            if self.p3d.view is not None:
                self.p3d.view.pending_scene = saved

    def _build_media(self):
        self.media = MediaPanel(self.ctl); self.h_media = self._host("Média", self.media); self._page(self.h_media)

    def _build_patch(self):
        w = QWidget(); l = QHBoxLayout(w); l.setContentsMargins(16, 16, 16, 16); l.setSpacing(16)
        self.patch_view = PatchView(self.ctl); l.addWidget(self.patch_view, 1)
        rig = RigPanel(self.ctl); rig.setFixedWidth(420); l.addWidget(rig)
        self.stack.addWidget(w)

    def _build_ext(self):
        self.ext = ExtSurface(self.ctl)
        c, l = card("SURFACE EXT · EXÉCUTEURS", [popout_btn(lambda: self.detach(self.h_ext))]); l.addWidget(self.ext, 1)
        self.h_ext = self._host("Surface EXT", c); self._page(self.h_ext)

    def _build_dmx(self):
        self.tabs = QTabWidget()
        self.tester = DmxTester(self.ctl); self.tabs.addTab(self.tester, "Testeur DMX")
        self.monitor = DmxMonitor(self.ctl); self.tabs.addTab(self.monitor, "Moniteur DMX")
        c, l = card(); l.addWidget(self.tabs); self._page(c)

    # ============================================================ menus
    def _act(self, menu, text, slot, key=None):
        a = QAction(text, self)
        if key:
            a.setShortcut(key)
        a.triggered.connect(lambda *_: slot()); menu.addAction(a); self.addAction(a); return a

    def _build_menus(self):
        mb = self.menubar
        f = mb.addMenu("Fichier")
        self._act(f, "Nouveau show", self.new_show, QKeySequence.New); self._act(f, "Ouvrir…", self.open_show, QKeySequence.Open)
        self.recent_menu = f.addMenu("Récents"); self._fill_recent(); f.addSeparator()
        self._act(f, "Enregistrer", self.save_show, QKeySequence.Save); self._act(f, "Enregistrer sous…", self.save_show_as, QKeySequence("Ctrl+Shift+S"))
        f.addSeparator(); self._act(f, "Charger les mémoires par défaut", self.default_memories); f.addSeparator(); self._act(f, "Quitter", self.close, QKeySequence.Quit)
        e = mb.addMenu("Édition")
        self._act(e, "Patch DMX", lambda: self.goto("patch")); self._act(e, "Testeur DMX", lambda: (self.goto("dmx"), self.tabs.setCurrentWidget(self.tester)))
        self._act(e, "Moniteur DMX", lambda: (self.goto("dmx"), self.tabs.setCurrentWidget(self.monitor)))
        c = mb.addMenu("Connexion")
        self._act(c, "Sortie DMX…", self.open_output, QKeySequence("Ctrl+D")); self._act(c, "MIDI…", self.open_midi, QKeySequence("Ctrl+M"))
        self.menu_view = mb.addMenu("Affichage")
        self.ws_actions = {}
        for i, (code, label, _ic) in enumerate(WORKSPACES):
            a = QAction({"live": "Live — pads, plan de feu, faders", "3d": "Plan 3D", "media": "Média — playlist & vidéo", "patch": "Patch & Rig",
                         "ext": "Surface EXT (pads / exécuteurs)", "dmx": "Testeur & Moniteur DMX"}[code], self)
            a.setShortcut(QKeySequence(f"Ctrl+{i + 1}")); a.setCheckable(True); a.triggered.connect(partial(self.goto, code)); self.addAction(a); self.ws_actions[code] = a
        self.act_full = QAction("Fenêtre principale en plein écran", self); self.act_full.setShortcut(QKeySequence("F11")); self.act_full.triggered.connect(self.toggle_fullscreen); self.addAction(self.act_full)
        self.menu_view.aboutToShow.connect(self._fill_view_menu)
        a = mb.addMenu("À propos")
        self._act(a, "À propos de YouStrow", lambda: QMessageBox.about(self, "YouStrow", f"YouStrow — version {__version__}\nContrôleur lumière DMX.\n\n"
                                                                        "Sorties : ENTTEC Open DMX USB (D2XX / COM), ENTTEC DMX USB PRO, Art-Net."))

    def _fill_view_menu(self):
        m = self.menu_view; m.clear()
        m.addSection("Espace de travail")
        for code, _l, _i in WORKSPACES:
            self.ws_actions[code].setChecked(self.stack.currentIndex() == [c for c, *_ in WORKSPACES].index(code)); m.addAction(self.ws_actions[code])
        m.addSeparator(); m.addSection("Fenêtres externes")
        screens = all_screens()
        for h in self.hosts:
            sub = m.addMenu(("● " if h.is_detached else "") + h.name)
            if h.is_detached:
                sub.addAction("Rapatrier dans la fenêtre principale", h.attach); sub.addSeparator()
            for i, s in enumerate(screens):
                sub.addAction(f"{screen_label(i, s)} — fenêtre", partial(h.detach, s, False))
                sub.addAction(f"{screen_label(i, s)} — plein écran", partial(h.detach, s, True))
        m.addAction("Tout rapatrier", self.attach_all)
        m.addSeparator(); m.addAction(self.act_full)

    def toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def attach_all(self):
        for h in self.hosts:
            h.attach()

    def detach(self, host: PanelHost, fullscreen: bool = False):
        """Détache sur l'écran secondaire s'il existe, sinon sur l'écran courant."""
        sc = all_screens()
        host.detach(sc[1] if len(sc) > 1 else sc[0], fullscreen)

    def _fill_recent(self):
        self.recent_menu.clear()
        for p in self.ctl.settings.data.get("recent", []):
            a = self.recent_menu.addAction(Path(p).name); a.triggered.connect(lambda _=False, p=p: self._open_path(p))
        self.recent_menu.setEnabled(bool(self.ctl.settings.data.get("recent")))

    # ============================================================ navigation
    def goto(self, code: str):
        idx = [c for c, *_ in WORKSPACES].index(code)
        self.stack.setCurrentIndex(idx)
        for c, (b, ic) in self.nav.items():
            b.setChecked(c == code); b.setIcon(icon(ic, T.ACCENT if c == code else T.MUTED, 22))

    # ============================================================ liens
    def _wire(self):
        self.btn_all.clicked.connect(lambda: self.plan.select([f.id for f in self.ctl.console.patch.fixtures]))
        self.btn_none.clicked.connect(lambda: self.plan.select([]))
        self.plan.selectionChanged.connect(self._selection_changed); self.plan.fixtureMoved.connect(self.ctl.touch)
        self.hue.valueChanged.connect(self._color_changed); self.sat.valueChanged.connect(self._color_changed)
        self.dim.valueChanged.connect(self._dimmer); self.strobe.valueChanged.connect(self._strobe); self.xy.moved.connect(self._xy)
        self.master.valueChanged.connect(lambda v: setattr(self.ctl.console, "master", v / 100))
        self.blackout.toggled.connect(self._blackout)

    def _targets(self):
        return sorted(self.plan.selected) or None

    # -------------------------------------------------------------- pads / MIDI
    def _pad(self, row, col):
        self.ctl.pad_press(row, col)

    def _pad_row(self, row):
        self.ctl.row_press(row)

    def _clear(self):
        c = self.ctl.console
        c.stop_all_effects(); c.states.clear(); self.ctl.bank.active.clear(); self.ctl.bank._started.clear()
        self.effects.rebuild(); self.ctl.touch(); self.ctl.memoriesChanged.emit()
        self.ctl.log("info", "CLEAR : tout éteint, effets arrêtés.")

    def default_memories(self):
        self.ctl.bank.load_defaults(); self.ctl.memoriesChanged.emit(); self.ctl.log("ok", "Mémoires par défaut chargées (palette de couleurs, page 1).")

    def apply_action(self, action: str, value: float):
        p = action.split(":")
        try:
            if action == "master": self.master.setValue(round(value * 100))
            elif p[0] == "group_level": self.group_faders[int(p[1]) - 1].setValue(value, True)
            elif action == "fx_speed": self.fx_fader.setValue(value, True)
            elif action == "dimmer": self.dim.setValue(value, True)
            elif action == "hue": self.hue.setValue(value, True)
            elif action == "saturation": self.sat.setValue(value, True)
            elif action == "strobe": self.strobe.setValue(value, True)
            elif action == "blackout": self.blackout.toggle()
            elif action == "clear": self._clear()
            elif p[0] == "pad": self._pad(int(p[1]), int(p[2]))
            elif p[0] == "pad_row": self._pad_row(int(p[1]))
            elif p[0] == "effect":
                i = int(p[1])
                if i < len(self.ctl.effects): self.effects.buttons[self.ctl.effects[i].name].click()
            elif action == "media_play": self.media.toggle_play()
            elif action == "media_next": self.media.next()
            elif action == "media_prev": self.media.prev()
        except (ValueError, IndexError, KeyError):
            pass

    def _sync(self):
        c = self.ctl.console
        if self.blackout.isChecked() != c.blackout:
            self.blackout.blockSignals(True); self.blackout.setChecked(c.blackout); self.blackout.blockSignals(False)
        if self.master.value() != round(c.master * 100) and not self.master.isSliderDown():
            self.master.blockSignals(True); self.master.setValue(round(c.master * 100)); self.master.blockSignals(False)
        m = self.ctl.midi
        if not (m.connected and m.out_name and self.ctl.settings.data["midi"].get("profile") == "apc_mini"):
            self._led_cache.clear(); return
        for r in range(8):
            for col in range(8):
                note = midi_mod.apc_pad_note(r, col)
                vel = midi_mod.LED_BY_ROW[r] if self.ctl.bank.active_row(self.ctl.page, col) == r else 0
                if self._led_cache.get(note) != vel:
                    self._led_cache[note] = vel; m.note(note, vel)

    # -------------------------------------------------------- couleur etc.
    def _color_changed(self, *_):
        h, s = self.hue.value(), self.sat.value()
        rgb = tuple(round(c * 255) for c in colorsys.hsv_to_rgb(h, s, 1.0))
        self.hue_lbl.setText(f"{round(h * 360)}°"); self.sat_lbl.setText(f"{round(s * 100)}%")
        self.dim.set_stops([(0, "#000000"), (1, QColor(*rgb).name())]); self.sat.set_stops([(0, "#ffffff"), (1, QColor.fromHsvF(min(h, .999), 1, 1).name())])
        self.ctl.console.set_color(rgb, self._targets())
        if self.dim.value() == 0: self.dim.setValue(1.0); self._dimmer(1.0)
        self.ctl.touch()

    def _dimmer(self, v):
        self.dim_lbl.setText(f"{round(v * 100)}%"); self.ctl.console.set_dimmer(v, self._targets()); self.ctl.touch()

    def _strobe(self, v):
        self.strobe_lbl.setText("off" if v < 0.02 else f"{round(v * 100)}%"); self.ctl.console.set_strobe(0.0 if v < 0.02 else v, self._targets()); self.ctl.touch()

    def _xy(self, pan, tilt):
        self.ctl.console.set_position(pan, tilt, self._targets()); self.ctl.touch()

    def _group_level(self, g, v):
        self.ctl.console.group_levels[g] = v; self.ctl.dirty = True

    def _fx_speed(self, v):
        self.ctl.set_fx_speed(0.1 * (40 ** v))

    def _blackout(self, on):
        self.ctl.console.blackout = on; self.ctl.log("warn" if on else "info", "BLACKOUT " + ("activé" if on else "désactivé"))

    def _selection_changed(self, ids):
        n = len(ids)
        self.sel_lbl.setText("Aucune sélection : les réglages s'appliquent à tous les appareils." if not n else f"{n} appareil(s) sélectionné(s)")
        if n:
            st = self.ctl.console.state(ids[0])
            self.dim.setValue(st.dimmer); self.xy.set_position(st.pan, st.tilt)
            h, s, _v = colorsys.rgb_to_hsv(*(c / 255 for c in st.color)); self.hue.setValue(h); self.sat.setValue(s)

    # -------------------------------------------------------- état / journal
    def _log(self, level, msg):
        col = {"ok": T.OK, "warn": T.WARN, "err": T.DANGER}.get(level, T.TEXT2)
        self.journal.appendHtml(f'<span style="color:{col}">{msg}</span>')

    def _update_chips(self):
        o = self.ctl.output
        if not o:
            txt, col = "DMX : simulation", T.MUTED
        else:
            s = o.status
            txt, col = {"running": (f"DMX · {s.fps:.0f} fps", T.OK), "connecting": ("DMX : connexion…", T.WARN), "error": ("DMX : erreur", T.DANGER)}.get(s.state, ("DMX : arrêté", T.MUTED))
        self.out_chip.setText("●  " + txt); self.out_chip.setStyleSheet(f"QPushButton{{color:{col};border:1px solid {T.BORDER};border-radius:999px;padding:5px 12px;}}")
        mc = self.ctl.midi
        t2, c2 = (f"MIDI · {mc.in_name}", T.OK) if mc.connected else ("MIDI : —", T.MUTED)
        self.midi_chip.setText("●  " + t2); self.midi_chip.setStyleSheet(f"QPushButton{{color:{c2};border:1px solid {T.BORDER};border-radius:999px;padding:5px 12px;}}")

    def _update_title(self, path):
        name = Path(path).name if path else "Sans titre"
        self.setWindowTitle(f"YouStrow — {name}"); self.show_lbl.setText(name); self._fill_recent()

    def _on_patch_changed(self):
        ids = {f.id for f in self.ctl.console.patch.fixtures}
        self.plan.selected &= ids; self.plan.update()

    # ============================================================ actions fichier
    def open_output(self):
        OutputDialog(self.ctl, self).exec()

    def open_midi(self):
        MidiDialog(self.ctl, self).exec()

    def _confirm_discard(self) -> bool:
        if not self.ctl.dirty:
            return True
        r = QMessageBox.question(self, "YouStrow", "Enregistrer les modifications du show ?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        return self.save_show() if r == QMessageBox.Save else r == QMessageBox.Discard

    def new_show(self):
        if self._confirm_discard():
            self.ctl.new_show(); self.effects.rebuild()

    def _open_path(self, path):
        if not self._confirm_discard():
            return
        try:
            self.ctl.open_show(path); self.effects.rebuild(); self.ext.reload()
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
        self.attach_all()
        self.media.shutdown()
        self.ctl.settings.data["geometry"] = bytes(self.saveGeometry().toBase64()).decode()
        self.ctl.shutdown()
        e.accept()
