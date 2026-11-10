"""Univers DMX : tampon de 512 canaux thread-safe, et fusion de sources."""
from __future__ import annotations

import threading

DMX_CHANNELS = 512


def clamp8(v: int | float) -> int:
    return 0 if v < 0 else 255 if v > 255 else int(v)


class Universe:
    """512 canaux, valeurs 0-255. Adressage utilisateur 1..512."""

    def __init__(self, index: int = 0):
        self.index = index
        self._buf = bytearray(DMX_CHANNELS)
        self._lock = threading.Lock()
        self.revision = 0  # incrémenté à chaque changement réel

    def set(self, channel: int, value: int) -> None:
        if not 1 <= channel <= DMX_CHANNELS:
            raise ValueError(f"canal DMX hors plage : {channel}")
        v = clamp8(value)
        with self._lock:
            if self._buf[channel - 1] != v:
                self._buf[channel - 1] = v
                self.revision += 1

    def get(self, channel: int) -> int:
        with self._lock:
            return self._buf[channel - 1]

    def set_many(self, start: int, values) -> None:
        with self._lock:
            for i, v in enumerate(values):
                ch = start - 1 + i
                if 0 <= ch < DMX_CHANNELS:
                    self._buf[ch] = clamp8(v)
            self.revision += 1

    def replace(self, data: bytes) -> None:
        """Remplace tout le contenu (complété par des zéros, tronqué à 512)."""
        data = bytes(data[:DMX_CHANNELS]).ljust(DMX_CHANNELS, b"\x00")
        with self._lock:
            if data != self._buf:
                self._buf[:] = data
                self.revision += 1

    def blackout(self) -> None:
        self.replace(b"")

    def snapshot(self) -> bytes:
        with self._lock:
            return bytes(self._buf)


def merge_htp(*frames: bytes) -> bytes:
    """Highest Takes Precedence : maximum canal par canal."""
    if not frames:
        return bytes(DMX_CHANNELS)
    out = bytearray(DMX_CHANNELS)
    for f in frames:
        for i, v in enumerate(f[:DMX_CHANNELS]):
            if v > out[i]:
                out[i] = v
    return bytes(out)
