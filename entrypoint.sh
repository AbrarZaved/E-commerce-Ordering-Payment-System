#!/usr/bin/env bash
set -e

echo "Waiting for database..."
python - <<'PY'
import os, time
import psycopg2
from urllib.parse import urlparse
url = urlparse(os.environ.get("DATABASE_URL", "postgres://ecommerce:ecommerce@db:5432/ecommerce"))
for _ in range(30):
    try:
        psycopg2.connect(dbname=url.path[1:], user=url.username, password=url.password, host=url.hostname, port=url.port).close()
        break
    except Exception:
        time.sleep(1)
PY

python manage.py makemigrations users products cart orders payments --noinput
python manage.py migrate --noinput
python manage.py seed_admin
python manage.py seed_products
python manage.py collectstatic --noinput || true

exec "$@"
