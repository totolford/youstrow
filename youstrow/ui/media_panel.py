"""Lecteur audio/vidéo : playlist, transport, volume par piste, vidéo détachable, effet lumineux par piste."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Qt, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QSlider, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..controller import AppController
from . import theme as T
from .widgets import GradientSlider

AUDIO_EXT = {".mp3", ".wav", ".flac", ".ogg", ".oga", ".m4a", ".aac", ".wma", ".opus"}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".wmv"}
MEDIA_FILTER = "Médias (" + " ".join("*" + e for e in sorted(AUDIO_EXT | VIDEO_EXT)) + ");;Tous (*)"
NO_EFFECT = "—"


def fmt_ms(ms: int) -> str:
    s = max(0, int(ms // 1000))
    return f"{s // 60}:{s % 60:02d}"


class VideoWindow(QWidget):
    closed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouStrow — Vidéo")
        self.resize(960, 540)
        self.setStyleSheet("background:#000")

    def closeEvent(self, e):
        self.closed.emit(); super().closeEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
        elif e.key() == Qt.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()


class MediaPanel(QWidget):
    def __init__(self, ctl: AppController, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.current = -1
        self._light_effect: str | None = None
        self._seeking = False
        self._detached: VideoWindow | None = None
        self.setAcceptDrops(True)

        self.audio = QAudioOutput(self); self.player = QMediaPlayer(self); self.player.setAudioOutput(self.audio)
        self.video = QVideoWidget(); self.video.setMinimumHeight(170); self.player.setVideoOutput(self.video)
        self.probe = QMediaPlayer(self); self._probe_queue: list[str] = []; self._probe_path = ""
        self._probe_timer = QTimer(self); self._probe_timer.setSingleShot(True); self._probe_timer.setInterval(3000)

        lay = QVBoxLayout(self); lay.setContentsMargins(14, 14, 14, 14); lay.setSpacing(8)
        top = QHBoxLayout(); t = QLabel("PLAYLIST AUDIO / VIDÉO"); t.setObjectName("section"); top.addWidget(t); top.addStretch(1)
        self.add_btn = QPushButton("＋ Ajouter"); self.rm_btn = QPushButton("Retirer"); self.up_btn = QPushButton("▲"); self.dn_btn = QPushButton("▼")
        for b in (self.add_btn, self.rm_btn, self.up_btn, self.dn_btn): top.addWidget(b)
        lay.addLayout(top)

        self.table = QTableWidget(0, 5); self.table.setHorizontalHeaderLabels(["", "Titre", "Durée", "Vol %", "Lumière"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False); self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        h = self.table.horizontalHeader(); h.setSectionResizeMode(QHeaderView.ResizeToContents); h.setSectionResizeMode(1, QHeaderView.Stretch)
        lay.addWidget(self.table, 1)
        self.hint = QLabel("Glissez des fichiers audio/vidéo ici, ou « Ajouter ». Double-clic pour lire."); self.hint.setObjectName("muted"); lay.addWidget(self.hint)

        vrow = QHBoxLayout(); vt = QLabel("VIDÉO"); vt.setObjectName("section"); vrow.addWidget(vt); vrow.addStretch(1)
        self.detach_btn = QPushButton("Fenêtre vidéo"); self.detach_btn.setCheckable(True); self.detach_btn.setToolTip("Détacher la vidéo (F11 = plein écran dans cette fenêtre)")
        vrow.addWidget(self.detach_btn); lay.addLayout(vrow)
        self.vholder = QVBoxLayout(); self.vholder.addWidget(self.video); lay.addLayout(self.vholder)

        seek = QHBoxLayout()
        self.pos_lbl = QLabel("0:00"); self.dur_lbl = QLabel("0:00")
        self.seek = GradientSlider([(0, T.ACCENT), (1, T.ACCENT)]); seek.addWidget(self.pos_lbl); seek.addWidget(self.seek, 1); seek.addWidget(self.dur_lbl)
        lay.addLayout(seek)
        ctl_row = QHBoxLayout(); ctl_row.setSpacing(8)
        self.prev_btn, self.play_btn, self.stop_btn, self.next_btn = QPushButton("⏮"), QPushButton("▶"), QPushButton("⏹"), QPushButton("⏭")
        self.play_btn.setObjectName("primary"); self.play_btn.setFixedWidth(64)
        for b in (self.prev_btn, self.play_btn, self.stop_btn, self.next_btn): ctl_row.addWidget(b)
        ctl_row.addStretch(1)
        self.repeat = QComboBox(); self.repeat.addItems(["Pas de répétition", "Répéter la playlist", "Répéter la piste"]); ctl_row.addWidget(self.repeat)
        ctl_row.addWidget(QLabel("Volume"))
        self.vol = QSlider(Qt.Horizontal); self.vol.setRange(0, 100); self.vol.setValue(80); self.vol.setFixedWidth(120)
        self.vol.setStyleSheet(f"QSlider::groove:horizontal{{height:6px;background:{T.RAISED_HI};border-radius:3px}}"
                               f"QSlider::sub-page:horizontal{{background:{T.ACCENT};border-radius:3px}}"
                               f"QSlider::handle:horizontal{{width:16px;height:16px;margin:-5px 0;border-radius:8px;background:#f5f7fa}}")
        ctl_row.addWidget(self.vol); lay.addLayout(ctl_row)

        self.add_btn.clicked.connect(self._add_dialog); self.rm_btn.clicked.connect(self._remove)
        self.up_btn.clicked.connect(lambda: self._move(-1)); self.dn_btn.clicked.connect(lambda: self._move(1))
        self.table.cellDoubleClicked.connect(lambda r, _c: self.play_index(r))
        self.play_btn.clicked.connect(self.toggle_play); self.stop_btn.clicked.connect(self.stop)
        self.next_btn.clicked.connect(self.next); self.prev_btn.clicked.connect(self.prev)
        self.vol.valueChanged.connect(lambda _v: self._apply_volume())
        self.seek.valueChanged.connect(self._seek_to)
        self.detach_btn.toggled.connect(self._detach)
        # Connexions DIFFÉRÉES : le backend FFmpeg émet ses signaux depuis setSource()/play() ; y faire du travail d'interface
        # (ou relancer une lecture) en direct peut le bloquer.
        q = Qt.QueuedConnection
        self.player.positionChanged.connect(self._on_position, q); self.player.durationChanged.connect(self._on_duration, q)
        self.player.playbackStateChanged.connect(self._on_state, q); self.player.mediaStatusChanged.connect(self._on_status, q)
        self.player.errorOccurred.connect(self._on_error, q)
        self.probe.durationChanged.connect(self._probe_duration, q); self._probe_timer.timeout.connect(self._probe_next)
        ctl.playlistChanged.connect(self.reload)
        self.reload()

    # ----------------------------------------------------------------- playlist
    def _items(self) -> list[dict]:
        return self.ctl.playlist

    def reload(self):
        self.table.setRowCount(len(self._items()))
        for r, it in enumerate(self._items()):
            self._fill_row(r, it)
        self.hint.setVisible(not self._items())
        self._enqueue_probes()

    def _fill_row(self, r, it):
        mark = QTableWidgetItem("▶" if r == self.current and self.player.playbackState() == QMediaPlayer.PlayingState else "")
        mark.setForeground(Qt.cyan)
        self.table.setItem(r, 0, mark)
        title = QTableWidgetItem(it.get("title") or Path(it["path"]).stem)
        if not Path(it["path"]).exists():
            title.setForeground(Qt.red); title.setToolTip("Fichier introuvable : " + it["path"])
        self.table.setItem(r, 1, title)
        self.table.setItem(r, 2, QTableWidgetItem(fmt_ms(it["duration_ms"]) if it.get("duration_ms") else "—"))
        sp = QSpinBox(); sp.setRange(0, 100); sp.setSuffix("%"); sp.setValue(int(it.get("volume", 100)))
        sp.valueChanged.connect(lambda v, it=it: self._set_item(it, "volume", v))
        self.table.setCellWidget(r, 3, sp)
        cb = QComboBox(); cb.addItem(NO_EFFECT); cb.addItems([e.name for e in self.ctl.effects])
        i = cb.findText(it.get("effect", "")); cb.setCurrentIndex(max(0, i))
        cb.currentTextChanged.connect(lambda t, it=it: self._set_item(it, "effect", "" if t == NO_EFFECT else t))
        self.table.setCellWidget(r, 4, cb)

    def _refresh_light_cells(self):
        for r, it in enumerate(self._items()):
            cb = self.table.cellWidget(r, 4)
            if cb:
                cb.blockSignals(True); cb.clear(); cb.addItem(NO_EFFECT); cb.addItems([e.name for e in self.ctl.effects])
                cb.setCurrentIndex(max(0, cb.findText(it.get("effect", "")))); cb.blockSignals(False)

    def _set_item(self, it, key, val):
        it[key] = val
        self.ctl.dirty = True
        if key == "volume":
            self._apply_volume()
        if key == "effect" and self._items() and self.current >= 0 and self._items()[self.current] is it:
            self._start_light(it)

    def add_files(self, paths):
        known = {it["path"] for it in self._items()}
        added = 0
        for p in paths:
            ext = Path(p).suffix.lower()
            if ext in AUDIO_EXT | VIDEO_EXT and p not in known:
                self._items().append({"path": str(p), "title": Path(p).stem, "volume": 100, "effect": "", "duration_ms": 0,
                                      "video": ext in VIDEO_EXT})
                known.add(p)
                added += 1
        if added:
            self.ctl.dirty = True
            self.ctl.log("ok", f"Playlist : {added} fichier(s) ajouté(s)")
            self.reload()
        return added

    def _add_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Ajouter des médias", "", MEDIA_FILTER)
        self.add_files(files)

    def _remove(self):
        r = self.table.currentRow()
        if 0 <= r < len(self._items()):
            if r == self.current:
                self.stop(); self.current = -1
            elif r < self.current:
                self.current -= 1
            del self._items()[r]; self.ctl.dirty = True; self.reload()

    def _move(self, d):
        r = self.table.currentRow(); n = r + d
        if 0 <= r < len(self._items()) and 0 <= n < len(self._items()):
            it = self._items(); it[r], it[n] = it[n], it[r]
            if self.current == r: self.current = n
            elif self.current == n: self.current = r
            self.ctl.dirty = True; self.reload(); self.table.selectRow(n)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()

    def dropEvent(self, e):
        self.add_files([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    # ----------------------------------------------------------------- durées
    def _enqueue_probes(self):
        self._probe_queue = [it["path"] for it in self._items() if not it.get("duration_ms") and Path(it["path"]).exists()]
        if self._probe_queue and not self._probe_timer.isActive() and not self._probe_path:
            self._probe_next()

    def _probe_next(self):
        self._probe_path = ""
        while self._probe_queue:
            p = self._probe_queue.pop(0)
            if any(it["path"] == p and not it.get("duration_ms") for it in self._items()):
                self._probe_path = p
                self.probe.stop(); self.probe.setSource(QUrl.fromLocalFile(p)); self._probe_timer.start()
                return
        self._probe_timer.stop()

    def _probe_duration(self, ms):
        if ms > 0 and self._probe_path:
            for r, it in enumerate(self._items()):
                if it["path"] == self._probe_path:
                    it["duration_ms"] = ms
                    if self.table.item(r, 2): self.table.item(r, 2).setText(fmt_ms(ms))
            self._probe_timer.stop(); self._probe_path = ""
            QTimer.singleShot(0, self._probe_next)      # jamais de setSource() depuis le signal du même lecteur (crash FFmpeg)

    # ---------------------------------------------------------------- lecture
    def _apply_volume(self):
        item = self._items()[self.current].get("volume", 100) if 0 <= self.current < len(self._items()) else 100
        self.audio.setVolume(self.vol.value() / 100 * item / 100)

    def play_index(self, i: int):
        if not 0 <= i < len(self._items()):
            return
        it = self._items()[i]
        if not Path(it["path"]).exists():
            self.ctl.log("err", f"Média introuvable : {it['path']}"); return
        self.current = i
        self._stop_light()
        self.player.setSource(QUrl.fromLocalFile(it["path"]))
        self._apply_volume(); self.player.play()
        self.table.selectRow(i)
        self.ctl.log("info", f"Lecture : {it.get('title')}")
        self._start_light(it)

    def toggle_play(self):
        st = self.player.playbackState()
        if st == QMediaPlayer.PlayingState:
            self.player.pause()
        elif st == QMediaPlayer.PausedState:
            self.player.play()
        else:
            self.play_index(self.current if self.current >= 0 else max(0, self.table.currentRow()))

    def stop(self):
        self.player.stop(); self._stop_light()

    def next(self):
        n = len(self._items())
        if n: self.play_index((self.current + 1) % n)

    def prev(self):
        n = len(self._items())
        if n:
            if self.player.position() > 3000: self.player.setPosition(0)
            else: self.play_index((self.current - 1) % n)

    def _on_status(self, st):
        if st == QMediaPlayer.EndOfMedia:
            mode = self.repeat.currentIndex()
            if mode == 2: self.player.setPosition(0); self.player.play()
            elif self.current + 1 < len(self._items()) or mode == 1: self.next()
            else: self._stop_light()

    def _on_state(self, st):
        self.play_btn.setText("⏸" if st == QMediaPlayer.PlayingState else "▶")
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0):
                self.table.item(r, 0).setText("▶" if r == self.current and st == QMediaPlayer.PlayingState else ("⏸" if r == self.current and st == QMediaPlayer.PausedState else ""))

    def _on_position(self, ms):
        self.pos_lbl.setText(fmt_ms(ms))
        d = self.player.duration()
        if d > 0 and not self._seeking:
            self.seek.setValue(ms / d)

    def _on_duration(self, ms):
        self.dur_lbl.setText(fmt_ms(ms))
        if 0 <= self.current < len(self._items()) and ms > 0:
            self._items()[self.current]["duration_ms"] = ms
            if self.table.item(self.current, 2): self.table.item(self.current, 2).setText(fmt_ms(ms))

    def _seek_to(self, v):
        d = self.player.duration()
        if d > 0:
            self._seeking = True; self.player.setPosition(int(v * d)); self._seeking = False

    def _on_error(self, err, msg):
        if err != QMediaPlayer.NoError:
            self.ctl.log("err", f"Lecteur : {msg or err}")

    # ---------------------------------------------------------------- lumière
    def _start_light(self, it):
        self._stop_light()
        name = it.get("effect", "")
        eff = next((e for e in self.ctl.effects if e.name == name), None)
        if eff:
            self.ctl.console.start_effect(eff, 1.0, self.ctl.fx_speed, None)
            self._light_effect = eff.name
            self.ctl.log("info", f"Lumière : effet « {eff.name} » lancé avec la piste")
            self.ctl.stateChanged.emit()

    def _stop_light(self):
        if self._light_effect:
            self.ctl.console.stop_effect(self._light_effect); self._light_effect = None
            self.ctl.stateChanged.emit()

    # ------------------------------------------------------------------ vidéo
    def _detach(self, on):
        if on:
            self._detached = VideoWindow(); lay = QVBoxLayout(self._detached); lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(self.video); self._detached.closed.connect(lambda: self.detach_btn.setChecked(False)); self._detached.show()
        elif self._detached:
            self.vholder.addWidget(self.video); self.video.show()
            w, self._detached = self._detached, None; w.closed.disconnect(); w.close()

    def shutdown(self):
        self.stop(); self.probe.stop()
        self._probe_queue.clear(); self._probe_timer.stop()
        for pl in (self.player, self.probe):          # libère les fichiers et arrête les threads du backend
            pl.setSource(QUrl())
        if self._detached: self._detach(False)
