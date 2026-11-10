"""Contrôleur applicatif : relie moteur, sorties, persistance et interface (signaux Qt)."""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from .engine.console import Console, Engine, FixtureState
from .engine import midi as midi_mod
from .engine.effects import Effect, builtin_effects
from .engine.memories import COLS, ROWS, MemoryBank
from .engine.ftdi import FtdiError, d2xx_available, find_index, list_devices
from .engine.outputs import ArtNetOutput, DmxOutput, EnttecProOutput, OpenDmxOutput
from .engine.outputs.serial_vcp import SerialBackend
from .fixtures.model import Patch
from .storage.files import Settings, load_show, save_show

OUTPUT_TYPES = {
    "none": "Aucune (simulation)",
    "open_dmx_d2xx": "ENTTEC Open DMX USB (D2XX, recommandé)",
    "open_dmx_com": "Open DMX / clone via port COM",
    "enttec_pro": "ENTTEC DMX USB PRO",
    "artnet": "Art-Net (réseau)",
}


def make_output(cfg: dict) -> DmxOutput | None:
    t, fps = cfg.get("type", "none"), float(cfg.get("fps", 30))
    if t == "open_dmx_d2xx":
        return OpenDmxOutput("ENTTEC Open DMX USB (D2XX)", serial=cfg.get("serial") or None, fps=fps)
    if t == "open_dmx_com":
        port = cfg.get("port", "")
        return OpenDmxOutput(f"Open DMX ({port})", backend_factory=lambda: SerialBackend(port), fps=fps)
    if t == "enttec_pro":
        return EnttecProOutput(cfg.get("port", ""), fps=fps)
    if t == "artnet":
        um = {int(k): int(v) for k, v in cfg.get("universe_map", {"0": 0}).items()}
        return ArtNetOutput(f"Art-Net {cfg.get('ip', '')}", cfg.get("ip", "255.255.255.255"), um, fps)
    return None


