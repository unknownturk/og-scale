#!/usr/bin/env bash
# Startet OG Scale zum Ausprobieren auf dem eigenen Rechner (Mac/Linux).
# Testbetrieb: Platzhalter-Bilder und nachgestellte Handys, es kostet nichts
# und postet nichts. Braucht Python 3.11+, Node 20+ und ffmpeg.
set -euo pipefail
cd "$(dirname "$0")"
for tool in python3 node npm ffmpeg; do
  command -v "$tool" >/dev/null || { echo "Es fehlt: $tool. Bitte zuerst installieren."; exit 1; }
done
echo "Richte das Backend ein …"
[ -x backend/.venv/bin/pip ] || { rm -rf backend/.venv; python3 -m venv backend/.venv; }
backend/.venv/bin/pip install -q -r backend/requirements.txt
echo "Richte das Frontend ein …"
(cd frontend && npm install --no-audit --no-fund --silent)
export BACKEND_API_KEY=demo-geheimnis MEDIA_PROVIDER=fake DEMO_SEED=1 ALI_TICK_SECONDS=10
trap 'kill 0' EXIT
(cd backend && .venv/bin/python -m uvicorn app.main:app --port 8000 --log-level warning) &
(cd frontend && BACKEND_URL=http://localhost:8000 APP_PASSWORD=demo AUTH_SECRET=nur-fuer-die-demo-0123456789 npm run dev -- -p 3000) &
echo
echo "  OG Scale läuft gleich unter  http://localhost:3000   (Passwort: demo)"
echo "  Beenden mit Strg+C."
wait
