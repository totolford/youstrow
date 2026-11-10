#!/usr/bin/env bash
# Installation « depuis les sources » sur Ubuntu/Debian (sans compiler de paquet) : dépendances système,
# environnement Python, règle udev pour l'Open DMX, lanceur de menu. Usage : ./install.sh
set -euo pipefail
cd "$(dirname "$0")"
HERE=$(pwd)
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip build-essential libasound2-dev libegl1 libxkbcommon-x11-0 libxcb-cursor0 \
  libpulse0 gstreamer1.0-plugins-good gstreamer1.0-libav
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -r requirements.txt
sudo install -m644 linux/youstrow-udev.rules /etc/udev/rules.d/60-youstrow.rules
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=usb || true
getent group dialout | grep -qw "$USER" || { sudo usermod -aG dialout "$USER"; echo "Ajouté au groupe dialout : reconnectez-vous pour l'activer."; }
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/256x256/apps" "$HOME/.local/share/mime/packages"
printf '#!/bin/sh\nexec "%s/.venv/bin/python" "%s/run_youstrow.py" "$@"\n' "$HERE" "$HERE" > "$HOME/.local/bin/youstrow"
chmod +x "$HOME/.local/bin/youstrow"
cp assets/youstrow.png "$HOME/.local/share/icons/hicolor/256x256/apps/youstrow.png"
cp linux/youstrow-mime.xml "$HOME/.local/share/mime/packages/youstrow.xml"
sed "s|^Exec=.*|Exec=$HOME/.local/bin/youstrow %f|" linux/youstrow.desktop > "$HOME/.local/share/applications/youstrow.desktop"
update-mime-database "$HOME/.local/share/mime" 2>/dev/null || true
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo "Installé. Lancez « YouStrow » depuis le menu ou : ~/.local/bin/youstrow"
