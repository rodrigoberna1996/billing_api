#!/usr/bin/env sh
set -e

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL no esta configurada" >&2
  exit 1
fi

python - <<'PY'
import os
import socket
import time
from sqlalchemy.engine import make_url

url = os.environ["DATABASE_URL"]
u = make_url(url)
host = u.host or "localhost"
port = u.port or 5432

deadline = time.time() + int(os.getenv("DB_WAIT_TIMEOUT", "60"))
while True:
    try:
        with socket.create_connection((host, port), timeout=2):
            break
    except OSError as exc:
        if time.time() > deadline:
            raise SystemExit(f"Database no disponible despues del timeout: {exc}")
        time.sleep(2)
print("Database lista")
PY

echo "Ejecutando migraciones..."
alembic upgrade head

exec "$@"
