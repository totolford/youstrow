import json
import urllib.request

import pytest

from youstrow.engine.console import Console
from youstrow.fixtures.model import FixtureDef, FixtureMode, Patch
from youstrow.ui import plan3d


def test_world_mapping_roundtrip_and_orientation():
    p = Patch()
    d = FixtureDef("T", "Par", "x", (FixtureMode("m", ("R", "G", "B")),))
    f = p.add_many(d, d.modes[0], 1, 0, 1)[0]
    f.x, f.y = 0.0, 1.0                           # coin plan « gauche / face »
    x, z = plan3d.world_pos(f)
    assert x == pytest.approx(9.0) and z == pytest.approx(-5.0)    # gauche (public) = jardin = X+ ; face = Z-
    assert plan3d.from_world(x, z) == pytest.approx((0.0, 1.0))
    assert plan3d.from_world(100, -100) == (0.0, 1.0)              # borné au plan


def test_projectors_payload():
    p = Patch()
    rgb = FixtureDef("T", "Par", "PAR LED", (FixtureMode("m", ("Dim", "R", "G", "B")),))
    mh = FixtureDef("T", "Lyre", "Moving Head", (FixtureMode("m", ("Pan", "PanFine", "Tilt", "TiltFine", "Dim")),))
    a = p.add_many(rgb, rgb.modes[0], 1, 0, 1)[0]; a.height_cm = 250
    b = p.add_many(mh, mh.modes[0], 1, 0, 10)[0]
    c = Console(p); c.set_color((255, 128, 0)); c.set_position(1.0, 0.5); c.render()
    out = plan3d.projectors_from_console(c, 8.0)
    assert out[0]["fixture_height"] == 2.5 and (out[0]["r"], out[0]["g"], out[0]["b"]) == (255, 128, 0) and out[0]["level"] == 100.0
    assert out[1]["fixture_height"] == 8.0 and out[1]["fixture_type"] == "Moving Head"
    assert out[1]["pan"] == 65535 and out[1]["tilt"] == 32768      # pan 1.0 -> 16 bits pleins ; tilt 0.5 -> 0x8000
    json.dumps(out)                                                # sérialisable pour le JS


def test_scene_catalog_matches_original():
    codes = [s.code for s in plan3d.SCENES]
    assert codes == ["vide", "concert_glb", "scene_6x5", "festival_plein_air", "discotheque", "dj_mobile", "conference", "sapin_noel"]
    assert plan3d.SCENE_BY_CODE["dj_mobile"].rig_height == 2.05 and plan3d.SCENE_BY_CODE["concert_glb"].yaw == 180.0


@pytest.mark.skipif(not plan3d.web_assets_present(), reason="fichiers 3D non présents (ressources d'origine non versionnées)")
def test_local_server_serves_js_module_and_glb():
    port = plan3d.server_port()
    r = urllib.request.urlopen(f"http://127.0.0.1:{port}/vendor/three/three.module.js")
    assert r.status == 200 and "javascript" in r.headers["Content-Type"]
    g = urllib.request.urlopen(f"http://127.0.0.1:{port}/scenes3d/scene_6x5.glb")
    assert g.read(4) == b"glTF"
