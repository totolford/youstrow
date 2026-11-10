from youstrow.engine.console import Console
from youstrow.engine.effects import Effect, EffectLayer
from youstrow.engine.memories import MemoryBank
from youstrow.fixtures.model import FixtureDef, FixtureMode, Patch


def rig():
    p = Patch()
    d = FixtureDef("T", "Par", "x", (FixtureMode("m", ("R", "G", "B")),))
    fx = p.add_many(d, d.modes[0], 4, 0, 1)
    for i, f in enumerate(fx):
        f.group = 1 if i < 2 else 2
    return Console(p), fx


def test_defaults_apply_color_to_group_and_exclusive_per_column():
    c, fx = rig(); b = MemoryBank(); b.load_defaults()
    assert b.recall(0, 1, 0, c)                       # rouge sur le groupe 1
    c.render(); s = c.universes[0].snapshot()
    assert s[0:3] == bytes([255, 24, 24]) and s[3:6] == bytes([255, 24, 24]) and s[6:9] == bytes(3)
    assert b.active_row(0, 0) == 1
    assert b.recall(0, 4, 0, c)                       # vert, même colonne : remplace le rouge
    c.render(); assert c.universes[0].snapshot()[0:3] == bytes([0, 214, 40]) and b.active_row(0, 0) == 4
    assert b.recall(0, 4, 1, c)                       # autre colonne : indépendante
    c.render(); s = c.universes[0].snapshot(); assert s[0:3] == bytes([0, 214, 40]) and s[6:9] == bytes([0, 214, 40])


def test_reclick_turns_off():
    c, fx = rig(); b = MemoryBank(); b.load_defaults()
    b.recall(0, 2, 0, c); b.recall(0, 2, 0, c)
    c.render(); assert c.universes[0].snapshot()[0:3] == bytes(3) and b.active_row(0, 0) is None


def test_rec_stores_current_state_and_effects_and_roundtrip():
    c, fx = rig(); b = MemoryBank()
    c.set_color((10, 20, 30), [fx[2].id, fx[3].id]); c.set_dimmer(0.5, [fx[2].id])
    pulse = Effect("Pulse", [EffectLayer("dimmer", "sine", 1.0, 1.0)]); c.start_effect(pulse)
    m = b.store(0, 3, 1, c)                           # colonne 1 = groupe 2
    assert m.fixture_ids == [fx[2].id, fx[3].id] and m.states[fx[2].id]["dimmer"] == 0.5 and m.effects == ["Pulse"]
    c.clear_all()
    d = MemoryBank.from_dict(b.to_dict())
    d.recall(0, 3, 1, c, {"Pulse": pulse})
    assert c.state(fx[2].id).color == (10, 20, 30) and c.state(fx[2].id).dimmer == 0.5 and "Pulse" in c.running


def test_clear_and_empty_recall():
    c, fx = rig(); b = MemoryBank()
    assert not b.recall(0, 0, 0, c)
    b.load_defaults(); b.clear(0, 1, 0, c); assert b.get(0, 1, 0) is None
