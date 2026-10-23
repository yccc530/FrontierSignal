#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --locked
uv run python scripts/setup.py
if [[ "${1:-}" != "--skip-database" ]]; then
  if docker compose version >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    docker compose up -d db
  elif [[ -x "$HOME/.local/share/frontiersignal-pg/usr/lib/postgresql/18/bin/postgres" ]]; then
    uv run python scripts/local_postgres.py
  else
    printf '%s\n' 'Start Docker Desktop with WSL integration, or configure PostgreSQL and use --skip-database.' >&2
    exit 1
  fi
fi
uv run python scripts/wait_db.py
uv run alembic upgrade head
npm --prefix frontend ci
npm --prefix frontend run build
printf '%s\n' 'FrontierSignal: http://localhost:8000'
exec uv run uvicorn frontiersignal.main:app --host 127.0.0.1 --port 8000
