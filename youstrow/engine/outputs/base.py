"""Socle commun des sorties DMX : thread dédié, état, reconnexion automatique."""
from __future__ import annotations

import sys
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..universe import DMX_CHANNELS


def precise_sleep(seconds: float) -> None:
    """Attente courte précise (le break/MAB DMX se compte en microsecondes)."""
    if seconds <= 0:
        return
    if seconds >= 0.004:
        time.sleep(seconds - 0.002)
    end = time.perf_counter() + (seconds if seconds < 0.004 else 0.002)
    while time.perf_counter() < end:
        pass


class _TimerResolution:
    """timeBeginPeriod(1) sous Windows : sans ça time.sleep() arrondit à ~15 ms."""
    _count = 0
    _lock = threading.Lock()

    @classmethod
    def acquire(cls):
        if sys.platform != "win32":
            return
        with cls._lock:
            if cls._count == 0:
                import ctypes
                ctypes.windll.winmm.timeBeginPeriod(1)
            cls._count += 1

    @classmethod
    def release(cls):
        if sys.platform != "win32":
            return
        with cls._lock:
            cls._count = max(0, cls._count - 1)
            if cls._count == 0:
                import ctypes
                ctypes.windll.winmm.timeEndPeriod(1)


@dataclass
class OutputStatus:
    state: str = "stopped"      # stopped | connecting | running | error
    message: str = ""
    frames_sent: int = 0
    fps: float = 0.0
    errors: int = 0


class DmxOutput(ABC):
    """Une sortie physique/réseau. Reçoit des trames par univers, les émet en continu."""

    kind = "base"

    def __init__(self, name: str, fps: float = 30.0):
        self.name = name
        self.fps = fps
        self.status = OutputStatus()
        self._frames: dict[int, bytes] = {}
        self._flock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- API publique -------------------------------------------------
    def set_frame(self, universe: int, data: bytes) -> None:
        data = bytes(data[:DMX_CHANNELS]).ljust(DMX_CHANNELS, b"\x00")
        with self._flock:
            self._frames[universe] = data

    def frames(self) -> dict[int, bytes]:
        with self._flock:
            return dict(self._frames)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.status = OutputStatus(state="connecting")
        self._thread = threading.Thread(target=self._run, name=f"dmx-{self.name}", daemon=True)
        self._thread.start()

    def stop(self, blackout: bool = False) -> None:
        if blackout:
            with self._flock:
                for u in self._frames:
                    self._frames[u] = bytes(DMX_CHANNELS)
            time.sleep(0.15)  # laisse partir une trame noire
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self.status.state = "stopped"

    # -- à implémenter --------------------------------------------------
    @abstractmethod
    def _connect(self) -> None: ...
    @abstractmethod
    def _send_cycle(self) -> None: ...
    def _disconnect(self) -> None: ...

    # -- boucle ----------------------------------------------------------
    def _run(self) -> None:
        _TimerResolution.acquire()
        try:
            while not self._stop.is_set():
                try:
                    self.status.state, self.status.message = "connecting", ""
                    self._connect()
                except Exception as e:  # noqa: BLE001 — l'état est exposé à l'UI
                    self._fail(e)
                    if self._stop.wait(1.0):
                        break
                    continue
                self.status.state, self.status.message = "running", ""
                period, t_fps, n_fps = 1.0 / self.fps, time.perf_counter(), 0
                try:
                    while not self._stop.is_set():
                        t0 = time.perf_counter()
                        self._send_cycle()
                        self.status.frames_sent += 1
                        n_fps += 1
                        if t0 - t_fps >= 1.0:
                            self.status.fps, t_fps, n_fps = n_fps / (t0 - t_fps), t0, 0
                        rest = period - (time.perf_counter() - t0)
                        if rest > 0:
                            self._stop.wait(rest)
                except Exception as e:  # noqa: BLE001
                    self._fail(e)
                finally:
                    try:
                        self._disconnect()
                    except Exception:  # noqa: BLE001
                        pass
                if self._stop.wait(1.0):  # reconnexion automatique
                    break
        finally:
            _TimerResolution.release()

    def _fail(self, e: Exception) -> None:
        self.status.state = "error"
        self.status.message = str(e)
        self.status.errors += 1
