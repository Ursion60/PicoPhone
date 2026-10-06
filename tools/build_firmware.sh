#!/usr/bin/env bash
# (Facultatif : firmware/phone_core2350b.uf2 est déjà fourni.)
# Recompile le firmware MicroPython pour la Waveshare Core2350B avec le module phone.
#   Fedora :  sudo dnf install gcc gcc-c++ make cmake git python3 arm-none-eabi-gcc-cs \
#                              arm-none-eabi-gcc-cs-c++ arm-none-eabi-newlib
#   Debian :  sudo apt install gcc make cmake git python3 gcc-arm-none-eabi libnewlib-arm-none-eabi \
#                              libstdc++-arm-none-eabi-newlib
# MPY_DIR=/chemin/micropython pour réutiliser un clone existant.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
MPY="${MPY_DIR:-$HERE/build/micropython}"
BOARD=WAVESHARE_RP2350B_CORE      # = Core2350B (RP2350B, 16 Mo flash, 8 Mo PSRAM)
[ -d "$MPY" ] || git clone --depth 1 https://github.com/micropython/micropython "$MPY"

make -C "$MPY/mpy-cross" -j"$(nproc)"
make -C "$MPY/ports/rp2" BOARD=$BOARD submodules
make -C "$MPY/ports/rp2" -j"$(nproc)" BOARD=$BOARD USER_C_MODULES="$HERE/phone/micropython.cmake"

mkdir -p "$HERE/firmware"
cp "$MPY/ports/rp2/build-$BOARD/firmware.uf2" "$HERE/firmware/phone_core2350b.uf2"
echo "OK -> $HERE/firmware/phone_core2350b.uf2"
