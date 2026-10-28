#!/usr/bin/env bash
# (Facultatif : firmware/phone_core2350b.uf2 est déjà fourni.)
# Recompile le firmware MicroPython pour la Waveshare Core2350B avec le module phone.
# PHONE_FB_IN_PSRAM=1 : framebuffer en PSRAM (+150 Ko de SRAM pour le tas) -> firmware/phone_core2350b_fb_psram.uf2.
#   Expérimental, non testé sur la carte ; le firmware par défaut n'est pas touché.
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

BUILD_DIR="build-$BOARD"; BUILD_ARG=""; OUT=phone_core2350b.uf2
if [ "${PHONE_FB_IN_PSRAM:-0}" = 1 ]; then
  export PHONE_FB_IN_PSRAM
  BUILD_DIR="build-$BOARD-fbpsram"; BUILD_ARG="BUILD=$BUILD_DIR"; OUT=phone_core2350b_fb_psram.uf2
  echo ">> framebuffer en PSRAM (expérimental, non testé sur la carte)"
fi

make -C "$MPY/mpy-cross" -j"$J"
make -C "$MPY/ports/rp2" BOARD=$BOARD $BUILD_ARG submodules
make -C "$MPY/ports/rp2" -j"$J" BOARD=$BOARD $BUILD_ARG USER_C_MODULES="$HERE/phone/micropython.cmake"

mkdir -p "$HERE/firmware"
cp "$MPY/ports/rp2/$BUILD_DIR/firmware.uf2" "$HERE/firmware/$OUT"
echo "OK -> $HERE/firmware/$OUT"
