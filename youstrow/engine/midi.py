"""MIDI : analyse des messages, liaisons contrôle -> action, profil AKAI APC mini, retour LED.

Aucune dépendance à Qt. `python-rtmidi` est importé à la demande ; un module factice peut être injecté (tests)."""
from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from typing import Callable

PAD_ROWS = 8
PAD_COLS = 8


class MidiError(RuntimeError):
    pass


@dataclass(frozen=True)
class MidiMsg:
    kind: str          # note_on | note_off | cc | other
    channel: int       # 1..16
    number: int        # note ou n° de contrôleur
    value: int         # vélocité ou valeur 0..127

    def describe(self) -> str:
        name = {"note_on": "Note", "note_off": "Note off", "cc": "CC"}.get(self.kind, "MIDI")
        return f"{name} {self.number} · canal {self.channel} · valeur {self.value}"


def parse(raw) -> MidiMsg:
    if not raw:
        return MidiMsg("other", 0, 0, 0)
    st, d1, d2 = (list(raw) + [0, 0])[:3]
    ch, typ = (st & 0x0F) + 1, st & 0xF0
    if typ == 0x90:
        return MidiMsg("note_on" if d2 > 0 else "note_off", ch, d1, d2)    # note on vélocité 0 = note off
    if typ == 0x80:
        return MidiMsg("note_off", ch, d1, d2)
    if typ == 0xB0:
        return MidiMsg("cc", ch, d1, d2)
    return MidiMsg("other", ch, d1, d2)


@dataclass
class Binding:
    kind: str                # "note" | "cc"
    number: int
    action: str
    channel: int | None = None   # None = n'importe quel canal

    def matches(self, m: MidiMsg) -> bool:
        if self.channel is not None and self.channel != m.channel:
            return False
        if self.kind == "note":
            return m.kind in ("note_on", "note_off") and m.number == self.number
        return m.kind == "cc" and m.number == self.number


# --- catalogue d'actions ----------------------------------------------------------------------
FADER_ACTIONS = ["master", "fx_speed", "dimmer", "hue", "saturation", "strobe"] + [f"group_level:{g}" for g in range(1, 9)]
BUTTON_ACTIONS = ["blackout", "clear"] + [f"pad_row:{r}" for r in range(PAD_ROWS)] + \
                 [f"pad:{r}:{c}" for r in range(PAD_ROWS) for c in range(PAD_COLS)] + [f"effect:{i}" for i in range(8)] + \
                 ["media_play", "media_next", "media_prev"]


def is_fader(action: str) -> bool:
    return action in FADER_ACTIONS


def action_label(action: str, effect_names: list[str] | None = None) -> str:
    base = {"master": "Master", "fx_speed": "Vitesse des effets", "dimmer": "Luminosité", "hue": "Couleur (teinte)",
            "saturation": "Saturation", "strobe": "Strobe", "blackout": "Blackout", "clear": "CLEAR",
            "media_play": "Média : lecture / pause", "media_next": "Média : suivant", "media_prev": "Média : précédent"}
    if action in base:
        return base[action]
    p = action.split(":")
    if p[0] == "group_level":
        return f"Niveau du groupe {p[1]}"
    if p[0] == "pad_row":
        return f"Ligne de pads {int(p[1]) + 1}"
    if p[0] == "pad":
        return f"Pad ligne {int(p[1]) + 1} / groupe {int(p[2]) + 1}"
    if p[0] == "effect":
        i = int(p[1])
        return f"Effet : {effect_names[i]}" if effect_names and i < len(effect_names) else f"Effet n°{i + 1}"
    return action


def resolve(bindings: list[Binding], m: MidiMsg) -> list[tuple[str, float]]:
    """Messages MIDI -> [(action, valeur 0..1)]. Un bouton ne réagit qu'à l'appui."""
    out = []
    for b in bindings:
        if not b.matches(m):
            continue
        if is_fader(b.action):
            if m.kind == "cc":
                out.append((b.action, m.value / 127.0))
        else:
            if (m.kind == "note_on") or (m.kind == "cc" and m.value >= 64):
                out.append((b.action, 1.0))
    return out


# --- profil AKAI APC mini ------------------------------------------------------------------------
APC_MINI_NAME = "APC MINI"


def apc_mini_bindings() -> list[Binding]:
    """Disposition publiée de l'APC mini (mode par défaut) : pads 8x8 = notes 0..63 en partant du bas-gauche,
    boutons de scène = notes 82..89 (haut vers bas), boutons du bas = 64..71, faders = CC 48..55, master = CC 56, Shift = 98."""
    b = []
    for r in range(PAD_ROWS):                       # r = 0 : ligne du haut
        for c in range(PAD_COLS):
            b.append(Binding("note", (PAD_ROWS - 1 - r) * 8 + c, f"pad:{r}:{c}"))
        b.append(Binding("note", 82 + r, f"pad_row:{r}"))
    b += [Binding("note", 64 + i, f"effect:{i}") for i in range(8)]
    b += [Binding("cc", 48 + g, f"group_level:{g + 1}") for g in range(8)]
    b += [Binding("cc", 56, "master"), Binding("note", 98, "blackout")]
    return b


