import socket
import time

from youstrow.engine.ftdi import FakeBackend, serials_match, list_devices
from youstrow.engine.outputs import OpenDmxOutput, ArtNetOutput
from youstrow.engine.outputs.artnet import build_artdmx, parse_artpollreply, ID
from youstrow.engine.outputs.enttec_pro import build_pro_packet
from youstrow.engine.universe import Universe, merge_htp


def wait_for(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_universe_basics():
    u = Universe()
    u.set(1, 300); u.set(512, -5)
    assert u.get(1) == 255 and u.get(512) == 0
    u.set_many(10, [1, 2, 3])
    assert u.snapshot()[9:12] == b"\x01\x02\x03"
    assert merge_htp(bytes([1, 9]), bytes([5, 2]))[:2] == bytes([5, 9])


def test_open_dmx_frame_sequence():
    be = FakeBackend()
    out = OpenDmxOutput(backend_factory=lambda: be, fps=40)
    frame = bytes(range(256)) * 2
    out.set_frame(0, frame)
    out.start()
    assert wait_for(lambda: sum(e[1] == "write" for e in be.events) >= 5)
    out.stop()
    kinds = [e[1] for e in be.events]
    assert kinds[:2] == ["open", "configure"]
    assert be.events[1][2] == {"baud": 250000, "bits": 8, "stop": 2, "parity": "none"}
    # chaque trame = break_on, break_off, write
    body = [k for k in kinds if k in ("break_on", "break_off", "write")]
    for i in range(0, 12, 3):
        assert body[i:i + 3] == ["break_on", "break_off", "write"]
    writes = [e[2] for e in be.events if e[1] == "write"]
    assert all(len(w) == 513 and w[0] == 0 and w[1:] == frame for w in writes)
    assert kinds[-1] == "close"


def test_open_dmx_break_mab_durations():
    be = FakeBackend()
    out = OpenDmxOutput(backend_factory=lambda: be, fps=30)
    out.start()
    assert wait_for(lambda: sum(e[1] == "write" for e in be.events) >= 10)
    out.stop()
    ev = be.events
    brk = [ev[i + 1][0] - ev[i][0] for i in range(len(ev) - 1) if ev[i][1] == "break_on" and ev[i + 1][1] == "break_off"]
    assert min(brk) >= 88e-6, "break DMX >= 88 us exigé par la norme"


def test_open_dmx_reconnects_after_unplug():
    backends = []

    def factory():
        b = FakeBackend(fail_write_after=3 if not backends else None)
        backends.append(b)
        return b

    out = OpenDmxOutput(backend_factory=factory, fps=40)
    out.start()
    assert wait_for(lambda: out.status.state == "error", 3)
    assert out.status.errors >= 1
    assert wait_for(lambda: len(backends) >= 2 and out.status.state == "running", 5), "reconnexion automatique"
    out.stop()


def test_open_dmx_connect_failure_reported():
    from youstrow.engine.ftdi import FtdiError

    def factory():
        raise FtdiError("Aucune puce FTDI détectée")
    out = OpenDmxOutput(backend_factory=factory)
    out.start()
    assert wait_for(lambda: out.status.state == "error")
    assert "FTDI" in out.status.message
    out.stop()


def test_artdmx_golden_packet():
    p = build_artdmx(7, 0x0123, bytes([255, 0, 128]))
    assert p[:8] == ID and p[8:10] == b"\x00\x50"          # opcode 0x5000 little-endian
    assert p[10:12] == b"\x00\x0e"                          # protocole 14
    assert p[12] == 7 and p[14] == 0x23 and p[15] == 0x01   # seq, SubUni, Net
    assert p[16:18] == b"\x00\x04"                          # longueur paire
    assert p[18:] == bytes([255, 0, 128, 0])


def test_artnet_output_over_udp_loopback():
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("127.0.0.1", 0)); rx.settimeout(2)
    port = rx.getsockname()[1]
    import youstrow.engine.outputs.artnet as an
    an.ARTNET_PORT = port
    out = ArtNetOutput(target_ip="127.0.0.1", universe_map={0: 5}, fps=40)
    data = bytes([i % 256 for i in range(512)])
    out.set_frame(0, data); out.start()
    pkt, _ = rx.recvfrom(2048)
    out.stop(); rx.close()
    assert pkt[:8] == ID and pkt[14] == 5 and pkt[18:] == data and len(pkt) == 18 + 512


def test_enttec_pro_packet():
    p = build_pro_packet(bytes([9] * 512))
    assert p[:4] == bytes([0x7E, 6, 0x01, 0x02]) and p[-1] == 0xE7 and len(p) == 518   # 513 = 0x0201


def test_pollreply_parse():
    pkt = bytearray(240); pkt[:8] = ID; pkt[8:10] = b"\x00\x21"
    pkt[26:30] = b"Node"; pkt[44:52] = b"Long nom"
    n = parse_artpollreply(bytes(pkt), "2.0.0.15")
    assert n and n.short_name == "Node" and n.long_name == "Long nom"


def test_ftdi_helpers():
    assert serials_match("BG04EMMJA", "BG04EMMJ")
    assert not serials_match("", "BG04EMMJ")
    assert isinstance(list_devices(), list)   # ne plante pas sans matériel
