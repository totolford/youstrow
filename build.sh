#!/usr/bin/env bash
# Compile YouStrow sous Ubuntu : tests -> application autonome (dist/YouStrow/) -> paquet dist/youstrow_X.Y.Z_amd64.deb
# Usage : ./build.sh [--skip-tests] [--skip-deb]
set -euo pipefail
cd "$(dirname "$0")"
SKIP_TESTS=0; SKIP_DEB=0
for a in "$@"; do case "$a" in --skip-tests) SKIP_TESTS=1;; --skip-deb) SKIP_DEB=1;; *) echo "option inconnue : $a" >&2; exit 2;; esac; done
VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' youstrow/__init__.py)

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -U pip
  .venv/bin/python -m pip install -r requirements.txt pyinstaller
fi
if [ "$SKIP_TESTS" = 0 ]; then QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q; fi
.venv/bin/python -m PyInstaller youstrow.spec --noconfirm --clean
echo "OK -> dist/YouStrow/YouStrow"
[ "$SKIP_DEB" = 1 ] && exit 0

ARCH=$(dpkg --print-architecture)
PKG="build/deb/youstrow_${VERSION}_${ARCH}"
rm -rf "$PKG"; mkdir -p "$PKG/DEBIAN" "$PKG/opt/youstrow" "$PKG/usr/bin" "$PKG/usr/share/applications" \
  "$PKG/usr/share/icons/hicolor/256x256/apps" "$PKG/usr/share/mime/packages" "$PKG/lib/udev/rules.d" "$PKG/usr/share/doc/youstrow"
cp -a dist/YouStrow/. "$PKG/opt/youstrow/"
ln -s /opt/youstrow/YouStrow "$PKG/usr/bin/youstrow"
install -m644 linux/youstrow.desktop "$PKG/usr/share/applications/youstrow.desktop"
install -m644 assets/youstrow.png "$PKG/usr/share/icons/hicolor/256x256/apps/youstrow.png"
install -m644 linux/youstrow-mime.xml "$PKG/usr/share/mime/packages/youstrow.xml"
install -m644 linux/youstrow-udev.rules "$PKG/lib/udev/rules.d/60-youstrow.rules"
install -m644 LICENSE NOTICE.md "$PKG/usr/share/doc/youstrow/"
cat > "$PKG/DEBIAN/control" <<CTL
Package: youstrow
Version: ${VERSION}
Section: video
Priority: optional
Architecture: ${ARCH}
Maintainer: YouStrow <noreply@youstrow.invalid>
Installed-Size: $(du -sk "$PKG/opt" | cut -f1)
Depends: libc6, libasound2t64 | libasound2, libegl1, libxkbcommon-x11-0, libxcb-cursor0, libpulse0
Recommends: gstreamer1.0-plugins-good, gstreamer1.0-libav
Homepage: https://github.com/totolford/youstrow
Description: Contrôleur lumière DMX (Open DMX USB, Art-Net, MIDI)
 Sortie ENTTEC Open DMX USB / DMX USB PRO / Art-Net, patch, effets,
 lecteur média avec effet lumineux par piste, contrôle MIDI (AKAI APC mini).
CTL
for s in postinst postrm; do
cat > "$PKG/DEBIAN/$s" <<'SH'
#!/bin/sh
set -e
command -v udevadm >/dev/null 2>&1 && { udevadm control --reload-rules || true; udevadm trigger --subsystem-match=usb || true; }
command -v update-mime-database >/dev/null 2>&1 && update-mime-database /usr/share/mime || true
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t /usr/share/icons/hicolor || true
exit 0
SH
chmod 755 "$PKG/DEBIAN/$s"; done
dpkg-deb --root-owner-group --build "$PKG" "dist/youstrow_${VERSION}_${ARCH}.deb"
echo "OK -> dist/youstrow_${VERSION}_${ARCH}.deb   (sudo apt install ./dist/youstrow_${VERSION}_${ARCH}.deb)"
