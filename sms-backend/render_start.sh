#!/usr/bin/env bash
set -euo pipefail

bootstrap_demo_data() {
  if [ "${BOOTSTRAP_DEMO_DATA:-false}" != "true" ]; then
    return
  fi

  local schema="${DEMO_SCHEMA_NAME:-demo_school}"
  local school_name="${DEMO_SCHOOL_NAME:-Demo School}"
  local tenant_domain="${DEMO_TENANT_DOMAIN:-demo.localhost}"
  local admin_user="${DEMO_ADMIN_USER:-admin}"
  local admin_pass="${DEMO_ADMIN_PASS:-admin123}"
  local admin_email="${DEMO_ADMIN_EMAIL:-admin@demo.school}"

  echo "[render] checking demo bootstrap for schema '${schema}'..."
  local tenant_exists
  tenant_exists="$(
    DEMO_SCHEMA_NAME="$schema" \
      python manage.py shell -c "import os; from clients.models import Tenant; print('yes' if Tenant.objects.filter(schema_name=os.environ['DEMO_SCHEMA_NAME']).exists() else 'no')"
  )"

  if [ "$tenant_exists" = "yes" ]; then
    echo "[render] demo tenant already exists; skipping demo bootstrap."
    return
  fi

  echo "[render] bootstrapping demo tenant data..."
  python manage.py seed_demo \
    --schema_name "$schema" \
    --name "$school_name" \
    --domain "$tenant_domain" \
    --admin_user "$admin_user" \
    --admin_pass "$admin_pass" \
    --admin_email "$admin_email"
  python manage.py seed_default_permissions --assign-roles --schema="$schema"
  python manage.py seed_modules --all-tenants
  python manage.py seed_kenya_school --schema_name "$schema"
  python manage.py seed_portal_accounts --schema_name "$schema"
}

echo "[render] starting backend bootstrap..."

python manage.py migrate_schemas --shared --noinput
python manage.py migrate_schemas --noinput
python manage.py collectstatic --noinput
bootstrap_demo_data

echo "[render] starting gunicorn..."
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --workers ${WEB_CONCURRENCY:-3} \
  --timeout 120
