"""Point d'entrée : python -m youstrow"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import QByteArray, Qt
from pathlib import Path

from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import QApplication

from .controller import AppController
from .ui import theme as T
from .ui.main_window import MainWindow


def _icon() -> QIcon:
    for base in (Path(getattr(sys, '_MEIPASS', '')), Path(__file__).resolve().parents[1]):
        f = base / 'assets' / 'youstrow.png'
        if f.exists():
            return QIcon(str(f))
    return QIcon()


_configured = False


def build_app(argv=None) -> QApplication:
    """Crée (ou récupère) la QApplication et applique le thème UNE seule fois : ré-appliquer icône/style/feuille de style
    à des fenêtres existantes (avec vidéo) peut bloquer."""
    global _configured
    app = QApplication.instance() or QApplication(argv or sys.argv)
    if _configured:
        return app
    _configured = True
    app.setStyle("Fusion")
    app.setApplicationName("YouStrow")
    app.setWindowIcon(_icon())
    pal = QPalette()
    for role, col in ((QPalette.Window, T.BG), (QPalette.Base, T.PANEL), (QPalette.AlternateBase, T.RAISED), (QPalette.Button, T.RAISED),
                      (QPalette.WindowText, T.TEXT), (QPalette.Text, T.TEXT), (QPalette.ButtonText, T.TEXT), (QPalette.ToolTipBase, T.RAISED),
                      (QPalette.ToolTipText, T.TEXT), (QPalette.Highlight, T.ACCENT_DIM), (QPalette.HighlightedText, T.TEXT)):
        pal.setColor(role, QColor(col))
    app.setPalette(pal)
    app.setFont(T.app_font(10))
    app.setStyleSheet(T.STYLESHEET)
    return app


def main(argv=None) -> int:
    app = build_app(argv)
    ctl = AppController()
    win = MainWindow(ctl)
    geo = ctl.settings.data.get("geometry")
    if geo:
        win.restoreGeometry(QByteArray.fromBase64(geo.encode()))
    win.show()
    ctl.start()
    args = [a for a in (argv or sys.argv)[1:] if a.lower().endswith('.ysshow')]
    if args:                                   # double-clic sur un show (association de fichier)
        win._open_path(args[0])
    app.aboutToQuit.connect(ctl.shutdown)
    code = app.exec()
    # Les sorties DMX sont déjà coupées (noir envoyé) et les réglages enregistrés. On quitte sans attendre le démontage
    # des lecteurs multimédia Qt/FFmpeg, qui peut laisser un processus « zombie » après la fermeture de la fenêtre.
    sys.stdout and sys.stdout.flush()
    os._exit(code)


if __name__ == "__main__":
    sys.exit(main())
