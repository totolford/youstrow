"""Accès bas niveau aux puces FTDI (driver D2XX) via ctypes.

Chargé *à la demande* : l'application démarre même si le driver FTDI est absent
(le paquet pip `ftd2xx` plantait à l'import dans ce cas).

Deux implémentations de l'interface `FtdiBackend` :
  - `D2xxBackend`  : vraie puce, via ftd2xx.dll
  - `FakeBackend`  : enregistre les appels (tests sans matériel / mode simulation)
"""
from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

FT_OK = 0
FT_BITS_8 = 8
FT_STOP_BITS_2 = 2
FT_PARITY_NONE = 0
FT_FLOW_NONE = 0
FT_PURGE_RX, FT_PURGE_TX = 1, 2


class FtdiError(RuntimeError):
    pass


@dataclass(frozen=True)
class FtdiDeviceInfo:
    index: int
    serial: str
    description: str
    in_use: bool = False  # FT_FLAGS_OPENED


class FtdiBackend(Protocol):
    def open(self) -> None: ...
    def close(self) -> None: ...
    def configure_dmx(self) -> None: ...
    def set_break(self, on: bool) -> None: ...
    def write(self, data: bytes) -> int: ...


# --------------------------------------------------------------------- DLL
_lib = None
_lib_lock = threading.Lock()


def _candidate_dlls() -> list[str]:
    here = Path(__file__).resolve()
    roots = [Path(getattr(sys, "_MEIPASS", "")) if hasattr(sys, "_MEIPASS") else None,
             Path(sys.executable).parent, here.parents[2] / "vendor", here.parents[2]]
    names = ["ftd2xx64.dll", "ftd2xx.dll"]
    out = [str(r / n) for r in roots if r for n in names if (r / n).exists()]
    return out + names  # puis chemin système (driver FTDI installé)


def load_library():
    """Retourne la DLL D2XX ou lève FtdiError si introuvable."""
    global _lib
    with _lib_lock:
        if _lib is not None:
            return _lib
        if os.name != "nt":
            names = ["libftd2xx.so", "libftd2xx.dylib"]
            loader = ctypes.CDLL
        else:
            names, loader = _candidate_dlls(), ctypes.WinDLL
        last = None
        for n in names:
            try:
                _lib = loader(n)
                break
            except OSError as e:
                last = e
        if _lib is None:
            raise FtdiError(f"Driver FTDI D2XX introuvable ({last})")
        _declare(_lib)
        return _lib


def _declare(d) -> None:
    H = ctypes.c_void_p
    U32, U8, U16 = ctypes.c_ulong, ctypes.c_ubyte, ctypes.c_ushort
    sig = {
        "FT_CreateDeviceInfoList": ([ctypes.POINTER(U32)], U32),
        "FT_GetDeviceInfoDetail": ([U32, ctypes.POINTER(U32), ctypes.POINTER(U32), ctypes.POINTER(U32),
                                    ctypes.POINTER(U32), ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(H)], U32),
        "FT_Open": ([ctypes.c_int, ctypes.POINTER(H)], U32),
        "FT_Close": ([H], U32),
        "FT_ResetDevice": ([H], U32),
        "FT_SetBaudRate": ([H, U32], U32),
        "FT_SetDataCharacteristics": ([H, U8, U8, U8], U32),
        "FT_SetFlowControl": ([H, U16, U8, U8], U32),
        "FT_ClrRts": ([H], U32),
        "FT_ClrDtr": ([H], U32),
        "FT_SetRts": ([H], U32),
        "FT_SetDtr": ([H], U32),
        "FT_Purge": ([H, U32], U32),
        "FT_SetBreakOn": ([H], U32),
        "FT_SetBreakOff": ([H], U32),
        "FT_SetTimeouts": ([H, U32, U32], U32),
        "FT_SetLatencyTimer": ([H, U8], U32),
        "FT_Write": ([H, ctypes.c_void_p, U32, ctypes.POINTER(U32)], U32),
    }
    for name, (args, res) in sig.items():
        fn = getattr(d, name)
        fn.argtypes, fn.restype = args, res


def d2xx_available() -> bool:
    try:
        load_library()
        return True
    except FtdiError:
        return False


