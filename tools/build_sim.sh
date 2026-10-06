#!/usr/bin/env bash
# Compile MicroPython "unix" + le module phone (HAL SDL2) : simulateur PC pour les applis Python.
#   Fedora :  sudo dnf install gcc make git python3 pkgconf-pkg-config SDL2-devel
#   Debian :  sudo apt install gcc make git python3 pkg-config libsdl2-dev
# MPY_DIR=/chemin/micropython pour réutiliser un clone existant.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
MPY="${MPY_DIR:-$HERE/build/micropython}"
[ -d "$MPY" ] || git clone --depth 1 https://github.com/micropython/micropython "$MPY"

make -C "$MPY/mpy-cross" -j"$(nproc)"
make -C "$MPY/ports/unix" submodules
make -C "$MPY/ports/unix" -j"$(nproc)" MICROPY_PY_FFI=0 USER_C_MODULES="$HERE/phone"

echo
echo "OK. Pour lancer le simulateur :"
echo "  cd $HERE/python && $MPY/ports/unix/build-standard/micropython main.py"
