"""Console : calcule les 4 univers DMX à partir du patch, des états d'appareils, des effets et des masters.

Aucune dépendance à Qt : l'interface ne fait qu'appeler les méthodes publiques (thread-safe)."""
from __future__ import annotations

import colorsys
import threading
import time
from dataclasses import dataclass, field

from ..fixtures.model import CHANNEL_DEFAULTS, Patch, PatchedFixture
from .effects import Effect
from .universe import DMX_CHANNELS, Universe, clamp8

UNIVERSE_COUNT = 4


@dataclass
class FixtureState:
    color: tuple[int, int, int] = (0, 0, 0)
    dimmer: float = 1.0           # 0..1
    pan: float = 0.5
    tilt: float = 0.5
    strobe: float = 0.0           # 0..1 (0 = pas de strobe)
    white: float = 0.0
    raw: dict[str, int] = field(default_factory=dict)  # valeurs brutes par type de canal (Gobo1, Zoom…)


@dataclass
class RunningEffect:
    effect: Effect
    level: float = 1.0
    speed: float = 1.0
    fixture_ids: list[int] | None = None   # None = tous
    started: float = field(default_factory=time.perf_counter)


def _channel_values(fx: PatchedFixture, st: FixtureState, dimmer: float) -> dict[str, int]:
    """Traduit un état d'appareil en valeurs de canaux (par type)."""
    r, g, b = st.color
    chans = set(fx.channels)
    out: dict[str, int] = {}
    has_rgb = {"R", "G", "B"} <= chans
    has_dim = "Dim" in chans
    scale = 1.0 if has_dim else dimmer           # sans canal Dim, le dimmer module les couleurs
    if has_rgb:
        out["R"], out["G"], out["B"] = clamp8(r * scale), clamp8(g * scale), clamp8(b * scale)
    elif {"C", "M", "Y"} <= chans:
        out["C"], out["M"], out["Y"] = clamp8((255 - r) * scale), clamp8((255 - g) * scale), clamp8((255 - b) * scale)
    if has_dim:
        # Avec mélange de couleurs, Dim = dimmer. Sinon (gradateur, lyre à roue) la « couleur » sert d'interrupteur :
        # noir = éteint, sinon intensité proportionnelle à sa luminosité maximale.
        mixes = has_rgb or {"C", "M", "Y"} <= chans
        lum = dimmer if mixes else dimmer * max(r, g, b) / 255
        out["Dim"] = clamp8(lum * 255)
    if "W" in chans:
        out["W"] = clamp8(st.white * 255 * dimmer)
    if st.strobe > 0 and "Strobe" in chans:
        out["Strobe"] = clamp8(16 + st.strobe * 239)
    for kind, val in (("Pan", st.pan), ("Tilt", st.tilt)):
        v = min(max(val, 0.0), 1.0)
        if (kind == "Pan" and fx.invert_pan) or (kind == "Tilt" and fx.invert_tilt):
            v = 1 - v
        if kind + "Fine" in chans:
            n = round(v * 65535)
            out[kind], out[kind + "Fine"] = n >> 8, n & 0xFF
        elif kind in chans:
            out[kind] = clamp8(round(v * 255))
    for k, v in st.raw.items():
        if k in chans:
            out[k] = clamp8(v)
    return out


