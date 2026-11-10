"""Panneaux détachables : n'importe quel panneau peut sortir dans sa propre fenêtre, sur l'écran de son choix, en fenêtre
ou en plein écran, puis être rapatrié. Un panneau détaché laisse un repère « affiché dans une fenêtre externe »."""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


def all_screens():
    return QGuiApplication.screens()


def screen_label(i: int, screen) -> str:
    g = screen.geometry()
    main = " · principal" if screen == QGuiApplication.primaryScreen() else ""
    return f"Écran {i + 1} · {g.width()}×{g.height()}{main}"


def screen_by_index(i: int):
    s = all_screens()
    return s[i] if 0 <= i < len(s) else QGuiApplication.primaryScreen()


def place_on_screen(win: QWidget, screen, fullscreen: bool = False) -> None:
    """Affiche `win` sur `screen`. En plein écran : couvre tout l'écran, sans bordure de fenêtre."""
    g = screen.geometry()
    if not fullscreen:
        win.resize(min(win.width() or 1100, g.width() - 120), min(win.height() or 700, g.height() - 120))
        win.move(g.topLeft() + QPoint(60, 60))
    else:
        win.move(g.topLeft())                       # le plein écran Windows suit l'écran qui contient la fenêtre
    win.show()
    h = win.windowHandle()
    if h is not None:
        h.setScreen(screen)
    if fullscreen:
        win.setGeometry(g)
        win.showFullScreen()


class FloatingWindow(QWidget):
    closed = Signal()

    def __init__(self, title: str, content: QWidget):
        super().__init__(None, Qt.Window)
        self.setWindowTitle(f"YouStrow — {title}")
        self.setObjectName("root")
        lay = QVBoxLayout(self); lay.setContentsMargins(10, 10, 10, 10)
        lay.addWidget(content)
        self.content = content
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        QShortcut(QKeySequence("Esc"), self, activated=lambda: self.isFullScreen() and self.showNormal())

    def toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def closeEvent(self, e):
        self.closed.emit()
        super().closeEvent(e)


class PanelHost(QFrame):
    """Conteneur d'un panneau. `detach()` le sort dans une fenêtre ; `attach()` le ramène."""
    detachedChanged = Signal(bool)

    def __init__(self, name: str, content: QWidget, parent=None):
        super().__init__(parent)
        self.name, self.content, self.window_ = name, content, None
        self._lay = QVBoxLayout(self); self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.addWidget(content)
        self._ph = QFrame(); self._ph.setObjectName("card")
        pl = QVBoxLayout(self._ph); pl.setAlignment(Qt.AlignCenter)
        t = QLabel(f"« {name} » est affiché dans une fenêtre externe"); t.setObjectName("muted"); t.setAlignment(Qt.AlignCenter)
        b = QPushButton("Rapatrier ici"); b.clicked.connect(self.attach)
        pl.addWidget(t); pl.addWidget(b, 0, Qt.AlignCenter)
        self._ph.hide(); self._lay.addWidget(self._ph)
        self.setSizePolicy(content.sizePolicy())

    @property
    def is_detached(self) -> bool:
        return self.window_ is not None

    def detach(self, screen=None, fullscreen: bool = False) -> None:
        if self.window_ is None:
            self._lay.removeWidget(self.content)
            self.window_ = FloatingWindow(self.name, self.content)
            self.window_.closed.connect(self._on_window_closed)
            self._ph.show()
            self.detachedChanged.emit(True)
        place_on_screen(self.window_, screen or QGuiApplication.primaryScreen(), fullscreen)

    def attach(self) -> None:
        w, self.window_ = self.window_, None
        if w is None:
            return
        w.closed.disconnect(self._on_window_closed)
        self._ph.hide()
        self._lay.insertWidget(0, self.content)
        self.content.show()
        w.close(); w.deleteLater()
        self.detachedChanged.emit(False)

    def _on_window_closed(self):
        self.attach()
