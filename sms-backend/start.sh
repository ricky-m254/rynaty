#!/usr/bin/env bash
set -euo pipefail

cd /home/runner/workspace/sms-backend

echo "[sms] Running shared migrations..."
python3.11 manage.py migrate_schemas --shared --noinput 2>&1 | grep -v "^$" || true

echo "[sms] Running tenant migrations..."
python3.11 manage.py migrate_schemas --noinput 2>&1 | grep -v "^$" || true

echo "[sms] Collecting static files..."
python3.11 manage.py collectstatic --noinput 2>/dev/null || true

echo "[sms] Starting server on port ${PORT:-8080}..."
python3.11 manage.py runserver 0.0.0.0:${PORT:-8080} --noreload &
SERVER_PID=$!

echo "[sms] Server started (PID: $SERVER_PID)"

if [ "${BOOTSTRAP_DEMO_DATA:-false}" = "true" ]; then
  echo "[sms] Bootstrapping demo data in background..."
  schema="${DEMO_SCHEMA_NAME:-demo_school}"
  tenant_exists=$(python3.11 manage.py shell -c "
import os
from clients.models import Tenant
schema = os.environ.get('DEMO_SCHEMA_NAME', 'demo_school')
print('yes' if Tenant.objects.filter(schema_name=schema).exists() else 'no')
" 2>/dev/null || echo "error")

  if [ "$tenant_exists" = "yes" ]; then
    echo "[sms] Demo tenant already exists; skipping bootstrap."
  else
    echo "[sms] Bootstrapping demo tenant..."
    python3.11 manage.py seed_demo \
      --schema_name "${DEMO_SCHEMA_NAME:-demo_school}" \
      --name "${DEMO_SCHOOL_NAME:-RynatySchool Demo}" \
      --domain "${DEMO_TENANT_DOMAIN:-demo.localhost}" \
      --admin_user "${DEMO_ADMIN_USER:-admin}" \
      --admin_pass "${DEMO_ADMIN_PASS:-admin123}" \
      --admin_email "${DEMO_ADMIN_EMAIL:-admin@demo.school}" && echo "[sms] Demo seeded OK" || echo "[sms] Demo seed skipped"
    python3.11 manage.py seed_default_permissions --assign-roles --schema="${DEMO_SCHEMA_NAME:-demo_school}" 2>/dev/null || true
    python3.11 manage.py seed_modules --all-tenants 2>/dev/null || true
    echo "[sms] Demo bootstrap complete"
  fi
fi

echo "[sms] Waiting for server process..."
wait $SERVER_PID
