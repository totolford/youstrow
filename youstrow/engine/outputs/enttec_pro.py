"""ENTTEC DMX USB PRO / PRO Mk2 : l'interface fabrique elle-même break/MAB.
Paquet « Output Only Send DMX » : 0x7E, label 6, longueur (LSB, MSB), start code + données, 0xE7."""
from __future__ import annotations

from ..ftdi import FtdiError

SOM, EOM, LABEL_SEND_DMX = 0x7E, 0xE7, 6


def build_pro_packet(data: bytes) -> bytes:
    payload = b"\x00" + bytes(data[:512])
    n = len(payload)
    return bytes([SOM, LABEL_SEND_DMX, n & 0xFF, (n >> 8) & 0xFF]) + payload + bytes([EOM])


from .base import DmxOutput  # noqa: E402


class EnttecProOutput(DmxOutput):
    kind = "enttec_pro"

    def __init__(self, port: str, name="ENTTEC DMX USB PRO", universe=0, fps=30.0, serial_factory=None):
        super().__init__(name, fps)
        self.port, self.universe = port, universe
        self._factory = serial_factory
        self._s = None

    def _connect(self):
        import serial
        try:
            self._s = (self._factory or (lambda: serial.Serial(self.port, 57600, timeout=1, write_timeout=1)))()
        except Exception as e:  # noqa: BLE001
            raise FtdiError(f"Ouverture de {self.port} impossible : {e}") from e

    def _disconnect(self):
        if self._s:
            self._s.close()
            self._s = None

    def _send_cycle(self):
        try:
            self._s.write(build_pro_packet(self.frames().get(self.universe, bytes(512))))
            self._s.flush()
        except Exception as e:  # noqa: BLE001
            raise FtdiError(f"écriture PRO : {e}") from e
