#!/usr/bin/env bash
# Copie un ou plusieurs PDF dans le dossier pdfs/ de la carte (lus par l'appli « Lecteur PDF »).
# Usage : tools/push_pdf.sh livre.pdf notes.pdf ...
set -euo pipefail
. "$(dirname "$0")/_env.sh"
need mpremote tools
[ "$#" -ge 1 ] || { echo "usage : $0 fichier.pdf [...]" >&2; exit 1; }
mpremote fs mkdir pdfs 2>/dev/null || true
for f in "$@"; do
    mpremote fs cp "$f" ":pdfs/$(basename "$f")"
done
echo "Copié. Les fichiers apparaissent dans l'appli Lecteur PDF (relancez-la si elle était ouverte)."
