"""Block until the configured database accepts connections (used by the Docker entrypoint)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlalchemy as sa  # noqa: E402

from backend import config  # noqa: E402

for attempt in range(60):
    try:
        with sa.create_engine(config.DATABASE_URL).connect() as c:
            c.execute(sa.text("SELECT 1"))
        print("Database is ready.")
        raise SystemExit(0)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print(f"Waiting for database ({attempt + 1}/60): {type(e).__name__}")
        time.sleep(2)
raise SystemExit("Database did not become ready in time.")