def list_devices() -> list[FtdiDeviceInfo]:
    """Puces FTDI visibles par D2XX. Liste vide si driver absent ou aucune puce."""
    try:
        d = load_library()
    except FtdiError:
        return []
    n = ctypes.c_ulong(0)
    if d.FT_CreateDeviceInfoList(ctypes.byref(n)) != FT_OK:
        return []
    out = []
    for i in range(n.value):
        flags, typ, did, loc = (ctypes.c_ulong() for _ in range(4))
        serial, desc = ctypes.create_string_buffer(16), ctypes.create_string_buffer(64)
        h = ctypes.c_void_p()
        if d.FT_GetDeviceInfoDetail(i, ctypes.byref(flags), ctypes.byref(typ), ctypes.byref(did),
                                    ctypes.byref(loc), serial, desc, ctypes.byref(h)) == FT_OK:
            out.append(FtdiDeviceInfo(i, serial.value.decode("ascii", "ignore"),
                                      desc.value.decode("ascii", "ignore"), bool(flags.value & 1)))
    return out


def serials_match(a: str, b: str) -> bool:
    """Égalité stricte ou préfixe (suffixe d'interface FTDI : BG04EMMJ / BG04EMMJA)."""
    a, b = a.strip().upper(), b.strip().upper()
    return bool(a and b) and (a == b or a.startswith(b) or b.startswith(a))


def find_index(serial: str | None) -> int:
    """Index D2XX à ouvrir : celui du numéro de série demandé, sinon le premier."""
    devs = list_devices()
    if not devs:
        raise FtdiError("Aucune puce FTDI détectée (driver absent, câble débranché ou puce déjà ouverte)")
    if serial:
        for d in devs:
            if serials_match(d.serial, serial):
                return d.index
        raise FtdiError(f"Puce FTDI {serial!r} introuvable (présentes : {[d.serial for d in devs]})")
    return devs[0].index


class D2xxBackend:
    """Vraie puce FTDI (ENTTEC Open DMX USB = FT232R passif)."""

    def __init__(self, index: int = 0):
        self.index = index
        self._h = ctypes.c_void_p()
        self._d = None

    def _chk(self, status: int, what: str) -> None:
        if status != FT_OK:
            raise FtdiError(f"{what} a échoué (FT_STATUS={status})")

    def open(self) -> None:
        self._d = load_library()
        self._chk(self._d.FT_Open(self.index, ctypes.byref(self._h)), "FT_Open")

    def close(self) -> None:
        if self._d is not None and self._h:
            try:
                self._d.FT_SetBreakOff(self._h)
                self._d.FT_Close(self._h)
            finally:
                self._h = ctypes.c_void_p()

    def configure_dmx(self) -> None:
        d, h = self._d, self._h
        self._chk(d.FT_ResetDevice(h), "FT_ResetDevice")
        self._chk(d.FT_SetBaudRate(h, 250000), "FT_SetBaudRate")
        self._chk(d.FT_SetDataCharacteristics(h, FT_BITS_8, FT_STOP_BITS_2, FT_PARITY_NONE), "FT_SetDataCharacteristics")
        self._chk(d.FT_SetFlowControl(h, FT_FLOW_NONE, 0, 0), "FT_SetFlowControl")
        self._chk(d.FT_ClrRts(h), "FT_ClrRts")  # RTS bas = driver RS-485 en émission
        d.FT_SetLatencyTimer(h, 1)               # réponse USB la plus rapide
        d.FT_SetTimeouts(h, 1000, 1000)
        self._chk(d.FT_Purge(h, FT_PURGE_RX | FT_PURGE_TX), "FT_Purge")

    def set_break(self, on: bool) -> None:
        self._chk((self._d.FT_SetBreakOn if on else self._d.FT_SetBreakOff)(self._h), "FT_SetBreak")

    def write(self, data: bytes) -> int:
        n = ctypes.c_ulong(0)
        buf = ctypes.create_string_buffer(bytes(data), len(data))
        self._chk(self._d.FT_Write(self._h, buf, len(data), ctypes.byref(n)), "FT_Write")
        return n.value


# ------------------------------------------------------------------- Fake
@dataclass
class FakeBackend:
    """Backend de test : enregistre chaque appel avec son horodatage."""
    events: list = field(default_factory=list)
    fail_write_after: int | None = None   # simule un débranchement
    opened: bool = False

    def _log(self, kind, payload=None):
        self.events.append((time.perf_counter(), kind, payload))

    def open(self): self.opened = True; self._log("open")
    def close(self): self.opened = False; self._log("close")
    def configure_dmx(self): self._log("configure", {"baud": 250000, "bits": 8, "stop": 2, "parity": "none"})
    def set_break(self, on): self._log("break_on" if on else "break_off")

    def write(self, data):
        writes = sum(1 for e in self.events if e[1] == "write")
        if self.fail_write_after is not None and writes >= self.fail_write_after:
            raise FtdiError("périphérique débranché (simulé)")
        self._log("write", bytes(data))
        return len(data)
