#!/usr/bin/env bash
# Local (non-Docker) start for macOS / Linux.
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
python -m alembic upgrade head
echo "Pramaan AI -> http://localhost:8000"
exec python -m uvicorn backend.main:app --reload --port "${PORT:-8000}"
