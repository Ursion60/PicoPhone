#!/usr/bin/env sh
# Installe les dépendances sur n'importe quelle distribution Linux courante.
#   tools/setup-deps.sh [sim] [firmware] [tools] [pronote] [udev]     (défaut : sim tools)
#     sim       gcc, make, git, pkg-config, SDL2 (dev)   -> tools/build_sim.sh
#     firmware  + cmake, toolchain arm-none-eabi          -> tools/build_firmware.sh
#     tools     polices DejaVu/Noto CJK + venv Python (.venv : pillow, mpremote)
#     pronote   pronotepy dans le venv .venv (après tools) -> tools/sync_pronote.py (synchro de l'EDT)
#     udev      règle d'accès USB à la carte (sans sudo ni groupe dialout)
# Détecte le gestionnaire de paquets (apt, dnf, pacman, zypper, apk, xbps, emerge).
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
[ $# -gt 0 ] || set -- sim tools

SUDO=""
[ "$(id -u)" -eq 0 ] || { command -v sudo >/dev/null 2>&1 && SUDO="sudo" || SUDO="doas"; }

pkgs_for() {   # $1 = gestionnaire, $2 = sim|firmware|tools
  case "$1:$2" in
    apt:sim)        echo "gcc make git python3 pkg-config libsdl2-dev" ;;
    apt:firmware)   echo "cmake g++ gcc-arm-none-eabi libnewlib-arm-none-eabi libstdc++-arm-none-eabi-newlib" ;;
    apt:tools)      echo "python3-venv fontconfig fonts-dejavu-core fonts-noto-cjk" ;;
    dnf:sim)        echo "gcc make git python3 pkgconf-pkg-config SDL2-devel" ;;
    dnf:firmware)   echo "cmake gcc-c++ arm-none-eabi-gcc-cs arm-none-eabi-gcc-cs-c++ arm-none-eabi-newlib" ;;
    dnf:tools)      echo "python3 fontconfig dejavu-sans-fonts google-noto-sans-cjk-fonts" ;;
    pacman:sim)     echo "gcc make git python pkgconf sdl2" ;;
    pacman:firmware) echo "cmake arm-none-eabi-gcc arm-none-eabi-newlib" ;;
    pacman:tools)   echo "python fontconfig ttf-dejavu noto-fonts-cjk" ;;
    zypper:sim)     echo "gcc make git python3 pkg-config SDL2-devel" ;;
    zypper:firmware) echo "cmake gcc-c++ cross-arm-none-gcc-devel cross-arm-none-newlib-devel" ;;
    zypper:tools)   echo "python3 fontconfig dejavu-fonts google-noto-sans-cjk-fonts" ;;
    apk:sim)        echo "build-base git python3 pkgconf sdl2-dev bash" ;;
    apk:firmware)   echo "cmake gcc-arm-none-eabi newlib-arm-none-eabi g++-arm-none-eabi bash" ;;
    apk:tools)      echo "python3 fontconfig font-dejavu font-noto-cjk" ;;
    xbps:sim)       echo "gcc make git python3 pkg-config SDL2-devel" ;;
    xbps:firmware)  echo "cmake cross-arm-none-eabi-gcc cross-arm-none-eabi-newlib" ;;
    xbps:tools)     echo "python3 fontconfig dejavu-fonts-ttf noto-fonts-cjk" ;;
    emerge:sim)     echo "sys-devel/gcc dev-vcs/git dev-util/pkgconf media-libs/libsdl2" ;;
    emerge:firmware) echo "dev-build/cmake sys-devel/crossdev" ;;
    emerge:tools)   echo "media-libs/fontconfig media-fonts/dejavu media-fonts/noto-cjk" ;;
    *) echo "" ;;
  esac
}
install_cmd() {
  case "$1" in
    apt)    echo "$SUDO apt-get install -y" ;;
    dnf)    echo "$SUDO dnf install -y" ;;
    pacman) echo "$SUDO pacman -S --needed --noconfirm" ;;
    zypper) echo "$SUDO zypper install -y" ;;
    apk)    echo "$SUDO apk add" ;;
    xbps)   echo "$SUDO xbps-install -y" ;;
    emerge) echo "$SUDO emerge --noreplace" ;;
  esac
}

PM=""
for c in apt-get:apt dnf:dnf pacman:pacman zypper:zypper apk:apk xbps-install:xbps emerge:emerge; do
  command -v "${c%%:*}" >/dev/null 2>&1 && { PM="${c##*:}"; break; }
done
[ -n "$PM" ] || { echo "Gestionnaire de paquets non reconnu : installez à la main (voir README)."; exit 1; }
echo ">> gestionnaire de paquets : $PM"
[ "$PM" = apt ] && $SUDO apt-get update

for what in "$@"; do
  case "$what" in
    sim|firmware|tools)
      list="$(pkgs_for "$PM" "$what")"
      [ -z "$list" ] || { echo ">> $what : $list"; $(install_cmd "$PM") $list || echo "!! certains paquets n'ont pas pu être installés (noms variables selon la version de la distro)"; }
      if [ "$what" = tools ]; then
        # venv local : évite 'externally-managed-environment' (PEP 668) sur Debian/Ubuntu/Fedora/Arch...
        python3 -m venv "$HERE/.venv"
        "$HERE/.venv/bin/pip" install --quiet --upgrade pip pillow mpremote
        echo ">> venv prêt : . $HERE/.venv/bin/activate   (ou utilisez directement tools/*.sh, qui l'activent seuls)"
      fi ;;
    pronote)
      [ -x "$HERE/.venv/bin/pip" ] || python3 -m venv "$HERE/.venv"
      "$HERE/.venv/bin/pip" install --quiet --upgrade pip pronotepy mpremote
      echo ">> pronotepy installé dans $HERE/.venv : tools/sync_pronote.py --help" ;;
    udev)
      $SUDO install -m 644 "$HERE/tools/99-pico.rules" /etc/udev/rules.d/99-pico.rules
      $SUDO udevadm control --reload-rules && $SUDO udevadm trigger || true
      echo ">> règle udev installée : rebranchez la carte. (Sans systemd/logind : ajoutez-vous au groupe dialout ou uucp.)" ;;
    *) echo "option inconnue : $what"; exit 1 ;;
  esac
done