class Console:
    def __init__(self, patch: Patch | None = None):
        self.patch = patch or Patch()
        self.universes = [Universe(i) for i in range(UNIVERSE_COUNT)]
        self.states: dict[int, FixtureState] = {}
        self.group_levels = {g: 1.0 for g in range(1, 9)}
        self.master = 1.0
        self.blackout = False
        self.running: dict[str, RunningEffect] = {}
        self.direct: dict[tuple[int, int], int] = {}
        self.tester_active = False        # le DMX Tester écrit directement : le rendu du show s'efface
        self._lock = threading.RLock()

    # ------------------------------------------------------------ état
    def state(self, fid: int) -> FixtureState:
        with self._lock:
            return self.states.setdefault(fid, FixtureState())

    def set_color(self, rgb, fixture_ids=None) -> None:
        with self._lock:
            for fx in self._targets(fixture_ids):
                self.state(fx.id).color = tuple(clamp8(c) for c in rgb)

    def set_dimmer(self, value: float, fixture_ids=None) -> None:
        with self._lock:
            for fx in self._targets(fixture_ids):
                self.state(fx.id).dimmer = min(max(value, 0.0), 1.0)

    def set_position(self, pan: float, tilt: float, fixture_ids=None) -> None:
        with self._lock:
            for fx in self._targets(fixture_ids):
                st = self.state(fx.id)
                st.pan, st.tilt = min(max(pan, 0.0), 1.0), min(max(tilt, 0.0), 1.0)

    def set_strobe(self, value: float, fixture_ids=None) -> None:
        with self._lock:
            for fx in self._targets(fixture_ids):
                self.state(fx.id).strobe = min(max(value, 0.0), 1.0)

    def set_raw(self, channel_type: str, value: int, fixture_ids=None) -> None:
        with self._lock:
            for fx in self._targets(fixture_ids):
                self.state(fx.id).raw[channel_type] = clamp8(value)

    def clear_all(self) -> None:
        with self._lock:
            self.states.clear()
            self.running.clear()
            self.direct.clear()

    def _targets(self, ids):
        return [f for f in self.patch.fixtures if ids is None or f.id in ids]

    # ---------------------------------------------------------- effets
    def start_effect(self, effect: Effect, level=1.0, speed=1.0, fixture_ids=None) -> None:
        with self._lock:
            self.running[effect.name] = RunningEffect(effect, level, speed, fixture_ids)

    def stop_effect(self, name: str) -> None:
        with self._lock:
            self.running.pop(name, None)

    def stop_all_effects(self) -> None:
        with self._lock:
            self.running.clear()

    # ------------------------------------------------- DMX direct (tester)
    def set_direct(self, universe: int, channel: int, value: int) -> None:
        with self._lock:
            self.direct[(universe, channel)] = clamp8(value)

    def release_direct(self) -> None:
        with self._lock:
            self.direct.clear()

    # ----------------------------------------------------------- rendu
    def render(self, now: float | None = None) -> None:
        now = time.perf_counter() if now is None else now
        with self._lock:
            bufs = [bytearray(DMX_CHANNELS) for _ in range(UNIVERSE_COUNT)]
            if not self.tester_active:
                fixtures = self.patch.fixtures
                n = len(fixtures)
                for idx, fx in enumerate(fixtures):
                    base = self.states.get(fx.id) or FixtureState()
                    st = FixtureState(base.color, base.dimmer, base.pan, base.tilt, base.strobe, base.white, dict(base.raw))
                    for run in self.running.values():
                        if run.fixture_ids is not None and fx.id not in run.fixture_ids:
                            continue
                        self._apply(run, st, now, idx, n)
                    level = st.dimmer * self.master * (self.group_levels.get(fx.group, 1.0) if fx.group else 1.0)
                    if self.blackout:
                        level = 0.0
                    vals = _channel_values(fx, st, level)
                    buf = bufs[fx.universe] if 0 <= fx.universe < UNIVERSE_COUNT else None
                    if buf is None:
                        continue
                    for off, ctype in enumerate(fx.channels):
                        addr = fx.address - 1 + off
                        if addr < DMX_CHANNELS:
                            buf[addr] = vals.get(ctype, CHANNEL_DEFAULTS.get(ctype, 0))
            for (u, ch), v in self.direct.items():
                if 0 <= u < UNIVERSE_COUNT and 1 <= ch <= DMX_CHANNELS:
                    bufs[u][ch - 1] = v
            if self.blackout and not self.tester_active:
                pass  # le blackout n'écrase pas les canaux « direct » du testeur
            for u, b in zip(self.universes, bufs):
                u.replace(bytes(b))

    def _apply(self, run: RunningEffect, st: FixtureState, now: float, idx: int, n: int) -> None:
        t = (now - run.started) * run.speed
        for layer in run.effect.layers:
            v = layer.value(t, idx, n)
            amt = layer.size * run.level
            tgt = layer.target
            if tgt == "dimmer":
                st.dimmer *= 1 - amt + amt * v
            elif tgt in ("red", "green", "blue"):
                i = ("red", "green", "blue").index(tgt)
                c = list(st.color); c[i] = clamp8(c[i] * (1 - amt + amt * v)); st.color = tuple(c)
            elif tgt == "hue":
                h, s, val = colorsys.rgb_to_hsv(*(c / 255 for c in st.color))
                if s == 0 and val > 0:       # blanc/gris : on colorise pour que l'arc-en-ciel soit visible
                    s = 1.0
                h = (h + amt * v) % 1.0
                st.color = tuple(clamp8(c * 255) for c in colorsys.hsv_to_rgb(h, s, val if val else 1.0))
            elif tgt == "pan":
                st.pan = min(max(st.pan + amt * (v - 0.5), 0.0), 1.0)
            elif tgt == "tilt":
                st.tilt = min(max(st.tilt + amt * (v - 0.5), 0.0), 1.0)
            elif tgt == "strobe":
                st.strobe = max(st.strobe, amt * v)


class Engine:
    """Boucle de rendu : Console -> sorties DMX (thread dédié, ~40 Hz)."""

    def __init__(self, console: Console, rate_hz: float = 40.0):
        self.console, self.rate = console, rate_hz
        self.outputs: list = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def add_output(self, out) -> None:
        self.outputs.append(out)

    def remove_output(self, out) -> None:
        if out in self.outputs:
            self.outputs.remove(out)
        out.stop(blackout=True)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="engine", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        for o in list(self.outputs):
            o.stop(blackout=True)

    def _loop(self) -> None:
        period = 1.0 / self.rate
        while not self._stop.is_set():
            t0 = time.perf_counter()
            self.console.render(t0)
            for o in self.outputs:
                for u in self.console.universes:
                    o.set_frame(u.index, u.snapshot())
            self._stop.wait(max(0.0, period - (time.perf_counter() - t0)))
