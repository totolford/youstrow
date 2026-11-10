"""Open DMX via port COM virtuel (VCP) — repli quand D2XX n'est pas disponible
(clones CH340/CP210x, ou driver D2XX absent). Même protocole que `open_dmx`."""
from __future__ import annotations

from ..ftdi import FtdiError


class SerialBackend:
    """Implémente l'interface FtdiBackend au-dessus de pyserial."""

    def __init__(self, port: str):
        self.port = port
        self._s = None

    def open(self) -> None:
        import serial
        try:
            self._s = serial.Serial(port=None, baudrate=250000, bytesize=serial.EIGHTBITS,
                                    parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_TWO, timeout=1,
                                    write_timeout=1)
            self._s.port = self.port
            self._s.open()
        except Exception as e:  # noqa: BLE001
            raise FtdiError(f"Ouverture de {self.port} impossible : {e}") from e

    def configure_dmx(self) -> None:
        self._s.rts = False
        self._s.dtr = False
        self._s.reset_output_buffer()

    def set_break(self, on: bool) -> None:
        self._s.break_condition = on

    def write(self, data: bytes) -> int:
        try:
            n = self._s.write(data)
            self._s.flush()
            return n
        except Exception as e:  # noqa: BLE001
            raise FtdiError(f"écriture série : {e}") from e

    def close(self) -> None:
        if self._s:
            try:
                self._s.break_condition = False
                self._s.close()
            finally:
                self._s = None


def list_com_ports() -> list[tuple[str, str, str]]:
    """[(port, description, numéro de série USB)]"""
    from serial.tools import list_ports
    return [(p.device, p.description or "", p.serial_number or "") for p in list_ports.comports()]
