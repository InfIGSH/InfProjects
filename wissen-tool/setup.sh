#!/usr/bin/env bash
# Einrichtung des Werkzeugs. Aus dem Ordner wissen-tool/ ausfuehren:
#   bash setup.sh
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 fehlt. Bitte Python 3.11 oder neuer installieren." >&2
  exit 1
fi

VERSION=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "Python 3.11 oder neuer nötig, gefunden: $VERSION" >&2
  exit 1
fi

echo "== virtuelle Umgebung =="
[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "== Abhängigkeiten =="
python -m pip install --upgrade pip --quiet
python -m pip install -e ".[dev]"

echo "== Chromium für Playwright =="
python -m playwright install chromium

echo "== ffmpeg =="
if command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg vorhanden: $(command -v ffmpeg)"
else
  cat >&2 <<'EOF'
ffmpeg fehlt -- ohne ffmpeg gibt es keine Screenshots aus Videos.
  macOS:          brew install ffmpeg
  Debian/Ubuntu:  sudo apt install ffmpeg
  Windows:        winget install Gyan.FFmpeg
EOF
fi

echo "== Konfiguration =="
ZIEL="$HOME/.config/wissen/wissen.toml"
if [ -f "$ZIEL" ]; then
  echo "vorhanden: $ZIEL"
else
  mkdir -p "$(dirname "$ZIEL")"
  cp wissen.toml.example "$ZIEL"
  echo "angelegt:  $ZIEL  -- Pfad der Ablage dort anpassen!"
fi

cat <<EOF

Fertig. Nächste Schritte:

  1. $ZIEL öffnen und [ablage] pfad auf dein Wissens-Repo setzen
  2. source $(pwd)/.venv/bin/activate
  3. wissen init

EOF
