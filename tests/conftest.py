"""Nettoyage de fin de session : ferme les fenêtres/lecteurs Qt avant la sortie de l'interpréteur
(sinon le démontage de QMediaPlayer/FFmpeg peut bloquer la fin du processus)."""
import os
import sys


def pytest_unconfigure(config):
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            for w in app.topLevelWidgets():
                w.close()
                w.deleteLater()
            app.processEvents()
    except Exception:  # noqa: BLE001
        pass
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(getattr(config, "_exitstatus", 0))   # filet de sécurité : la suite est terminée, on ne laisse rien bloquer la sortie


def pytest_sessionfinish(session, exitstatus):
    session.config._exitstatus = int(exitstatus)
