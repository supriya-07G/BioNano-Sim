#!/usr/bin/env bash
# Codespace bootstrap. Runs once, after the container is created.
set -euo pipefail

echo "==> Python 3.11 virtualenv and backend dependencies"
python -m venv .venv311
./.venv311/bin/python -m pip install --upgrade pip
# requirements-dev so the test suite runs in the Codespace too.
./.venv311/bin/pip install -r backend/requirements-dev.txt

echo "==> Local data: structures, protein registry, feature schema"
./.venv311/bin/python scripts/setup_local.py

echo "==> Frontend dependencies"
(cd frontend && npm ci)

echo "==> 3Dmol viewer bundle"
# Vendored, gitignored, and not an npm dependency, so a fresh clone lacks it
# and the structure viewer would render nothing.
./.venv311/bin/python scripts/fetch_viewer.py

cat <<'BANNER'

  Setup complete. Start the app with two terminals:

    cd backend && ../.venv311/bin/python -m uvicorn app.main:app --port 8000
    cd frontend && npm run dev

  Then open the forwarded port 5173. To share the URL, go to the PORTS tab,
  right-click port 5173 and set Port Visibility -> Public.

  Port 5173 alone is enough: Vite proxies /api to the backend inside the
  Codespace, so one URL serves the whole app and there is no CORS to set up.

BANNER
