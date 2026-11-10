"""Plan de feu 3D : rendu Three.js dans QtWebEngine, alimenté en direct par la console DMX.

Le moteur 3D (index.html + vendor/three + scenes3d) est servi par un petit serveur HTTP local (127.0.0.1) : les modules
JavaScript ne se chargent pas depuis file:// dans Chromium. Si les fichiers 3D ne sont pas présents (dépôt cloné sans
les ressources d'origine) ou si QtWebEngine manque, le panneau l'indique au lieu de planter."""
from __future__ import annotations

import base64
import json
import threading
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PySide6.QtCore import QObject, QSize, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QScrollArea, QSlider, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from ..controller import AppController
from . import theme as T
from .widgets import fixture_display_color

try:
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE = True
except Exception:  # noqa: BLE001 — QtWebEngine absent : le panneau 3D se désactive
    WEBENGINE = False

WEB_ROOT = Path(__file__).resolve().parents[1] / "resources" / "web3d"
PLAN_W, PLAN_D = 18.0, 10.0           # largeur / profondeur du plan 2D (mètres) — comme le gabarit du moteur 3D


@dataclass(frozen=True)
class Scene3D:
    code: str
    label: str
    rig_height: float
    glb: str | None = None
    yaw: float = 0.0
    span: float = 18.0
    note: str = ""


SCENES = [
    Scene3D("vide", "Aucun décor", 7.0, note="Scène nue"),
    Scene3D("concert_glb", "Scène de concert", 8.7, "concert_stage.glb", 180.0, 16.2, "Modèle 3D"),
    Scene3D("scene_6x5", "Scène 6×5 m", 3.7, "scene_6x5.glb", 0.0, 8.2, "Modèle 3D"),
    Scene3D("festival_plein_air", "Festival plein air", 8.0),
    Scene3D("discotheque", "Discothèque", 4.8),
    Scene3D("dj_mobile", "DJ mobile", 2.05),
    Scene3D("conference", "Conférence", 4.9),
    Scene3D("sapin_noel", "Sapin de Noël", 7.0),
]
SCENE_BY_CODE = {s.code: s for s in SCENES}
DEFAULT_SCENE = "festival_plein_air"


def web_assets_present() -> bool:
    return (WEB_ROOT / "index.html").exists() and (WEB_ROOT / "vendor" / "three" / "three.module.js").exists()


# ------------------------------------------------------------------ serveur local
class _Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript", ".mjs": "text/javascript",
                      ".glb": "model/gltf-binary", ".html": "text/html", ".png": "image/png"}

    def log_message(self, *a):          # silence
        pass

    def _send(self, data: bytes, ctype: str):
        self.send_response(200); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data)))
        self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/qwebchannel.js":          # la page est en http:// : elle ne peut pas lire qrc:// directement
            from PySide6.QtCore import QFile, QIODevice
            f = QFile(":/qtwebchannel/qwebchannel.js")
            if f.open(QIODevice.ReadOnly):
                return self._send(bytes(f.readAll()), "text/javascript")
            return self.send_error(404)
        if path in ("/", "/index.html"):
            html = (Path(self.directory) / "index.html").read_text(encoding="utf-8")
            return self._send(html.replace("qrc:///qtwebchannel/qwebchannel.js", "/qwebchannel.js").encode("utf-8"), "text/html; charset=utf-8")
        return super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):   # connexions coupées par le navigateur : sans importance
        pass


_server: ThreadingHTTPServer | None = None
_server_lock = threading.Lock()


def server_port() -> int:
    global _server
    with _server_lock:
        if _server is None:
            _server = _Server(("127.0.0.1", 0), partial(_Handler, directory=str(WEB_ROOT)))
            threading.Thread(target=_server.serve_forever, name="web3d-http", daemon=True).start()
        return _server.server_address[1]


# --------------------------------------------------------------- données projecteurs
def world_pos(fx) -> tuple[float, float]:
    """Plan 2D (0..1) -> mètres. Jardin = X positifs ; la face (bas du plan) est en Z négatif."""
    return -(fx.x - 0.5) * PLAN_W, (0.5 - fx.y) * PLAN_D


