#!/usr/bin/env bash
# (Facultatif : firmware/phone_core2350b.uf2 est déjà fourni.)
# Recompile le firmware MicroPython pour la Waveshare Core2350B avec le module phone.
# Dépendances (toutes distributions) :  tools/setup-deps.sh firmware
# MPY_DIR=/chemin/micropython pour réutiliser un clone existant.
set -euo pipefail
. "$(dirname "$0")/_env.sh"
need git; need make; need cmake firmware; need arm-none-eabi-gcc firmware
J="$(ncpu)"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
MPY="${MPY_DIR:-$HERE/build/micropython}"
BOARD=WAVESHARE_RP2350B_CORE      # = Core2350B (RP2350B, 16 Mo flash, 8 Mo PSRAM)
[ -d "$MPY" ] || git clone --depth 1 https://github.com/micropython/micropython "$MPY"

make -C "$MPY/mpy-cross" -j"$J"
make -C "$MPY/ports/rp2" BOARD=$BOARD submodules
make -C "$MPY/ports/rp2" -j"$J" BOARD=$BOARD USER_C_MODULES="$HERE/phone/micropython.cmake"

mkdir -p "$HERE/firmware"
cp "$MPY/ports/rp2/build-$BOARD/firmware.uf2" "$HERE/firmware/phone_core2350b.uf2"
echo "OK -> $HERE/firmware/phone_core2350b.uf2"
