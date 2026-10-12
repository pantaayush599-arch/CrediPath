#!/usr/bin/env bash
# Start backend (:8000) and frontend (:3000) together. Run the installs in README first.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
(cd "$ROOT/backend" && .venv/bin/uvicorn app.main:app --port 8000) &
BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT
cd "$ROOT/frontend" && npm run dev