def from_world(x: float, z: float) -> tuple[float, float]:
    return min(max(0.5 - x / PLAN_W, 0.0), 1.0), min(max(0.5 - z / PLAN_D, 0.0), 1.0)


def projectors_from_console(console, rig_height: float) -> list[dict]:
    """Une entrée par appareil patché, au format attendu par `updateScene()` du moteur 3D."""
    snaps = [u.snapshot() for u in console.universes]
    out = []
    for fx in console.patch.fixtures:
        vals = list(snaps[fx.universe][fx.address - 1: fx.end_address]) if 0 <= fx.universe < len(snaps) else []
        r, g, b, inten = fixture_display_color(fx.channels, vals) if vals else (0, 0, 0, 0.0)
        d = dict(zip(fx.channels, vals))
        x, z = world_pos(fx)
        moving = "Pan" in fx.channels or "Tilt" in fx.channels

        def sixteen(coarse, fine):
            if coarse not in d:
                return 32768
            return d[coarse] * 256 + (d.get(fine, 0) if fine in d else d[coarse])   # 8 bits seuls : 0..255 -> 0..65535

        out.append({
            "x": x, "z": z, "fixture_height": fx.height_cm / 100.0 if fx.height_cm else rig_height,
            "r": r, "g": g, "b": b, "level": round(inten * 100, 1),
            "pan": sixteen("Pan", "PanFine"), "tilt": sixteen("Tilt", "TiltFine"),
            "fixture_type": "Moving Head" if moving else (fx.fixture_type if fx.fixture_type == "Barre LED" else "PAR LED"),
            "group": f"g{fx.group}" if fx.group else None, "fixture_scale": 1.0, "beam_angle": 1.0,
            "rot3d_x": 0, "rot3d_y": 0, "rot3d_z": 0, "has_gobo": False, "has_zoom": False, "has_focus": False,
        })
    return out


# -------------------------------------------------------------------- vue WebEngine
if WEBENGINE:
    class _Bridge(QObject):
        selected = Signal(int)

        @Slot(int)
        def projoSelected(self, idx):
            self.selected.emit(idx)

        @Slot(str, str)
        def saveGlitchShot(self, url, reason):      # diagnostic du moteur : ignoré
            pass

    class _Page(QWebEnginePage):
        def __init__(self, ctl, parent=None):
            super().__init__(parent)
            self._ctl = ctl

        def javaScriptConsoleMessage(self, level, message, line, source):
            if level == QWebEnginePage.ErrorMessageLevel:
                self._ctl.log("err", f"3D : {message} ({Path(source).name}:{line})")

    class Plan3DView(QWebEngineView):
        projectorClicked = Signal(int)   # index dans patch.fixtures
        readyChanged = Signal(bool)

        def __init__(self, ctl: AppController, parent=None):
            super().__init__(parent)
            self.ctl, self.ready, self.scene_code, self._last = ctl, False, None, ""
            self.setPage(_Page(ctl, self))
            s = self.page().settings()
            s.setAttribute(QWebEngineSettings.WebGLEnabled, True)
            s.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
            self.page().setBackgroundColor(QColor("#05060e"))
            self.bridge = _Bridge(self); self.bridge.selected.connect(self.projectorClicked)
            self.channel = QWebChannel(self.page()); self.channel.registerObject("bridge", self.bridge); self.page().setWebChannel(self.channel)
            self._poll = QTimer(self); self._poll.setInterval(250); self._poll.timeout.connect(self._check_ready)
            self._tick = QTimer(self); self._tick.setInterval(40); self._tick.timeout.connect(self.push)
            self.pending_scene = DEFAULT_SCENE
            self.setUrl(QUrl(f"http://127.0.0.1:{server_port()}/index.html"))
            self._poll.start()

        def _check_ready(self):
            self.page().runJavaScript("typeof window.updateScene==='function'&&typeof window.setScenePreset==='function'&&!!window._bridge",
                                      0, self._on_ready_probe)

        def _on_ready_probe(self, ok):
            if ok and not self.ready:
                self.ready = True; self._poll.stop(); self._tick.start()
                self.set_scene(self.pending_scene); self.readyChanged.emit(True)

        # --- API
        def js(self, code: str, cb=None):
            if cb:
                self.page().runJavaScript(code, 0, cb)
            else:
                self.page().runJavaScript(code)

        def set_scene(self, code: str):
            self.pending_scene = code
            if not self.ready:
                return
            sc = SCENE_BY_CODE.get(code, SCENES[0]); self.scene_code = code
            self.js(f"window.setScenePreset({json.dumps(code)});")
            glb = WEB_ROOT / "scenes3d" / sc.glb if sc.glb else None
            if glb and glb.exists():
                b64 = base64.b64encode(glb.read_bytes()).decode("ascii")
                self.js(f"window.setStageFloor(false); window.loadSceneGLB({json.dumps(b64)}, {sc.yaw}, {sc.span});")
            else:
                self.js("window.clearSceneGLB(); window.setStageFloor(true); window.setCyclorama(false);")
            self._last = ""

        def rig_height(self) -> float:
            return SCENE_BY_CODE.get(self.scene_code or self.pending_scene, SCENES[0]).rig_height

        def push(self):
            if not self.ready or not self.isVisible():
                return
            payload = json.dumps(projectors_from_console(self.ctl.console, self.rig_height()), separators=(",", ":"))
            if payload != self._last:
                self._last = payload
                self.js(f"window.updateScene({payload});")

        def snapshot(self, cb):
            self.js("window.snapshot()", cb)
