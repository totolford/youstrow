"""Mémoires (pads) : un pad = un « look » enregistré (couleur/intensité/position des appareils + effets en cours).

Comportement repris de l'application d'origine :
  - grille 8 colonnes × 8 lignes, plusieurs pages ;
  - une colonne = un groupe d'appareils ; **activer une mémoire éteint celle de la même colonne** (exclusivité) ;
  - REC puis clic sur un pad vide/plein = enregistrer l'état courant dans ce pad ;
  - « charger les mémoires par défaut » = une palette de couleurs par ligne.
Aucune dépendance à Qt."""
from __future__ import annotations

from dataclasses import dataclass, field

from .console import Console, FixtureState

ROWS, COLS, DEFAULT_PAGES = 8, 8, 4
PALETTE = [("Blanc", (244, 246, 250)), ("Rouge", (255, 24, 24)), ("Orange", (255, 128, 0)), ("Jaune", (255, 214, 0)),
           ("Vert", (0, 214, 40)), ("Cyan", (0, 200, 220)), ("Bleu", (24, 40, 255)), ("Magenta", (220, 0, 220))]


@dataclass
class Memory:
    name: str = ""
    group: int | None = None                      # cible : groupe d'appareils (None = ids explicites)
    fixture_ids: list[int] = field(default_factory=list)
    states: dict[int, dict] = field(default_factory=dict)   # id -> {"color","dimmer","pan","tilt","strobe","white","raw"}
    effects: list[str] = field(default_factory=list)
    color: tuple[int, int, int] = (255, 255, 255)           # couleur d'affichage du pad

    def to_dict(self) -> dict:
        return {"name": self.name, "group": self.group, "fixture_ids": self.fixture_ids,
                "states": {str(k): v for k, v in self.states.items()}, "effects": self.effects, "color": list(self.color)}

    @classmethod
    def from_dict(cls, d: dict) -> "Memory":
        return cls(d.get("name", ""), d.get("group"), list(d.get("fixture_ids", [])),
                   {int(k): v for k, v in d.get("states", {}).items()}, list(d.get("effects", [])), tuple(d.get("color", (255, 255, 255))))


def _snap(st: FixtureState) -> dict:
    return {"color": list(st.color), "dimmer": st.dimmer, "pan": st.pan, "tilt": st.tilt, "strobe": st.strobe,
            "white": st.white, "raw": dict(st.raw)}


class MemoryBank:
    def __init__(self, pages: int = DEFAULT_PAGES):
        self.pages = pages
        self.slots: dict[tuple[int, int, int], Memory] = {}
        self.active: dict[tuple[int, int], int] = {}          # (page, col) -> row actif
        self._started: dict[tuple[int, int], list[str]] = {}  # effets lancés par la mémoire active d'une colonne

    # -------------------------------------------------------------- accès
    def get(self, page: int, row: int, col: int) -> Memory | None:
        return self.slots.get((page, row, col))

    def clear(self, page: int, row: int, col: int, console: Console | None = None) -> None:
        if self.active.get((page, col)) == row and console:
            self._deactivate(page, col, console)
        self.slots.pop((page, row, col), None)

    # ------------------------------------------------------------- cibles
    @staticmethod
    def targets(console: Console, group: int | None) -> list[int]:
        fx = console.patch.fixtures
        if group is None:
            return [f.id for f in fx]
        ids = [f.id for f in fx if f.group == group]
        return ids if ids or any(f.group for f in fx) else [f.id for f in fx]   # sans groupes définis : tous les appareils

    # ---------------------------------------------------------- enregistrer
    def store(self, page: int, row: int, col: int, console: Console, name: str = "") -> Memory:
        ids = self.targets(console, col + 1)
        states = {i: _snap(console.state(i)) for i in ids}
        first = states[ids[0]]["color"] if ids else (255, 255, 255)
        m = Memory(name or f"{page + 1}·{chr(65 + row)}{col + 1}", col + 1, ids, states,
                   [e for e in console.running], tuple(first) if max(first) > 0 else (255, 255, 255))
        self.slots[(page, row, col)] = m
        self.active[(page, col)] = row
        self._started[(page, col)] = []          # les effets enregistrés étaient DÉJÀ en cours : on ne les arrête pas
        return m

    # ------------------------------------------------------------- activer
    def recall(self, page: int, row: int, col: int, console: Console, effects_by_name: dict | None = None) -> bool:
        m = self.slots.get((page, row, col))
        if m is None:
            return False
        if self.active.get((page, col)) == row:            # re-clic sur la mémoire active = l'éteindre
            self._deactivate(page, col, console)
            return True
        self._deactivate(page, col, console)               # exclusivité par colonne
        ids = self.targets(console, m.group) if m.group is not None and not m.fixture_ids else m.fixture_ids
        for i in ids:
            s = m.states.get(i)
            if s is None and m.states:
                s = next(iter(m.states.values()))          # mémoire « par groupe » : l'état type s'applique à toute la cible
            if s is None:
                continue
            st = console.state(i)
            st.color, st.dimmer, st.pan, st.tilt = tuple(s["color"]), s["dimmer"], s["pan"], s["tilt"]
            st.strobe, st.white, st.raw = s["strobe"], s["white"], dict(s.get("raw", {}))
        started = []
        for name in m.effects:
            eff = (effects_by_name or {}).get(name)
            if eff and name not in console.running:
                console.start_effect(eff, 1.0, 1.0, ids or None)
                started.append(name)
        self._started[(page, col)] = started
        self.active[(page, col)] = row
        return True

    def _deactivate(self, page: int, col: int, console: Console) -> None:
        row = self.active.pop((page, col), None)
        for name in self._started.pop((page, col), []):
            console.stop_effect(name)
        m = self.slots.get((page, row, col)) if row is not None else None
        if m is not None:
            for i in (self.targets(console, m.group) if (m.group is not None and not m.fixture_ids) else m.fixture_ids):
                console.state(i).color = (0, 0, 0)

    def active_row(self, page: int, col: int) -> int | None:
        return self.active.get((page, col))

    # --------------------------------------------------------- par défaut
    def load_defaults(self, pages: int | None = None) -> None:
        """Palette de couleurs par ligne, une colonne par groupe (page 1)."""
        self.slots = {k: v for k, v in self.slots.items() if k[0] != 0}
        self.active = {k: v for k, v in self.active.items() if k[0] != 0}
        for r, (name, rgb) in enumerate(PALETTE):
            for c in range(COLS):
                st = {"color": list(rgb), "dimmer": 1.0, "pan": 0.5, "tilt": 0.5, "strobe": 0.0, "white": 0.0, "raw": {}}
                self.slots[(0, r, c)] = Memory(f"{name} G{c + 1}", c + 1, [], {0: st}, [], rgb)

    # ---------------------------------------------------------- sauvegarde
    def to_dict(self) -> dict:
        return {"pages": self.pages, "slots": {f"{p},{r},{c}": m.to_dict() for (p, r, c), m in self.slots.items()}}

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryBank":
        b = cls(int(d.get("pages", DEFAULT_PAGES)))
        for k, v in d.get("slots", {}).items():
            try:
                p, r, c = (int(x) for x in k.split(","))
                b.slots[(p, r, c)] = Memory.from_dict(v)
            except (ValueError, TypeError):
                continue
        return b
