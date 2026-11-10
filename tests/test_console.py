import pytest

from youstrow.engine.console import Console
from youstrow.engine.effects import Effect, EffectLayer, wave
from youstrow.fixtures.model import FixtureDef, FixtureMode, Patch, PatchError, load_library, search_library


def mk(chans, addr=1, u=0, patch=None, name="F"):
    p = patch or Patch()
    d = FixtureDef("T", name, "x", (FixtureMode("m", tuple(chans)),))
    return p, p.add_many(d, d.modes[0], 1, u, addr)[0]


def test_library_loaded():
    lib = load_library()
    assert len(lib) > 1700
    assert search_library("generique rgb")[0].manufacturer == "Générique"


def test_patch_overlap_rejected_and_free_address():
    p, a = mk(["R", "G", "B"], 1)
    d = FixtureDef("T", "x", "x", (FixtureMode("m", ("R", "G", "B")),))
    with pytest.raises(PatchError):
        p.add_many(d, d.modes[0], 1, 0, 2)
    assert p.free_address(0, 3) == 4
    with pytest.raises(PatchError):
        p.add_many(d, d.modes[0], 1, 0, 511)       # dépasse 512


def test_patch_many_contiguous():
    p = Patch()
    d = FixtureDef("T", "Par", "PAR LED", (FixtureMode("m", ("Dim", "R", "G", "B")),))
    fx = p.add_many(d, d.modes[0], 4, 0, 1)
    assert [f.address for f in fx] == [1, 5, 9, 13]


def test_rgb_render_and_master():
    p, fx = mk(["R", "G", "B"], 10)
    c = Console(p)
    c.set_color((255, 128, 0)); c.render()
    assert c.universes[0].snapshot()[9:12] == bytes([255, 128, 0])
    c.master = 0.5; c.render()
    assert c.universes[0].snapshot()[9:12] == bytes([127, 64, 0])     # sans canal Dim, le master module la couleur
    c.blackout = True; c.render()
    assert c.universes[0].snapshot()[9:12] == bytes(3)


def test_dim_rgb_strobe_fixture():
    p, fx = mk(["Dim", "R", "G", "B", "Strobe"], 1)
    c = Console(p)
    c.set_color((10, 20, 30)); c.set_dimmer(0.5); c.render()
    assert c.universes[0].snapshot()[:5] == bytes([127, 10, 20, 30, 0])
    c.set_strobe(1.0); c.render()
    assert c.universes[0].snapshot()[4] == 255


def test_pan_tilt_16bit_and_invert():
    p, fx = mk(["Pan", "PanFine", "Tilt", "TiltFine", "Dim"], 1)
    c = Console(p)
    c.set_position(1.0, 0.5); c.render()
    s = c.universes[0].snapshot()
    assert s[0] == 255 and s[1] == 255 and s[2] == 128 and s[3] == 0   # 0.5*65535 = 32768 -> 0x8000
    fx.invert_pan = True; c.set_position(1.0, 0.5); c.render()
    assert c.universes[0].snapshot()[0] == 0


def test_defaults_for_unpatched_channels_center_pan():
    p, fx = mk(["Pan", "Tilt"], 1)
    c = Console(p); c.render()
    assert c.universes[0].snapshot()[:2] == bytes([128, 128])         # centre par défaut


def test_dimmer_only_fixture_follows_color_luminosity():
    p, fx = mk(["Dim"], 1)
    c = Console(p)
    c.render(); assert c.universes[0].get(1) == 0
    c.set_color((255, 255, 255)); c.render(); assert c.universes[0].get(1) == 255
    c.set_color((128, 0, 0)); c.render(); assert 126 <= c.universes[0].get(1) <= 128


def test_group_level():
    p, fx = mk(["R", "G", "B"], 1)
    fx.group = 2
    c = Console(p); c.set_color((200, 200, 200)); c.group_levels[2] = 0.5; c.render()
    assert c.universes[0].snapshot()[:3] == bytes([100, 100, 100])


def test_effect_chase_spreads_over_fixtures():
    p = Patch()
    d = FixtureDef("T", "Par", "x", (FixtureMode("m", ("R", "G", "B")),))
    p.add_many(d, d.modes[0], 4, 0, 1)
    c = Console(p); c.set_color((255, 255, 255))
    eff = Effect("chase", [EffectLayer("dimmer", "square", 1.0, 1.0, spread=1.0)])
    c.start_effect(eff)
    run = c.running["chase"]
    c.render(run.started + 0.01)       # fixture 0 en phase haute, 1 (offset .25) haute, 2 (.5) basse, 3 (.75) basse
    s = c.universes[0].snapshot()
    assert [s[0], s[3], s[6], s[9]] == [255, 255, 0, 0]
    c.render(run.started + 0.51)
    s = c.universes[0].snapshot()
    assert [s[0], s[3], s[6], s[9]] == [0, 0, 255, 255]


def test_direct_overrides_and_tester_mode():
    p, fx = mk(["R", "G", "B"], 1)
    c = Console(p); c.set_color((255, 0, 0)); c.set_direct(0, 1, 77); c.render()
    assert c.universes[0].get(1) == 77
    c.tester_active = True; c.render()
    assert c.universes[0].get(2) == 0 and c.universes[0].get(1) == 77      # le show s'efface, le direct reste


def test_waves_range():
    for s in ("sine", "triangle", "square", "saw", "ramp", "random"):
        assert all(0 <= wave(s, x / 7) <= 1 for x in range(50))


def test_rig_lines_and_stands():
    from youstrow.fixtures.rig import line_report, stand_warnings
    p = Patch()
    d = FixtureDef("T", "Par", "x", (FixtureMode("m", ("R", "G", "B")),))
    fx = p.add_many(d, d.modes[0], 3, 0, 1)
    fx[0].line, fx[1].line, fx[2].line = 1, 1, 9
    fx[0].stand, fx[0].height_cm = "BLS-315 Pro", 400
    rep = "\n".join(line_report(p))
    assert "Sortie 1 : 2 appareil(s)" in rep and "Sortie 9 inexistante" in rep and "Sorties libres : 2, 3" in rep
    assert "hors plage" in stand_warnings(p)[0]
    fx[0].height_cm = 250
    assert stand_warnings(p) == []
