"""Effets par couches : Cible × Forme × Vitesse × Taille × Décalage × Phase.

Une couche module un paramètre d'appareil au cours du temps. Le *décalage* (spread) déphase les appareils
consécutifs (0 = tous ensemble, 1 = un cycle complet réparti sur le parc) ; la *phase* déphase toute la couche."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, asdict

SHAPES = ("sine", "triangle", "square", "saw", "ramp", "random")
TARGETS = ("dimmer", "hue", "red", "green", "blue", "pan", "tilt", "strobe")


def wave(shape: str, x: float) -> float:
    """Forme d'onde normalisée : x en cycles (réel), retour dans [0, 1]."""
    f = x - math.floor(x)
    if shape == "sine":
        return 0.5 - 0.5 * math.cos(2 * math.pi * f)
    if shape == "triangle":
        return 1 - abs(2 * f - 1)
    if shape == "square":
        return 1.0 if f < 0.5 else 0.0
    if shape == "saw":
        return f
    if shape == "ramp":
        return 1 - f
    if shape == "random":                      # échantillonné-bloqué, reproductible par cycle
        return random.Random(int(math.floor(x)) * 7919).random()
    raise ValueError(f"forme inconnue : {shape}")


@dataclass
class EffectLayer:
    target: str = "dimmer"
    shape: str = "sine"
    rate: float = 1.0       # cycles par seconde (Hz)
    size: float = 1.0       # amplitude 0..1
    spread: float = 0.0     # 0..1
    phase: float = 0.0      # 0..1

    def value(self, t: float, index: int, count: int) -> float:
        offset = self.spread * (index / max(count, 1))
        return wave(self.shape, t * self.rate + self.phase + offset)


@dataclass
class Effect:
    name: str = "Effet"
    layers: list[EffectLayer] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "layers": [asdict(l) for l in self.layers]}

    @classmethod
    def from_dict(cls, d: dict) -> "Effect":
        return cls(d.get("name", "Effet"), [EffectLayer(**l) for l in d.get("layers", [])])


def builtin_effects() -> list[Effect]:
    return [
        Effect("Pulse", [EffectLayer("dimmer", "sine", 1.0, 1.0)]),
        Effect("Chenillard", [EffectLayer("dimmer", "square", 1.0, 1.0, spread=1.0)]),
        Effect("Vague", [EffectLayer("dimmer", "sine", 0.5, 1.0, spread=1.0)]),
        Effect("Arc-en-ciel", [EffectLayer("hue", "saw", 0.2, 1.0, spread=1.0)]),
        Effect("Flash", [EffectLayer("dimmer", "square", 4.0, 1.0)]),
        Effect("Aléatoire", [EffectLayer("dimmer", "random", 3.0, 1.0, spread=1.0)]),
        Effect("Balayage", [EffectLayer("pan", "sine", 0.25, 0.5, spread=0.5)]),
        Effect("Cercle", [EffectLayer("pan", "sine", 0.3, 0.4), EffectLayer("tilt", "sine", 0.3, 0.3, phase=0.25)]),
    ]
