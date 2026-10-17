#!/usr/bin/env bash
# Compile MicroPython "unix" + le module phone (HAL SDL2) : simulateur PC pour les applis Python.
# Dépendances (toutes distributions) :  tools/setup-deps.sh sim
# MPY_DIR=/chemin/micropython pour réutiliser un clone existant.
set -euo pipefail
. "$(dirname "$0")/_env.sh"
need gcc; need make; need git; need pkg-config
pkg-config --exists sdl2 || { echo "SDL2 (en-têtes de développement) introuvable : tools/setup-deps.sh sim" >&2; exit 1; }
J="$(ncpu)"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
MPY="${MPY_DIR:-$HERE/build/micropython}"
[ -d "$MPY" ] || git clone --depth 1 https://github.com/micropython/micropython "$MPY"

make -C "$MPY/mpy-cross" -j"$J"
make -C "$MPY/ports/unix" submodules
make -C "$MPY/ports/unix" -j"$J" MICROPY_PY_FFI=0 USER_C_MODULES="$HERE/phone"

echo
echo "OK. Pour lancer le simulateur :"
echo "  cd $HERE/python && $MPY/ports/unix/build-standard/micropython main.py"