# vélocités LED de l'APC mini : 0 éteint, 1 vert, 3 rouge, 5 jaune
LED_BY_ROW = [5, 3, 5, 5, 1, 1, 1, 3]       # blanc, rouge, orange, jaune, vert, cyan, bleu, magenta (au plus proche)


def apc_pad_note(row: int, col: int) -> int:
    return (PAD_ROWS - 1 - row) * 8 + col


def bindings_to_json(bs: list[Binding]) -> list[dict]:
    return [asdict(b) for b in bs]


def bindings_from_json(data) -> list[Binding]:
    out = []
    for d in data or []:
        try:
            out.append(Binding(str(d["kind"]), int(d["number"]), str(d["action"]), None if d.get("channel") is None else int(d["channel"])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def learn_binding(bindings: list[Binding], action: str, m: MidiMsg) -> Binding | None:
    """Associe `action` au contrôle qui vient de bouger (remplace l'ancienne liaison de l'action ET du contrôle)."""
    if m.kind == "other" or m.kind == "note_off":
        return None
    kind = "cc" if m.kind == "cc" else "note"
    if is_fader(action) and kind != "cc":
        return None                                  # un fader demande un contrôleur continu
    nb = Binding(kind, m.number, action, m.channel)
    bindings[:] = [b for b in bindings if b.action != action and not (b.kind == kind and b.number == m.number and b.channel == m.channel)]
    bindings.append(nb)
    return nb


# --- ports --------------------------------------------------------------------------------------
def _rt():
    try:
        import rtmidi
        return rtmidi
    except Exception as e:  # noqa: BLE001
        raise MidiError(f"python-rtmidi indisponible : {e}") from e


def list_inputs(rt=None) -> list[str]:
    try:
        m = (rt or _rt()).MidiIn()
        try:
            return list(m.get_ports())
        finally:
            m.delete() if hasattr(m, "delete") else None
    except MidiError:
        return []


def list_outputs(rt=None) -> list[str]:
    try:
        m = (rt or _rt()).MidiOut()
        try:
            return list(m.get_ports())
        finally:
            m.delete() if hasattr(m, "delete") else None
    except MidiError:
        return []


class MidiEngine:
    """Ouvre un port d'entrée (et optionnellement de sortie pour les LED) ; appelle `on_message(MidiMsg)`
    depuis le thread rtmidi."""

    def __init__(self, on_message: Callable[[MidiMsg], None], rt=None):
        self.on_message = on_message
        self._rt_mod = rt
        self._in = self._out = None
        self.in_name = self.out_name = ""
        self._lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self._in is not None

    def open(self, in_name: str, out_name: str = "") -> None:
        self.close()
        rt = self._rt_mod or _rt()
        mi = rt.MidiIn()
        ports = list(mi.get_ports())
        idx = next((i for i, p in enumerate(ports) if p == in_name), None)
        if idx is None:
            idx = next((i for i, p in enumerate(ports) if in_name and in_name.lower() in p.lower()), None)
        if idx is None:
            raise MidiError(f"Port MIDI d'entrée introuvable : {in_name!r} (présents : {ports})")
        try:
            mi.open_port(idx)
        except Exception as e:  # noqa: BLE001
            raise MidiError(f"Ouverture du port MIDI impossible (déjà utilisé par un autre logiciel ?) : {e}") from e
        mi.ignore_types(sysex=True, timing=True, active_sense=True)
        mi.set_callback(self._cb)
        self._in, self.in_name = mi, ports[idx]
        if out_name:
            mo = rt.MidiOut()
            oports = list(mo.get_ports())
            oidx = next((i for i, p in enumerate(oports) if p == out_name or out_name.lower() in p.lower()), None)
            if oidx is not None:
                try:
                    mo.open_port(oidx)
                    self._out, self.out_name = mo, oports[oidx]
                except Exception:  # noqa: BLE001  — le retour LED est facultatif
                    self._out = None

    def _cb(self, event, _data=None):
        try:
            self.on_message(parse(event[0]))
        except Exception:  # noqa: BLE001  — ne jamais tuer le thread rtmidi
            pass

    def send(self, status: int, d1: int, d2: int) -> None:
        with self._lock:
            if self._out is not None:
                try:
                    self._out.send_message([status, d1, d2])
                except Exception:  # noqa: BLE001
                    pass

    def note(self, note: int, velocity: int, channel: int = 1) -> None:
        self.send(0x90 | (channel - 1), note, velocity)

    def close(self) -> None:
        for m in (self._in, self._out):
            if m is not None:
                try:
                    m.cancel_callback() if hasattr(m, "cancel_callback") and m is self._in else None
                    m.close_port()
                except Exception:  # noqa: BLE001
                    pass
        self._in = self._out = None
        self.in_name = self.out_name = ""
