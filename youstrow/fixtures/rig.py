"""Matériel passif du rig : splitter DMX et pieds. Aucun n'est pilotable par logiciel — on les modélise
pour documenter le câblage (quelle sortie XLR alimente quels appareils) et signaler les erreurs de charge/hauteur."""
from __future__ import annotations

from dataclasses import dataclass

from .model import Patch


@dataclass(frozen=True)
class SplitterModel:
    name: str
    outputs: int
    notes: str


@dataclass(frozen=True)
class StandModel:
    name: str
    min_cm: int
    max_cm: int
    max_load_kg: float


# Showtec DB-1-8 : booster/splitter DMX-512 isolé, 1 entrée (XLR 3 ou 5 br.), 8 sorties XLR 3 br. + 1 thru.
SPLITTERS = {"Showtec DB-1-8": SplitterModel("Showtec DB-1-8", 8, "Entrée XLR 3/5 broches, 8 sorties XLR 3 broches isolées, 1 thru")}
# Stairville BLS-315 Pro Lighting Stand B : pied d'éclairage 150–310 cm, charge max 30 kg (fiche revendeur).
STANDS = {"BLS-315 Pro": StandModel("Stairville BLS-315 Pro", 150, 310, 30.0)}

MAX_DEVICES_PER_LINE = 32       # limite DMX-512 par ligne (32 charges unitaires)


def line_report(patch: Patch, splitter: str = "Showtec DB-1-8") -> list[str]:
    """Fiche de câblage + avertissements, une ligne de texte par information."""
    sp = SPLITTERS[splitter]
    out = [f"Splitter : {sp.name} — {sp.outputs} sorties"]
    groups: dict[int, list] = {}
    for f in patch.fixtures:
        groups.setdefault(f.line, []).append(f)
    for line in sorted(groups):
        fx = groups[line]
        label = "Ligne directe (sans splitter)" if line == 0 else f"Sortie {line}"
        chans = sum(f.footprint for f in fx)
        out.append(f"{label} : {len(fx)} appareil(s), {chans} canaux — " + ", ".join(f"{f.name} (U{f.universe + 1}.{f.address})" for f in fx))
        if len(fx) > MAX_DEVICES_PER_LINE:
            out.append(f"  ⚠ {label} : {len(fx)} appareils > {MAX_DEVICES_PER_LINE} (limite DMX par ligne)")
        if line > sp.outputs:
            out.append(f"  ⚠ Sortie {line} inexistante (le {sp.name} en a {sp.outputs})")
    free = [i for i in range(1, sp.outputs + 1) if i not in groups]
    if free:
        out.append("Sorties libres : " + ", ".join(map(str, free)))
    out.append("Rappel : un terminateur 120 Ω en bout de CHAQUE ligne de sortie utilisée.")
    return out


def stand_warnings(patch: Patch) -> list[str]:
    out = []
    for f in patch.fixtures:
        if not f.stand:
            continue
        m = STANDS.get(f.stand)
        if not m:
            out.append(f"{f.name} : pied inconnu « {f.stand} »")
        elif f.height_cm and not m.min_cm <= f.height_cm <= m.max_cm:
            out.append(f"{f.name} : hauteur {f.height_cm} cm hors plage du {m.name} ({m.min_cm}–{m.max_cm} cm)")
    return out
