"""Sortie Art-Net (ArtDMX, OpCode 0x5000, UDP 6454) + découverte ArtPoll."""
from __future__ import annotations

import socket
import struct
import time
from dataclasses import dataclass

from .base import DmxOutput

ARTNET_PORT = 6454
ID = b"Art-Net\x00"
OP_POLL, OP_POLL_REPLY, OP_DMX = 0x2000, 0x2100, 0x5000


def build_artdmx(sequence: int, port_address: int, data: bytes, physical: int = 0) -> bytes:
    """Paquet ArtDMX. port_address : 15 bits (Net 7 bits | SubNet 4 | Universe 4)."""
    if not 0 <= port_address <= 0x7FFF:
        raise ValueError("port-address Art-Net hors plage (0..32767)")
    n = len(data)
    if n % 2:                                # la longueur doit être paire
        data, n = data + b"\x00", n + 1
    return (ID + struct.pack("<H", OP_DMX) + struct.pack(">H", 14)
            + bytes([sequence & 0xFF, physical & 0xFF, port_address & 0xFF, (port_address >> 8) & 0x7F])
            + struct.pack(">H", n) + bytes(data))


def build_artpoll() -> bytes:
    return ID + struct.pack("<H", OP_POLL) + struct.pack(">H", 14) + bytes([0x02, 0x00])


@dataclass
class ArtNetNode:
    ip: str
    short_name: str
    long_name: str


def parse_artpollreply(pkt: bytes, ip: str) -> ArtNetNode | None:
    if len(pkt) < 108 or pkt[:8] != ID or struct.unpack("<H", pkt[8:10])[0] != OP_POLL_REPLY:
        return None
    short = pkt[26:44].split(b"\x00")[0].decode("latin-1")
    long_ = pkt[44:108].split(b"\x00")[0].decode("latin-1")
    return ArtNetNode(ip, short, long_)


def discover_nodes(timeout: float = 2.0, bind_ip: str = "") -> list[ArtNetNode]:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    nodes: dict[str, ArtNetNode] = {}
    try:
        try:
            s.bind((bind_ip, ARTNET_PORT))
        except OSError:
            s.bind((bind_ip, 0))
        s.sendto(build_artpoll(), ("255.255.255.255", ARTNET_PORT))
        end = time.time() + timeout
        while time.time() < end:
            s.settimeout(max(0.05, end - time.time()))
            try:
                pkt, (ip, _) = s.recvfrom(1024)
            except (socket.timeout, OSError):
                break
            n = parse_artpollreply(pkt, ip)
            if n:
                nodes[ip] = n
    finally:
        s.close()
    return list(nodes.values())


class ArtNetOutput(DmxOutput):
    """universe_map : univers interne -> port-address Art-Net ; target_ip : node ou broadcast."""
    kind = "artnet"

    def __init__(self, name="Art-Net", target_ip="255.255.255.255", universe_map: dict[int, int] | None = None,
                 fps: float = 30.0, bind_ip: str = ""):
        super().__init__(name, fps)
        self.target_ip = target_ip
        self.universe_map = universe_map or {0: 0}
        self.bind_ip = bind_ip
        self._sock: socket.socket | None = None
        self._seq = {}

    def _connect(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        if self.bind_ip:
            s.bind((self.bind_ip, 0))
        self._sock = s

    def _disconnect(self) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None

    def _send_cycle(self) -> None:
        frames = self.frames()
        for uni, pa in self.universe_map.items():
            seq = self._seq.get(uni, 0) % 255 + 1   # 1..255 (0 = séquencement désactivé)
            self._seq[uni] = seq
            self._sock.sendto(build_artdmx(seq, pa, frames.get(uni, bytes(512))), (self.target_ip, ARTNET_PORT))
