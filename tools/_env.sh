# Sourcé par les autres scripts : active le venv local s'il existe, vérifie les outils requis.
_HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$_HERE/.venv/bin/activate" ] && . "$_HERE/.venv/bin/activate"
need() {   # need outil [paquet-ou-conseil]
  command -v "$1" >/dev/null 2>&1 || { echo "Il manque '$1'. Lancez : tools/setup-deps.sh ${2:-sim}" >&2; exit 1; }
}
ncpu() { nproc 2>/dev/null || getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 2; }
