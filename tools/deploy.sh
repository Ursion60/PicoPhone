#!/usr/bin/env bash
# Copie les fichiers Python sur la carte (via USB) avec mpremote (installé par tools/setup-deps.sh tools).
# Accès USB sans sudo : tools/setup-deps.sh udev
# Relancez ce script à chaque modification d'une appli.
#
# Par défaut, i18n, appkit et apps/*.py sont précompilés en .mpy avec mpy-cross : la carte n'a plus à
# compiler le source à chaque ouverture d'appli (mesuré sur le simulateur : le tas nécessaire à l'import
# de pdftext passe de 160 Ko à 32 Ko). main.py et apps/__init__.py restent en .py.
#   PY=1 tools/deploy.sh              envoie les sources .py tels quels
#   MPY_CROSS=/chemin/mpy-cross ...   utilise un autre mpy-cross (défaut : celui compilé par build_sim.sh)
# Si mpy-cross manque, ou si le format .mpy n'est pas celui du firmware de la carte, on retombe sur les .py.
set -euo pipefail
. "$(dirname "$0")/_env.sh"
need mpremote tools
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE/python"

XC="${MPY_CROSS:-$HERE/build/micropython/mpy-cross/build/mpy-cross}"
USE_MPY=1
if [ "${PY:-0}" = 1 ]; then
  USE_MPY=0
elif [ ! -x "$XC" ]; then
  echo "mpy-cross introuvable ($XC) : envoi des sources .py (tools/build_sim.sh le compile)."
  USE_MPY=0
else
  # Le firmware n'accepte que le format .mpy de sa propre version : on compare avant d'envoyer.
  want_ver="$("$XC" --version 2>&1 | sed -n 's/.*mpy v\([0-9][0-9]*\)\.\([0-9][0-9]*\).*/\1 \2/p')"
  if [ -z "$want_ver" ]; then
    echo "Version .mpy de mpy-cross illisible : envoi des sources .py."
    USE_MPY=0
  else
    want=$(( ${want_ver% *} | (${want_ver#* } << 8) ))
    got="$(mpremote exec "import sys; print(sys.implementation._mpy & 1023)" 2>/dev/null | tr -d '\r' | tail -1 || true)"
    if [ "$got" != "$want" ]; then
      echo "Format .mpy de la carte (${got:-inconnu}) différent de celui de mpy-cross ($want) : envoi des sources .py."
      USE_MPY=0
    fi
  fi
fi

mpremote fs mkdir apps 2>/dev/null || true
mpremote fs mkdir pdfs 2>/dev/null || true
mpremote fs cp main.py :
mpremote fs cp apps/__init__.py :apps/

MODULES="i18n.py appkit.py $(cd apps && ls *.py | grep -v '^__init__\.py$' | sed 's|^|apps/|' | tr '\n' ' ')"
if [ "$USE_MPY" = 1 ]; then
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  mkdir -p "$TMP/apps"
  for f in $MODULES; do "$XC" -o "$TMP/${f%.py}.mpy" "$f"; done
  for f in $MODULES; do mpremote fs cp "$TMP/${f%.py}.mpy" ":${f%.py}.mpy"; done
  # un .py de même nom l'emporterait sur le .mpy : on le retire de la carte
  for f in $MODULES; do mpremote fs rm ":$f" 2>/dev/null || true; done
  echo "Modules précompilés en .mpy."
else
  for f in $MODULES; do mpremote fs cp "$f" ":$f"; done
  for f in $MODULES; do mpremote fs rm ":${f%.py}.mpy" 2>/dev/null || true; done   # .mpy périmés
fi

mpremote fs cp pdfs/*.pdf :pdfs/ 2>/dev/null || true     # PDF d'exemple (supprimez-le du dossier python/pdfs pour ne plus le recopier)
mpremote reset
echo "Fichiers copiés, carte redémarrée."