class AppController(QObject):
    patchChanged = Signal()
    outputChanged = Signal()
    logged = Signal(str, str)         # niveau, message
    stateChanged = Signal()           # couleur/dimmer/effets modifiés
    showChanged = Signal(str)         # chemin (ou "")
    midiMessage = Signal(object)      # MidiMsg (émis depuis le thread rtmidi)
    midiChanged = Signal()            # connexion / liaisons modifiées
    midiActivity = Signal(str)        # dernier message, lisible
    actionTriggered = Signal(str, float)
    playlistChanged = Signal()
    memoriesChanged = Signal()

    def __init__(self, settings: Settings | None = None):
        super().__init__()
        self.settings = settings or Settings()
        self.console = Console(Patch())
        self.engine = Engine(self.console)
        self.output: DmxOutput | None = None
        self.effects: list[Effect] = builtin_effects()
        self.show_path = ""
        self.dirty = False
        self.fx_speed = 1.0
        self.playlist: list[dict] = []
        self.bank = MemoryBank(); self.bank.load_defaults()
        self.page = 0
        self.recording = False
        self.ext_layout: list[dict] = []
        self.learn_action: str | None = None
        self.midi = midi_mod.MidiEngine(self.midiMessage.emit)
        self.midiMessage.connect(self.handle_midi)
        self.bindings: list[midi_mod.Binding] = self._load_bindings()
        self._last_state = ""
        self._poll = QTimer(self)
        self._poll.setInterval(400)
        self._poll.timeout.connect(self._poll_output)

    # ------------------------------------------------------------ cycle de vie
    def start(self) -> None:
        self.engine.start()
        self._poll.start()
        self.log("info", "Moteur DMX démarré (40 Hz).")
        cfg = self.settings.data["output"]
        if cfg.get("autoconnect") and cfg.get("type", "none") != "none":
            self.connect_output(cfg)
        mc = self.settings.data["midi"]
        if mc.get("autoconnect") and mc.get("in"):
            try:
                self.connect_midi(mc["in"], mc.get("out", ""))
            except midi_mod.MidiError as e:
                self.log("warn", f"MIDI : {e}")
        last = self.settings.data.get("last_show")
        if last and Path(last).exists():
            try:
                self.open_show(last)
            except Exception as e:  # noqa: BLE001
                self.log("warn", f"Dernier show illisible : {e}")

    def shutdown(self) -> None:
        if getattr(self, "_down", False):
            return                      # idempotent : appelé à la fermeture de la fenêtre ET à aboutToQuit
        self._down = True
        self._poll.stop()
        self.midi.close()
        self.engine.stop()          # envoie un noir avant de couper les sorties
        self.settings.save()

    def log(self, level: str, msg: str) -> None:
        self.logged.emit(level, f"[{time.strftime('%H:%M:%S')}] {msg}")

    # ---------------------------------------------------------------- sortie
    def connect_output(self, cfg: dict) -> None:
        self.disconnect_output(log=False)
        self.settings.data["output"].update(cfg)
        out = make_output(self.settings.data["output"])
        if out is None:
            self.log("info", "Sortie DMX : aucune (simulation).")
            self.outputChanged.emit()
            return
        self.output = out
        self.engine.add_output(out)
        out.start()
        self.log("info", f"Sortie DMX : connexion à « {out.name} »…")
        self.outputChanged.emit()

    def disconnect_output(self, log: bool = True) -> None:
        if self.output:
            self.engine.remove_output(self.output)      # blackout puis arrêt
            if log:
                self.log("info", "Sortie DMX : déconnectée (noir envoyé).")
            self.output = None
            self._last_state = ""
            self.outputChanged.emit()

    def _poll_output(self) -> None:
        o = self.output
        sig = f"{o.status.state}|{o.status.message}" if o else ""
        if sig != self._last_state:
            self._last_state = sig
            if o:
                lvl = {"running": "ok", "error": "err"}.get(o.status.state, "info")
                txt = {"running": "Sortie DMX : activée", "error": f"Sortie DMX : {o.status.message}",
                       "connecting": "Sortie DMX : connexion…"}.get(o.status.state, "")
                if txt:
                    self.log(lvl, txt)
            self.outputChanged.emit()

    # ----------------------------------------------------------------- show
    def new_show(self) -> None:
        self.console.clear_all()
        self.console.patch.fixtures.clear()
        self.playlist = []
        self.bank = MemoryBank(); self.bank.load_defaults(); self.page = 0; self.recording = False; self.ext_layout = []
        self.show_path, self.dirty = "", False
        self.playlistChanged.emit(); self.memoriesChanged.emit()
        self.patchChanged.emit(); self.stateChanged.emit(); self.showChanged.emit("")

    def save_show(self, path: str | None = None) -> None:
        path = path or self.show_path
        if not path:
            raise ValueError("aucun chemin de show")
        save_show(path, self.console.patch, self.console.states, self.effects,
                  {"playlist": self.playlist, "memories": self.bank.to_dict(), "ext": self.ext_layout})
        self.show_path, self.dirty = path, False
        self.settings.add_recent(path); self.settings.save()
        self.log("ok", f"Show enregistré : {Path(path).name}")
        self.showChanged.emit(path)

    def open_show(self, path: str) -> None:
        d = load_show(path)
        patch = Patch.from_dict(d["patch"])
        self.console.clear_all()
        self.console.patch.fixtures[:] = patch.fixtures
        for fid, s in d.get("states", {}).items():
            self.console.states[int(fid)] = FixtureState(tuple(s["color"]), s["dimmer"], s["pan"], s["tilt"],
                                                         s["strobe"], s["white"], s.get("raw", {}))
        if d.get("effects"):
            self.effects = [Effect.from_dict(e) for e in d["effects"]]
        self.playlist = [x for x in d.get("playlist", []) if isinstance(x, dict) and x.get("path")]
        if d.get("memories"):
            self.bank = MemoryBank.from_dict(d["memories"])
        else:
            self.bank = MemoryBank(); self.bank.load_defaults()
        self.ext_layout = [b for b in d.get("ext", []) if isinstance(b, dict)]
        self.page = 0; self.recording = False
        self.show_path, self.dirty = path, False
        self.settings.add_recent(path)
        self.log("ok", f"Show ouvert : {Path(path).name} ({len(patch.fixtures)} appareils)")
        self.patchChanged.emit(); self.stateChanged.emit(); self.playlistChanged.emit(); self.memoriesChanged.emit(); self.showChanged.emit(path)

    def set_fx_speed(self, speed: float) -> None:
        """Vitesse globale des effets (multiplicateur), appliquée aux effets en cours."""
        self.fx_speed = speed
        for run in list(self.console.running.values()):
            now = time.perf_counter()
            # conserve la phase : on recale l'origine pour que le changement de vitesse ne fasse pas « sauter » l'effet
            elapsed = (now - run.started) * run.speed
            run.speed = speed
            run.started = now - elapsed / speed

    # ------------------------------------------------------------------ MIDI
    def _load_bindings(self):
        mc = self.settings.data["midi"]
        bs = midi_mod.bindings_from_json(mc.get("bindings"))
        if not bs and mc.get("profile", "apc_mini") == "apc_mini":
            bs = midi_mod.apc_mini_bindings()
        return bs

    def save_bindings(self) -> None:
        self.settings.data["midi"]["bindings"] = midi_mod.bindings_to_json(self.bindings)
        self.settings.save()
        self.midiChanged.emit()

    def apply_apc_profile(self) -> None:
        self.bindings = midi_mod.apc_mini_bindings()
        self.settings.data["midi"]["profile"] = "apc_mini"
        self.save_bindings()

    def connect_midi(self, in_name: str, out_name: str = "") -> None:
        self.midi.open(in_name, out_name)
        mc = self.settings.data["midi"]
        mc["in"], mc["out"] = in_name, out_name
        self.log("ok", f"MIDI : connecté à « {self.midi.in_name} »" + (f", retour LED « {self.midi.out_name} »" if self.midi.out_name else ""))
        self.midiChanged.emit()

    def disconnect_midi(self) -> None:
        self.midi.close()
        self.log("info", "MIDI : déconnecté.")
        self.midiChanged.emit()

    def start_learn(self, action: str | None) -> None:
        self.learn_action = action
        self.midiChanged.emit()

    def handle_midi(self, msg) -> None:
        """Thread GUI : apprentissage, sinon routage vers les actions."""
        if msg.kind != "other":
            self.midiActivity.emit(msg.describe())
        if self.learn_action:
            b = midi_mod.learn_binding(self.bindings, self.learn_action, msg)
            if b:
                self.log("ok", f"MIDI : {midi_mod.action_label(b.action)} ← {msg.describe()}")
                self.learn_action = None
                self.settings.data["midi"]["profile"] = "custom"
                self.save_bindings()
            return
        for action, value in midi_mod.resolve(self.bindings, msg):
            self.actionTriggered.emit(action, value)

    # ------------------------------------------------------------- mémoires / pads
    def effects_by_name(self) -> dict:
        return {e.name: e for e in self.effects}

    def pad_press(self, row: int, col: int) -> None:
        if self.recording:
            m = self.bank.store(self.page, row, col, self.console)
            self.recording = False
            self.log("ok", f"Mémoire {m.name} enregistrée ({len(m.fixture_ids)} appareil(s), {len(m.effects)} effet(s))")
        elif not self.bank.recall(self.page, row, col, self.console, self.effects_by_name()):
            self.log("info", "Pad vide : activez REC puis cliquez le pad pour y enregistrer l'état courant.")
        self.touch(); self.memoriesChanged.emit()

    def pad_clear(self, row: int, col: int) -> None:
        if self.bank.get(self.page, row, col):
            self.bank.clear(self.page, row, col, self.console)
            self.log("info", "Mémoire effacée."); self.touch(); self.memoriesChanged.emit()

    def row_press(self, row: int) -> None:
        for c in range(COLS):
            if self.bank.get(self.page, row, c) and self.bank.active_row(self.page, c) != row:
                self.bank.recall(self.page, row, c, self.console, self.effects_by_name())
        self.touch(); self.memoriesChanged.emit()

    def toggle_rec(self) -> None:
        self.recording = not self.recording
        self.log("warn" if self.recording else "info", "REC : cliquez un pad pour y enregistrer l'état courant." if self.recording else "REC annulé.")
        self.memoriesChanged.emit()

    def set_page(self, page: int) -> None:
        self.page = min(max(page, 0), self.bank.pages - 1); self.memoriesChanged.emit()

    def touch(self) -> None:
        self.dirty = True
        self.stateChanged.emit()

    def patch_touch(self) -> None:
        self.dirty = True
        self.patchChanged.emit()


def detect_hardware() -> dict:
    """Instantané du matériel DMX détectable (D2XX + ports COM) — pour l'assistant de connexion."""
    from .engine.outputs.serial_vcp import list_com_ports
    return {"d2xx_available": d2xx_available(), "ftdi": list_devices(), "com": list_com_ports()}
