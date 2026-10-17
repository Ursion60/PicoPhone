#!/usr/bin/env bash
# Copie les fichiers Python sur la carte (via USB) avec mpremote (installé par tools/setup-deps.sh tools).
# Accès USB sans sudo : tools/setup-deps.sh udev
# Relancez ce script à chaque modification d'une appli.
set -euo pipefail
. "$(dirname "$0")/_env.sh"
need mpremote tools
cd "$(dirname "$0")/../python"
mpremote fs mkdir apps 2>/dev/null || true
mpremote fs cp main.py appkit.py :
mpremote fs cp apps/*.py :apps/
mpremote reset
echo "Fichiers copiés, carte redémarrée."
