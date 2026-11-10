"""ENTTEC Open DMX USB (FT232R « passif ») et clones.

L'Open DMX n'a aucune électronique de protocole : c'est au PC de fabriquer
BREAK + MAB + trame, en continu. Séquence émise à chaque trame :

    BREAK  (ligne TX à 0, >= 88 µs)   -> FT_SetBreakOn / pause / FT_SetBreakOff
    MAB    (ligne à 1, >= 8 µs)
    START CODE 0x00 + 512 canaux, 250 000 bauds, 8 bits, 2 stop, sans parité

Une trame = 513 octets x 11 bits x 4 µs ≈ 22,6 ms, donc 44 fps maximum ; 30 fps par défaut.
Les durées réelles du break/MAB sont arrondies par le bus USB (~1 ms) : c'est normal et accepté par les
récepteurs DMX (le break max toléré est de 1 s).
"""
from __future__ import annotations

from typing import Callable

from ..ftdi import D2xxBackend, FtdiBackend, FtdiError, find_index
from .base import DmxOutput, precise_sleep

BREAK_S = 0.000120
MAB_S = 0.000020


class OpenDmxOutput(DmxOutput):
    kind = "open_dmx"

    def __init__(self, name="ENTTEC Open DMX USB", backend_factory: Callable[[], FtdiBackend] | None = None,
                 serial: str | None = None, universe: int = 0, fps: float = 30.0,
                 break_s: float = BREAK_S, mab_s: float = MAB_S):
        super().__init__(name, min(fps, 44.0))
        self.serial = serial
        self.universe = universe
        self.break_s, self.mab_s = break_s, mab_s
        self._factory = backend_factory or self._default_factory
        self._be: FtdiBackend | None = None

    def _default_factory(self) -> FtdiBackend:
        return D2xxBackend(find_index(self.serial))

    def _connect(self) -> None:
        be = self._factory()
        be.open()
        try:
            be.configure_dmx()
        except Exception:
            be.close()
            raise
        self._be = be

    def _disconnect(self) -> None:
        if self._be:
            try:
                self._be.close()
            finally:
                self._be = None

    def _send_cycle(self) -> None:
        be = self._be
        if be is None:
            raise FtdiError("sortie non connectée")
        frame = b"\x00" + (self.frames().get(self.universe) or bytes(512))
        be.set_break(True)
        precise_sleep(self.break_s)
        be.set_break(False)
        precise_sleep(self.mab_s)
        written = be.write(frame)
        if written != len(frame):
            raise FtdiError(f"écriture partielle ({written}/{len(frame)} octets)")
