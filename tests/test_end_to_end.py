"""Chaîne complète sans matériel : interface/contrôleur -> moteur -> sortie Open DMX (backend factice)."""
import os
import time


import pytest

from youstrow.engine.console import Console, Engine
from youstrow.engine.ftdi import FakeBackend
from youstrow.engine.outputs import OpenDmxOutput
from youstrow.fixtures.model import Patch, search_library
from youstrow.storage.files import Settings, load_show, save_show


def wait_for(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_color_reaches_the_wire():
    d = search_library("generique rgb + dimmer")[0]
    p = Patch(); p.add_many(d, d.modes[0], 2, 0, 1)         # U1: 1-4 et 5-8 (Dim,R,G,B)
    c = Console(p); c.set_color((255, 0, 128))
    be = FakeBackend(); out = OpenDmxOutput(backend_factory=lambda: be, fps=44)
    eng = Engine(c); eng.add_output(out); eng.start(); out.start()
    assert wait_for(lambda: any(e[1] == "write" and e[2][1:9] == bytes([255, 255, 0, 128, 255, 255, 0, 128]) for e in be.events))
    wire = [e[2] for e in be.events if e[1] == "write"][-1]
    assert len(wire) == 513 and wire[0] == 0                # start code DMX 0x00 + 512 canaux
    c.blackout = True
    assert wait_for(lambda: [e[2] for e in be.events if e[1] == "write"][-1][1:9] == bytes([0, 255, 0, 128, 0, 255, 0, 128]))
    eng.stop()
    assert be.events[-1][1] == "close"
    last = [e[2] for e in be.events if e[1] == "write"][-1]
    assert last[1:] == bytes(512), "noir envoyé à l'arrêt"


def test_show_roundtrip(tmp_path):
    d = search_library("generique lyre 16")[0]
    p = Patch(); p.add_many(d, d.modes[0], 2, 1, 10)
    c = Console(p); c.set_color((1, 2, 3)); c.set_position(0.25, 0.75)
    f = tmp_path / "a.ysshow"
    save_show(f, p, c.states, [])
    r = load_show(f)
    assert Patch.from_dict(r["patch"]).fixtures[1].address == 21
    assert r["states"]["1"]["color"] == [1, 2, 3] and r["states"]["1"]["pan"] == 0.25


def test_invalid_show_rejected(tmp_path):
    f = tmp_path / "x.ysshow"; f.write_text('{"hello": 1}')
    with pytest.raises(ValueError):
        load_show(f)


def test_settings_roundtrip(tmp_path):
    s = Settings(tmp_path / "s.json"); s.data["output"]["type"] = "open_dmx_d2xx"; s.add_recent("x.ysshow"); s.save()
    assert Settings(tmp_path / "s.json").data["output"]["type"] == "open_dmx_d2xx"
    assert Settings(tmp_path / "s.json").data["recent"] == ["x.ysshow"]


def test_gui_smoke(tmp_path):
    from youstrow.app import build_app
    from youstrow.controller import AppController
    from youstrow.ui.main_window import MainWindow
    app = build_app([])
    ctl = AppController(Settings(tmp_path / "s.json"))
    win = MainWindow(ctl); win.resize(1480, 880); win.show()
    d = search_library("generique rgb")[0]
    ctl.console.patch.add_many(d, d.modes[0], 4, 0, 1)
    for f in ctl.console.patch.fixtures: f.group = 1
    ctl.patchChanged.emit()
    win._pad(1, 0)                                   # rouge sur le groupe 1
    ctl.console.render()
    assert ctl.console.universes[0].snapshot()[:3] == bytes([255, 24, 24])
    win.tabs.setCurrentWidget(win.monitor); win.tabs.setCurrentWidget(win.tester); win.tabs.setCurrentWidget(win.patch_view)
    assert win.grab().width() == 1480
    win.tester.enable.setChecked(True); win.tester._moved(0, 1.0)
    ctl.console.render()
    assert ctl.console.universes[0].get(1) == 255
    win.tester.enable.setChecked(False)
    win._clear(); ctl.console.render()
    assert ctl.console.universes[0].snapshot()[:3] == bytes(3)
    ctl.dirty = False
    win.close()
