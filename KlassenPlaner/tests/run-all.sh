#!/usr/bin/env bash
# Erzeugt die Fixtures und laesst alle Testskripte gegen
# ../Klassenbildungstool_v1.html laufen.
#
#   npm i playwright && npx playwright install chromium
#   ./run-all.sh
#
# Liegt Chromium an einem eigenen Ort: PW_CHROME=/pfad/zu/chrome ./run-all.sh
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p fixtures
node gen-fair.js            fixtures/fair150.csv
node gen-konfliktdatensatz.js fixtures/jahrgang150.csv
for t in 0*.js; do
  echo "===== $t"
  node "$t"
done