else:
    Plan3DView = None  # type: ignore[assignment,misc]


# ------------------------------------------------------------------------ panneau
class SceneCard(QFrame):
    clicked = Signal(str)

    def __init__(self, scene: Scene3D):
        super().__init__()
        self.scene, self.selected = scene, False
        self.setCursor(Qt.PointingHandCursor); self.setFixedHeight(166)
        img = WEB_ROOT / "scenes3d" / "vignettes" / f"{scene.code}_iso.png"
        self.pix = QPixmap(str(img)) if img.exists() else QPixmap()

    def set_selected(self, on):
        self.selected = on; self.update()

    def mousePressEvent(self, e):
        self.clicked.emit(self.scene.code)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(T.ACCENT if self.selected else T.BORDER), 2 if self.selected else 1)); p.setBrush(QColor(T.RAISED)); p.drawRoundedRect(r, 12, 12)
        pv = r.adjusted(8, 8, -8, -(r.height() - 108))
        if not self.pix.isNull():
            p.save(); path = __import__("PySide6.QtGui", fromlist=["QPainterPath"]).QPainterPath(); path.addRoundedRect(pv, 8, 8); p.setClipPath(path)
            sc = self.pix.scaled(pv.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap(pv.topLeft(), sc, sc.rect().adjusted((sc.width() - pv.width()) // 2, (sc.height() - pv.height()) // 2, -(sc.width() - pv.width()) // 2, -(sc.height() - pv.height()) // 2)); p.restore()
        else:
            p.setPen(Qt.NoPen); p.setBrush(QColor("#0B1020")); p.drawRoundedRect(pv, 8, 8)
        p.setPen(QColor(T.TEXT)); f = p.font(); f.setPointSize(9); f.setBold(True); p.setFont(f)
        p.drawText(r.adjusted(10, 114, -8, 0), Qt.AlignLeft | Qt.AlignTop, self.scene.label)
        f.setBold(False); f.setPointSize(8); p.setFont(f); p.setPen(QColor(T.MUTED))
        p.drawText(r.adjusted(10, 134, -8, 0), Qt.AlignLeft | Qt.AlignTop, f"{self.scene.note + ' · ' if self.scene.note else ''}accroche {self.scene.rig_height:g} m".replace(".", ","))


def _slider(lo, hi, val):
    s = QSlider(Qt.Horizontal); s.setRange(lo, hi); s.setValue(val)
    s.setStyleSheet(f"QSlider::groove:horizontal{{height:6px;background:{T.RAISED_HI};border-radius:3px}}"
                    f"QSlider::sub-page:horizontal{{background:{T.ACCENT};border-radius:3px}}"
                    f"QSlider::handle:horizontal{{width:16px;height:16px;margin:-5px 0;border-radius:8px;background:#f5f7fa}}")
    return s


class Plan3DPanel(QWidget):
    """Vue 3D + panneau Caméra / Plan / Décor (maquette Figma « Plan 3D »)."""

    def __init__(self, ctl: AppController, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(16)
        self.view = None
        left = QFrame(); left.setObjectName("card"); ll = QVBoxLayout(left); ll.setContentsMargins(12, 12, 12, 12); ll.setSpacing(10)
        tools = QHBoxLayout(); tools.setSpacing(6)
        self.cam_btns = {}
        for code, label in (("iso", "Iso"), ("front", "Face"), ("top", "Dessus"), ("side", "Côté")):
            b = QPushButton(label); b.setCheckable(True); b.clicked.connect(lambda _=False, c=code: self.set_cam(c)); tools.addWidget(b); self.cam_btns[code] = b
        self.cam_btns["iso"].setChecked(True)
        tools.addStretch(1)
        self.fps = QLabel(""); self.fps.setObjectName("muted"); tools.addWidget(self.fps)
        self.detach_btn = QPushButton("Fenêtre détachée"); self.full_btn = QPushButton("Plein écran")
        tools.addWidget(self.detach_btn); tools.addWidget(self.full_btn)
        ll.addLayout(tools)
        self.holder = QVBoxLayout(); ll.addLayout(self.holder, 1)
        hint = QLabel("Glisser : orbite · Molette : zoom · Double-clic : réinitialiser"); hint.setObjectName("muted"); ll.addWidget(hint)
        lay.addWidget(left, 1)

        self.tabs = QTabWidget(); right = QFrame(); right.setObjectName("card"); right.setFixedWidth(420)
        rl = QVBoxLayout(right); rl.setContentsMargins(0, 4, 0, 0); rl.addWidget(self.tabs)
        self._build_cam_tab(); self._build_plan_tab(); self._build_scene_tab()
        self.tabs.setCurrentIndex(2)
        lay.addWidget(right)

        if not WEBENGINE or not web_assets_present():
            why = ("QtWebEngine n'est pas disponible." if not WEBENGINE else
                   "Les fichiers 3D (index.html, scènes) sont absents de cette installation.\n"
                   "Ils proviennent de l'application d'origine et ne sont pas inclus dans le dépôt public.")
            msg = QLabel("Plan 3D indisponible\n\n" + why); msg.setAlignment(Qt.AlignCenter); msg.setObjectName("muted"); self.holder.addWidget(msg)
        else:
            self.view = Plan3DView(ctl); self.holder.addWidget(self.view)
            self.view.readyChanged.connect(lambda _ok: self._apply_defaults())
            self.view.projectorClicked.connect(self._clicked)
            self._fps_t = QTimer(self); self._fps_t.setInterval(1000); self._fps_t.timeout.connect(self._poll_fps); self._fps_t.start()
        ctl.patchChanged.connect(self._fill_plan_table)

    # ------------------------------------------------------------ onglets
    def _page(self, title):
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(16, 12, 16, 12); l.setSpacing(10); self.tabs.addTab(w, title); return l

    def _build_cam_tab(self):
        l = self._page("Caméra")
        l.addWidget(self._sec("VUE"))
        for code, label in (("iso", "Isométrique"), ("front", "Face"), ("top", "Dessus"), ("side", "Côté")):
            b = QPushButton(label); b.clicked.connect(lambda _=False, c=code: self.set_cam(c)); l.addWidget(b)
        l.addWidget(self._sec("RENDU"))
        self.quality = QComboBox(); self.quality.addItems(["Qualité 1 (rapide)", "Qualité 2", "Qualité 3 (maximale)"]); self.quality.setCurrentIndex(1)
        self.quality.currentIndexChanged.connect(lambda i: self._js(f"window.setQuality({i + 1}, true);")); l.addWidget(self.quality)
        self.auto_q = QCheckBox("Baisser la qualité automatiquement si ça rame"); self.auto_q.setChecked(True)
        self.auto_q.toggled.connect(lambda on: self._js(f"window.autoQuality={'true' if on else 'false'};")); l.addWidget(self.auto_q)
        self.show_fps = QCheckBox("Afficher le compteur d'images/s"); self.show_fps.toggled.connect(lambda on: self._js(f"window.showFps({'true' if on else 'false'});")); l.addWidget(self.show_fps)
        exp = QPushButton("Exporter l'image…"); exp.clicked.connect(self.export_image); l.addWidget(exp); l.addStretch(1)

    def _build_plan_tab(self):
        l = self._page("Plan")
        l.addWidget(self._sec("POSITIONNEMENT 3D (mètres)"))
        self.table = QTableWidget(0, 5); self.table.setHorizontalHeaderLabels(["ID", "Nom", "X", "Z", "Haut."])
        self.table.verticalHeader().setVisible(False); self.table.setAlternatingRowColors(True)
        h = self.table.horizontalHeader(); h.setSectionResizeMode(QHeaderView.ResizeToContents); h.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.itemChanged.connect(self._plan_edited); l.addWidget(self.table, 1)
        hint = QLabel("X : + = jardin · Z : + = fond de scène · Haut. : hauteur d'accroche."); hint.setObjectName("muted"); hint.setWordWrap(True); l.addWidget(hint)
        self._loading = False; self._fill_plan_table()

    def _build_scene_tab(self):
        sa = QScrollArea(); sa.setWidgetResizable(True); sa.setFrameShape(QFrame.NoFrame); body = QWidget(); l = QVBoxLayout(body); l.setContentsMargins(16, 12, 16, 12); l.setSpacing(12)
        sa.setWidget(body); self.tabs.addTab(sa, "Décor")
        l.addWidget(self._sec("DÉCOR"))
        grid = QVBoxLayout(); grid.setSpacing(10); self.cards = []
        for i in range(0, len(SCENES), 2):
            row = QHBoxLayout(); row.setSpacing(10)
            for sc in SCENES[i:i + 2]:
                c = SceneCard(sc); c.clicked.connect(self.set_scene); row.addWidget(c); self.cards.append(c)
            grid.addLayout(row)
        l.addLayout(grid)
        imp = QPushButton("Importer une scène 3D (.glb / .gltf)…"); imp.clicked.connect(self.import_scene); l.addWidget(imp)
        clr = QPushButton("Effacer l'import"); clr.clicked.connect(lambda: self._js("window.clearImportedScene();")); l.addWidget(clr)
        l.addWidget(self._sec("AMBIANCE"))
        self._ambiance = {}
        for key, label, lo, hi, val, code in (("fog", "Brouillard", 0, 100, 15, "window.setFog({v});"),
                                              ("fogscale", "Finesse des volutes", 0, 100, 60, "window.setFogScale({v}/100*1.85+0.15);"),
                                              ("fogspeed", "Vitesse de brassage", 0, 100, 35, "window.setFogSpeed({v});"),
                                              ("amb", "Lumière ambiante", 0, 200, 25, "window.setRoomAmbience({v}/100);")):
            r = QHBoxLayout(); r.addWidget(QLabel(label)); v = QLabel(f"{val} %"); v.setObjectName("muted"); r.addStretch(1); r.addWidget(v); l.addLayout(r)
            s = _slider(lo, hi, val); s.valueChanged.connect(lambda x, c=code, vl=v: (vl.setText(f"{x} %"), self._js(c.format(v=x)))); l.addWidget(s); self._ambiance[key] = (s, code)
        self.flags = {}
        for flag, label in (("bloom", "Bloom"), ("floor", "Sol réfléchissant"), ("grid", "Grille"), ("trusses", "Trusses"), ("fixtures", "Appareils"), ("screen", "Écran vidéo / retour")):
            cb = QCheckBox(label); cb.setChecked(True); cb.toggled.connect(lambda _on, f=flag: self._js(f"window.toggleFlag('{f}');")); l.addWidget(cb); self.flags[flag] = cb
        l.addStretch(1)
        self._mark(DEFAULT_SCENE)

    @staticmethod
    def _sec(t):
        x = QLabel(t); x.setObjectName("section"); return x

    # -------------------------------------------------------------- actions
    def _js(self, code):
        if self.view is not None and self.view.ready:
            self.view.js(code)

    def _apply_defaults(self):
        for key, (s, code) in self._ambiance.items():
            self._js(code.format(v=s.value()))
        self._js(f"window.setQuality({self.quality.currentIndex() + 1}, true);")

    def _mark(self, code):
        for c in self.cards:
            c.set_selected(c.scene.code == code)

    def set_scene(self, code):
        self._mark(code)
        if self.view is not None:
            self.view.set_scene(code)
        self.ctl.settings.data["scene3d"] = code
        self.ctl.log("info", f"Décor 3D : {SCENE_BY_CODE[code].label}")

    def set_cam(self, code):
        for k, b in self.cam_btns.items():
            b.setChecked(k == code)
        self._js(f"window.setCam('{code}');")

    def import_scene(self):
        p, _ = QFileDialog.getOpenFileName(self, "Importer une scène 3D", "", "Fichiers 3D (*.glb *.gltf)")
        if p and self.view is not None and self.view.ready:
            b64 = base64.b64encode(Path(p).read_bytes()).decode("ascii")
            self._js(f"window.loadGLTF({json.dumps(b64)}, {'true' if p.lower().endswith('.glb') else 'false'});")
            self.ctl.log("ok", f"Scène 3D importée : {Path(p).name}")

    def export_image(self):
        if self.view is None:
            return
        def done(url):
            if not isinstance(url, str) or not url.startswith("data:image/png;base64,"):
                self.ctl.log("err", f"Export 3D impossible : {url}"); return
            p, _ = QFileDialog.getSaveFileName(self, "Exporter l'image 3D", "plan3d.png", "PNG (*.png)")
            if p:
                Path(p).write_bytes(base64.b64decode(url.split(",", 1)[1])); self.ctl.log("ok", f"Image 3D exportée : {Path(p).name}")
        self.view.snapshot(done)

    def _poll_fps(self):
        if self.view is not None and self.view.ready and self.isVisible():
            self.view.js("window.getFps ? window.getFps() : 0", lambda v: self.fps.setText(f"{float(v or 0):.0f} images/s"))

    def _clicked(self, idx):
        fx = self.ctl.console.patch.fixtures
        if 0 <= idx < len(fx):
            self.ctl.log("info", f"3D : appareil {fx[idx].id} — {fx[idx].name}")

    def _fill_plan_table(self):
        self._loading = True
        fx = self.ctl.console.patch.fixtures
        self.table.setRowCount(len(fx))
        rig = SCENE_BY_CODE.get(getattr(self.view, "scene_code", None) or DEFAULT_SCENE, SCENES[0]).rig_height
        for i, f in enumerate(fx):
            x, z = world_pos(f)
            for c, v in enumerate((f.id, f.name, f"{x:.2f}", f"{z:.2f}", f"{(f.height_cm / 100 if f.height_cm else rig):.2f}")):
                it = QTableWidgetItem(str(v)); it.setData(Qt.UserRole, f.id)
                if c < 2:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, c, it)
        self._loading = False

    def _plan_edited(self, item):
        if self._loading or item.column() < 2:
            return
        f = self.ctl.console.patch.get(item.data(Qt.UserRole))
        if f is None:
            return
        try:
            v = float(item.text().replace(",", "."))
        except ValueError:
            self._fill_plan_table(); return
        x, z = world_pos(f)
        if item.column() == 2:
            f.x, _ = from_world(v, z)
        elif item.column() == 3:
            _, f.y = from_world(x, v)
        else:
            f.height_cm = max(0, round(v * 100))
        self.ctl.touch()
