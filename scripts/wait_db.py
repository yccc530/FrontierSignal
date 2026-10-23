"""Wait for the configured PostgreSQL service before migrating."""

import time

import psycopg
from frontiersignal.config import settings
from sqlalchemy.engine import make_url

url = make_url(settings.database_url.get_secret_value()).set(drivername="postgresql")
for attempt in range(60):
    try:
        with psycopg.connect(url.render_as_string(hide_password=False), connect_timeout=2) as conn:
            conn.execute("SELECT 1")
        print("PostgreSQL is ready")
        break
    except psycopg.OperationalError:
        if attempt == 59:
            raise SystemExit(
                "PostgreSQL not ready. Check Docker/WSL and FS_DATABASE_URL."
            ) from None
        time.sleep(1)
