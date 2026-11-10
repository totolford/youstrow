"""Persistance : réglages utilisateur et fichiers de show (JSON, écriture atomique).

Les données vont dans %APPDATA%/YouStrow (Windows) ou ~/.config/YouStrow (Linux) — volontairement séparé des fichiers ~/.youstrow_*.json de
l'application d'origine, pour ne jamais les écraser."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

SHOW_VERSION = 1
SHOW_EXT = ".ysshow"


def data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:                                   # Linux : XDG_CONFIG_HOME, sinon ~/.config
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    p = Path(base) / "YouStrow"
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_json_atomic(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)          # jamais de fichier à moitié écrit
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


class Settings:
    """Réglages persistants (sortie DMX, dernier show, géométrie…)."""

    DEFAULTS = {
        "output": {"type": "none", "serial": "", "port": "", "ip": "255.255.255.255", "fps": 30,
                   "universe_map": {"0": 0}, "autoconnect": True},
        "midi": {"in": "", "out": "", "profile": "apc_mini", "bindings": [], "autoconnect": True},
        "last_show": "",
        "recent": [],
        "geometry": "",
    }

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else data_dir() / "settings.json"
        self.data = json.loads(json.dumps(self.DEFAULTS))
        stored = read_json(self.path, {})
        for k, v in stored.items():
            if isinstance(v, dict) and isinstance(self.data.get(k), dict):
                self.data[k].update(v)
            else:
                self.data[k] = v

    def save(self) -> None:
        write_json_atomic(self.path, self.data)

    def add_recent(self, path: str) -> None:
        r = [p for p in self.data["recent"] if p != path]
        self.data["recent"] = ([path] + r)[:8]
        self.data["last_show"] = path


def save_show(path, patch, states: dict, effects: list, extra: dict | None = None) -> None:
    write_json_atomic(path, {
        "format": "youstrow-next-show", "version": SHOW_VERSION,
        "patch": patch.to_dict(),
        "states": {str(fid): {"color": list(s.color), "dimmer": s.dimmer, "pan": s.pan, "tilt": s.tilt,
                              "strobe": s.strobe, "white": s.white, "raw": s.raw} for fid, s in states.items()},
        "effects": [e.to_dict() for e in effects],
        **(extra or {}),
    })


def load_show(path) -> dict:
    d = read_json(path)
    if not isinstance(d, dict) or d.get("format") != "youstrow-next-show":
        raise ValueError("Ce fichier n'est pas un show youstrow valide")
    if d.get("version", 0) > SHOW_VERSION:
        raise ValueError("Show créé avec une version plus récente du logiciel")
    return d
