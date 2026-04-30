#!/usr/bin/env bash
set -euo pipefail

# Wait for the database to accept TCP connections.
if [[ -n "${DATABASE_URL:-}" ]]; then
  echo "[entrypoint] waiting for database to be reachable..."
  python - <<'PY'
import os
import re
import socket
import time

url = os.environ["DATABASE_URL"]
m = re.match(r".*://(?:[^:]+:[^@]+@)?([^:/]+)(?::(\d+))?", url)
if not m:
    raise SystemExit(f"cannot parse DATABASE_URL host: {url}")
host = m.group(1)
port = int(m.group(2) or 5432)

deadline = time.time() + 60
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"[entrypoint] db reachable at {host}:{port}")
            break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit(f"database unreachable at {host}:{port} after 60s")
PY
fi

# Run migrations unless explicitly disabled.
if [[ "${RUN_MIGRATIONS:-true}" == "true" ]]; then
  echo "[entrypoint] running alembic upgrade head..."
  alembic upgrade head
fi

echo "[entrypoint] starting: $*"
exec "$@"
