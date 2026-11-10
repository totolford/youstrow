from youstrow.engine import midi as M


class FakeIn:
    ports = ["Akai APC MINI 1", "Autre"]
    last = None

    def get_ports(self): return self.ports
    def open_port(self, i): FakeIn.opened = i
    def ignore_types(self, **k): pass
    def set_callback(self, cb): FakeIn.last = cb
    def cancel_callback(self): pass
    def close_port(self): FakeIn.opened = None


class FakeOut:
    sent = []
    def get_ports(self): return ["APC MINI out"]
    def open_port(self, i): pass
    def send_message(self, m): FakeOut.sent.append(m)
    def close_port(self): pass


class FakeRt:
    MidiIn, MidiOut = FakeIn, FakeOut


def test_parse():
    assert M.parse([0x90, 36, 100]) == M.MidiMsg("note_on", 1, 36, 100)
    assert M.parse([0x91, 36, 0]).kind == "note_off"          # vélocité 0 = note off
    assert M.parse([0x80, 5, 64]).kind == "note_off"
    assert M.parse([0xB2, 48, 127]) == M.MidiMsg("cc", 3, 48, 127)
    assert M.parse([0xE0, 0, 0]).kind == "other" and M.parse([]).kind == "other"


def test_resolve_fader_and_button():
    bs = [M.Binding("cc", 48, "group_level:1"), M.Binding("note", 0, "pad:7:0"), M.Binding("cc", 20, "blackout")]
    assert M.resolve(bs, M.parse([0xB0, 48, 127])) == [("group_level:1", 1.0)]
    assert M.resolve(bs, M.parse([0xB0, 48, 0])) == [("group_level:1", 0.0)]
    assert M.resolve(bs, M.parse([0x90, 0, 90])) == [("pad:7:0", 1.0)]
    assert M.resolve(bs, M.parse([0x80, 0, 0])) == []         # relâchement : rien
    assert M.resolve(bs, M.parse([0xB0, 20, 127])) == [("blackout", 1.0)]
    assert M.resolve(bs, M.parse([0xB0, 20, 10])) == []       # bouton sur CC : seulement l'appui
    assert M.resolve([M.Binding("cc", 48, "master", channel=2)], M.parse([0xB0, 48, 64])) == []   # mauvais canal


def test_apc_mini_layout():
    bs = M.apc_mini_bindings()
    by = {(b.kind, b.number): b.action for b in bs}
    assert by[("note", 0)] == "pad:7:0"        # bas-gauche
    assert by[("note", 63)] == "pad:0:7"       # haut-droite
    assert by[("note", 82)] == "pad_row:0" and by[("note", 89)] == "pad_row:7"
    assert by[("cc", 48)] == "group_level:1" and by[("cc", 55)] == "group_level:8" and by[("cc", 56)] == "master"
    assert M.apc_pad_note(0, 0) == 56 and M.apc_pad_note(7, 7) == 7
    assert len({(b.kind, b.number) for b in bs}) == len(bs), "pas de contrôle en double"


def test_learn_replaces_and_validates():
    bs = []
    assert M.learn_binding(bs, "master", M.parse([0x90, 5, 100])) is None      # un fader exige un CC
    assert M.learn_binding(bs, "master", M.parse([0xB0, 7, 50])).number == 7
    M.learn_binding(bs, "master", M.parse([0xB0, 8, 50]))                       # ré-apprentissage : remplace
    assert [(b.action, b.number) for b in bs] == [("master", 8)]
    M.learn_binding(bs, "blackout", M.parse([0xB0, 8, 127]))                    # même contrôle : prend sa place
    assert [(b.action) for b in bs] == ["blackout"]
    assert M.learn_binding(bs, "clear", M.parse([0x80, 3, 0])) is None


def test_json_roundtrip_ignores_garbage():
    bs = M.apc_mini_bindings()
    assert M.bindings_from_json(M.bindings_to_json(bs)) == bs
    assert M.bindings_from_json([{"nope": 1}, {"kind": "cc", "number": "x", "action": "a"}]) == []


def test_engine_open_callback_and_led():
    got = []
    e = M.MidiEngine(got.append, rt=FakeRt())
    e.open("apc mini", "APC MINI out")
    assert e.connected and e.in_name == "Akai APC MINI 1"
    FakeIn.last(([0x90, 10, 127], 0.0), None)
    assert got == [M.MidiMsg("note_on", 1, 10, 127)]
    e.note(56, 3)
    assert FakeOut.sent[-1] == [0x90, 56, 3]
    e.close(); assert not e.connected


def test_engine_missing_port_error():
    import pytest
    with pytest.raises(M.MidiError):
        M.MidiEngine(lambda m: None, rt=FakeRt()).open("inexistant")
