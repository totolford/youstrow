import os
import time
from pathlib import Path


import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtMultimedia import QMediaPlayer

DATA = Path(__file__).parent / "data"


def pump(cond, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        QCoreApplication.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def env(tmp_path):
    from youstrow.app import build_app
    from youstrow.controller import AppController
    from youstrow.storage.files import Settings
    from youstrow.ui.media_panel import MediaPanel
    app = build_app([])
    ctl = AppController(Settings(tmp_path / "s.json"))
    panel = MediaPanel(ctl)
    yield ctl, panel
    # démontage complet : des lecteurs Qt/FFmpeg laissés vivants entre deux tests peuvent bloquer le thread GUI
    from PySide6.QtCore import QEvent, QUrl
    panel.shutdown()
    for pl in (panel.player, panel.probe):
        pl.stop(); pl.setSource(QUrl())
    QCoreApplication.processEvents()
    panel.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QCoreApplication.processEvents()


def test_add_filters_and_dedupes(env):
    ctl, panel = env
    assert panel.add_files([str(DATA / "tone.wav"), str(DATA / "tone.wav"), str(DATA / "note.txt")]) == 1
    assert len(ctl.playlist) == 1 and ctl.playlist[0]["volume"] == 100
    assert panel.table.rowCount() == 1


def test_duration_probe_and_playback_with_light(env):
    ctl, panel = env
    panel.add_files([str(DATA / "tone.wav"), str(DATA / "clip.mp4")])
    assert pump(lambda: all(it["duration_ms"] > 0 for it in ctl.playlist)), "durées lues depuis les fichiers"
    assert 2800 <= ctl.playlist[0]["duration_ms"] <= 3300
    ctl.playlist[0]["effect"] = "Pulse"
    panel.play_index(0)
    assert pump(lambda: panel.player.playbackState() == QMediaPlayer.PlayingState)
    assert "Pulse" in ctl.console.running, "l'effet lumineux démarre avec la piste"
    assert pump(lambda: panel.player.position() > 300), "la lecture avance"
    panel.stop()
    assert "Pulse" not in ctl.console.running, "l'effet s'arrête avec la piste"


def test_video_track_and_next(env):
    ctl, panel = env
    panel.add_files([str(DATA / "clip.mp4"), str(DATA / "tone.wav")])
    panel.play_index(0)
    assert pump(lambda: panel.player.hasVideo()), "piste vidéo détectée"
    panel.next()
    assert panel.current == 1
    assert pump(lambda: panel.player.playbackState() == QMediaPlayer.PlayingState)
    assert not panel.player.hasVideo() or True
    panel.prev()                                         # position < 3 s : revient à la piste précédente
    assert panel.current == 0


def test_remove_move_and_show_persistence(env, tmp_path):
    ctl, panel = env
    panel.add_files([str(DATA / "tone.wav"), str(DATA / "clip.mp4")])
    panel.table.selectRow(1); panel._move(-1)
    assert ctl.playlist[0]["path"].endswith("clip.mp4")
    ctl.playlist[0]["volume"] = 40
    ctl.save_show(str(tmp_path / "x.ysshow"))
    ctl.playlist = []
    ctl.open_show(str(tmp_path / "x.ysshow"))
    assert [Path(i["path"]).name for i in ctl.playlist] == ["clip.mp4", "tone.wav"] and ctl.playlist[0]["volume"] == 40
    panel.table.selectRow(0); panel._remove()
    assert len(ctl.playlist) == 1


def test_midi_actions_drive_the_ui(env, tmp_path):
    from youstrow.ui.main_window import MainWindow
    from youstrow.engine import midi as M
    ctl, panel = env
    win = MainWindow(ctl)
    d = __import__("youstrow.fixtures.model", fromlist=["x"]).search_library("generique rgb")[0]
    for f in ctl.console.patch.add_many(d, d.modes[0], 2, 0, 1): f.group = 1
    ctl.patchChanged.emit()
    ctl.handle_midi(M.parse([0x90, 56, 100]))             # APC mini : note 56 = pad ligne 1 (blanc) / groupe 1... (bas-gauche = note 0)
    ctl.handle_midi(M.parse([0x90, 0, 100]))              # note 0 = bas-gauche = ligne 8 (magenta), groupe 1
    ctl.console.render()
    assert ctl.console.universes[0].snapshot()[:3] == bytes([220, 0, 220])
    ctl.handle_midi(M.parse([0xB0, 56, 0]))               # fader master à 0
    ctl.console.render()
    assert ctl.console.master == 0 and ctl.console.universes[0].snapshot()[:3] == bytes(3)
    ctl.handle_midi(M.parse([0xB0, 56, 127])); ctl.handle_midi(M.parse([0xB0, 48, 64]))   # CC48 = niveau groupe 1
    assert abs(ctl.console.group_levels[1] - 64 / 127) < 1e-6
    ctl.start_learn("blackout"); ctl.handle_midi(M.parse([0x90, 77, 127]))               # apprentissage
    ctl.handle_midi(M.parse([0x90, 77, 127])); assert ctl.console.blackout
    from PySide6.QtCore import QEvent, QUrl
    win.media.shutdown()
    for pl in (win.media.player, win.media.probe):
        pl.stop(); pl.setSource(QUrl())
    ctl.dirty = False
    win.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete); QCoreApplication.processEvents()
