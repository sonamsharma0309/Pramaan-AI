#!/bin/sh
# Wait for the database, apply migrations, then start the API.
set -e
python scripts/wait_for_db.py
python -m alembic upgrade head
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"
