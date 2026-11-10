"""Modèle de fixtures (appareils), bibliothèque et patch."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from functools import lru_cache
from pathlib import Path

RESOURCES = Path(__file__).resolve().parents[1] / "resources"

# Types de canaux (noms normalisés issus de la bibliothèque QLC+ ; défaut DMX quand non piloté)
CHANNEL_DEFAULTS: dict[str, int] = {
    "Dim": 0, "R": 0, "G": 0, "B": 0, "W": 0, "A": 0, "UV": 0, "Lime": 0, "C": 0, "M": 0, "Y": 0,
    "CTO": 0, "CTB": 0, "Strobe": 0, "Pan": 128, "PanFine": 0, "Tilt": 128, "TiltFine": 0,
    "ColorWheel": 0, "Gobo1": 0, "GoboRot": 0, "Prism": 0, "PrismRot": 0, "Zoom": 0, "Focus": 0,
    "Iris": 0, "Speed": 0, "Effect": 0, "Mode": 0, "Smoke": 0, "Fan": 0,
}
CHANNEL_LABELS_FR = {
    "Dim": "Dimmer", "R": "Rouge", "G": "Vert", "B": "Bleu", "W": "Blanc", "A": "Ambre", "UV": "UV", "Lime": "Lime",
    "C": "Cyan", "M": "Magenta", "Y": "Jaune", "CTO": "CTO", "CTB": "CTB", "Strobe": "Strobe", "Pan": "Pan",
    "PanFine": "Pan fin", "Tilt": "Tilt", "TiltFine": "Tilt fin", "ColorWheel": "Roue couleur", "Gobo1": "Gobo",
    "GoboRot": "Rotation gobo", "Prism": "Prisme", "PrismRot": "Rotation prisme", "Zoom": "Zoom", "Focus": "Focus",
    "Iris": "Iris", "Speed": "Vitesse", "Effect": "Effet", "Mode": "Mode", "Smoke": "Fumée", "Fan": "Ventilateur",
}


@dataclass(frozen=True)
class FixtureMode:
    name: str
    channels: tuple[str, ...]


@dataclass(frozen=True)
class FixtureDef:
    manufacturer: str
    model: str
    fixture_type: str
    modes: tuple[FixtureMode, ...]

    @property
    def label(self) -> str:
        return f"{self.manufacturer} {self.model}".strip()


# Appareils génériques toujours disponibles
GENERIC = (
    FixtureDef("Générique", "Dimmer", "Gradateur", (FixtureMode("1 canal", ("Dim",)),)),
    FixtureDef("Générique", "RGB", "PAR LED", (FixtureMode("3 canaux", ("R", "G", "B")),)),
    FixtureDef("Générique", "RGB + Dimmer", "PAR LED", (
        FixtureMode("4 canaux", ("Dim", "R", "G", "B")),
        FixtureMode("5 canaux (+Strobe)", ("Dim", "R", "G", "B", "Strobe")))),
    FixtureDef("Générique", "RGBW", "PAR LED", (FixtureMode("4 canaux", ("R", "G", "B", "W")),)),
    FixtureDef("Générique", "RGBW + Dimmer + Strobe", "PAR LED", (FixtureMode("6 canaux", ("Dim", "R", "G", "B", "W", "Strobe")),)),
    FixtureDef("Générique", "Lyre 8 canaux", "Moving Head", (FixtureMode("8 canaux", (
        "Pan", "Tilt", "ColorWheel", "Gobo1", "Strobe", "Dim", "Speed", "Effect")),)),
    FixtureDef("Générique", "Lyre 16 bits", "Moving Head", (FixtureMode("11 canaux", (
        "Pan", "PanFine", "Tilt", "TiltFine", "ColorWheel", "Gobo1", "Strobe", "Dim", "Speed", "Effect", "Mode")),)),
)


@lru_cache(maxsize=1)
def load_library() -> tuple[FixtureDef, ...]:
    """Bibliothèque intégrée (génériques + ~1800 appareils QLC+)."""
    defs = list(GENERIC)
    p = RESOURCES / "fixtures_qlcplus.json"
    if p.exists():
        for f in json.loads(p.read_text(encoding="utf-8")):
            modes = tuple(FixtureMode(m["name"], tuple(m["channels"])) for m in f.get("modes", []) if m.get("channels"))
            if modes:
                defs.append(FixtureDef(f.get("manufacturer", ""), f.get("model", ""), f.get("fixture_type", ""), modes))
    return tuple(defs)


def _fold(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def search_library(text: str = "", limit: int = 200) -> list[FixtureDef]:
    """Recherche multi-mots, insensible à la casse et aux accents."""
    t = _fold(text).split()
    out = [d for d in load_library() if all(w in _fold(d.label + " " + d.fixture_type) for w in t)]
    return out[:limit]


@dataclass
class PatchedFixture:
    id: int
    name: str
    channels: list[str]            # profil de canaux du mode choisi
    universe: int = 0              # 0..3
    address: int = 1               # 1..512
    x: float = 0.5                 # position sur le plan de feu (0..1)
    y: float = 0.5
    group: int = 0                 # 0 = aucun, 1..8
    fixture_type: str = ""
    model: str = ""
    mode: str = ""
    invert_pan: bool = False
    invert_tilt: bool = False
    line: int = 0                  # sortie du splitter DMX (1..8), 0 = directement sur la ligne principale
    stand: str = ""                # pied/support (voir rig.STANDS), "" = aucun
    height_cm: int = 0             # hauteur de fixation (0 = non renseignée)

    @property
    def footprint(self) -> int:
        return len(self.channels)

    @property
    def end_address(self) -> int:
        return self.address + self.footprint - 1

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PatchedFixture":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class PatchError(ValueError):
    pass


@dataclass
class Patch:
    fixtures: list[PatchedFixture] = field(default_factory=list)

    def next_id(self) -> int:
        return max((f.id for f in self.fixtures), default=0) + 1

    def conflicts(self, fx: PatchedFixture, ignore_id: int | None = None) -> list[PatchedFixture]:
        return [o for o in self.fixtures if o.id != (ignore_id if ignore_id is not None else fx.id) and o.id != fx.id
                and o.universe == fx.universe and not (o.end_address < fx.address or o.address > fx.end_address)]

    def free_address(self, universe: int, size: int) -> int | None:
        """Première adresse libre (de `universe`) pouvant contenir `size` canaux."""
        used = sorted((f.address, f.end_address) for f in self.fixtures if f.universe == universe)
        addr = 1
        for s, e in used:
            if addr + size - 1 < s:
                break
            addr = max(addr, e + 1)
        return addr if addr + size - 1 <= 512 else None

    def add(self, fx: PatchedFixture, allow_overlap: bool = False) -> PatchedFixture:
        if not 1 <= fx.address <= 512 or fx.end_address > 512:
            raise PatchError(f"{fx.name} : adresses {fx.address}-{fx.end_address} hors de 1..512")
        c = self.conflicts(fx)
        if c and not allow_overlap:
            raise PatchError(f"{fx.name} chevauche {c[0].name} (adresses {c[0].address}-{c[0].end_address})")
        self.fixtures.append(fx)
        return fx

    def remove(self, fid: int) -> None:
        self.fixtures = [f for f in self.fixtures if f.id != fid]

    def get(self, fid: int) -> PatchedFixture | None:
        return next((f for f in self.fixtures if f.id == fid), None)

    def add_many(self, definition: FixtureDef, mode: FixtureMode, count: int, universe: int, start: int | None,
                 name: str | None = None) -> list[PatchedFixture]:
        """Patche `count` appareils consécutifs (adresses contiguës, ou première place libre)."""
        out, size = [], len(mode.channels)
        addr = start if start else self.free_address(universe, size)
        for i in range(count):
            if addr is None or addr + size - 1 > 512:
                raise PatchError(f"Plus de place dans l'univers {universe + 1} pour l'appareil {i + 1}/{count}")
            fx = PatchedFixture(self.next_id(), f"{name or definition.model} {i + 1}" if count > 1 else (name or definition.model),
                                list(mode.channels), universe, addr, fixture_type=definition.fixture_type,
                                model=definition.label, mode=mode.name)
            self.add(fx)
            out.append(fx)
            addr += size
        return out

    def to_dict(self) -> dict:
        return {"fixtures": [f.to_dict() for f in self.fixtures]}

    @classmethod
    def from_dict(cls, d: dict) -> "Patch":
        return cls([PatchedFixture.from_dict(x) for x in d.get("fixtures", [])])
