#!/usr/bin/env bash
set -euo pipefail

cd /home/runner/workspace/sms-backend

echo "[sms] Running shared migrations..."
python3.11 manage.py migrate_schemas --shared --noinput --fake-initial 2>&1 | grep -v "^$" || true

echo "[sms] Running tenant migrations..."
python3.11 manage.py migrate_schemas --noinput --fake-initial 2>&1 | grep -v "^$" || true

echo "[sms] Collecting static files..."
python3.11 manage.py collectstatic --noinput 2>/dev/null || true

echo "[sms] Starting server on port ${PORT:-8080}..."
python3.11 manage.py runserver 0.0.0.0:${PORT:-8080} --noreload &
SERVER_PID=$!

echo "[sms] Server started (PID: $SERVER_PID)"

if [ "${BOOTSTRAP_DEMO_DATA:-false}" = "true" ]; then
  schema="${DEMO_SCHEMA_NAME:-demo_school}"

  echo "[sms] Checking demo tenant..."
  tenant_exists=$(python3.11 manage.py shell -c "
import os
from clients.models import Tenant
schema = os.environ.get('DEMO_SCHEMA_NAME', 'demo_school')
print('yes' if Tenant.objects.filter(schema_name=schema).exists() else 'no')
" 2>/dev/null || echo "error")

  if [ "$tenant_exists" != "yes" ]; then
    echo "[sms] Creating demo tenant..."
    python3.11 manage.py seed_demo \
      --schema_name "${DEMO_SCHEMA_NAME:-demo_school}" \
      --name "${DEMO_SCHOOL_NAME:-RynatySchool Demo}" \
      --domain "${DEMO_TENANT_DOMAIN:-demo.localhost}" \
      --admin_user "${DEMO_ADMIN_USER:-Riqs#.}" \
      --admin_pass "${DEMO_ADMIN_PASS:-Ointment.54.#}" \
      --admin_email "${DEMO_ADMIN_EMAIL:-admin@demo.school}" && echo "[sms] Base tenant created" || echo "[sms] Base tenant creation skipped"
  else
    echo "[sms] Demo tenant exists — ensuring all seed data is present..."
  fi

  # Register any runtime/production domains with the demo tenant so that
  # tenant middleware correctly routes requests in deployed environments.
  echo "[sms] Registering runtime domains with demo tenant..."
  python3.11 manage.py shell -c "
import os
from clients.models import Tenant, Domain

schema = os.environ.get('DEMO_SCHEMA_NAME', 'demo_school')
try:
    tenant = Tenant.objects.get(schema_name=schema)
except Tenant.DoesNotExist:
    print('  [domains] Tenant not found, skipping')
    exit()

# Collect all candidate domains
candidates = set()
candidates.add(os.environ.get('DEMO_TENANT_DOMAIN', 'demo.localhost'))

replit_domains = os.environ.get('REPLIT_DOMAINS', '')
for d in replit_domains.split(','):
    d = d.strip()
    if d:
        candidates.add(d)

extra = os.environ.get('EXTRA_TENANT_DOMAINS', '')
for d in extra.split(','):
    d = d.strip()
    if d:
        candidates.add(d)

added = []
for domain_name in candidates:
    _, created = Domain.objects.get_or_create(
        domain=domain_name,
        defaults={'tenant': tenant, 'is_primary': False},
    )
    if created:
        added.append(domain_name)

if added:
    print('  [domains] Registered: ' + ', '.join(added))
else:
    print('  [domains] All domains already registered (' + str(Domain.objects.filter(tenant=tenant).count()) + ' total)')
" 2>/dev/null || echo "[sms] Domain registration skipped"

  echo "[sms] Seeding modules..."
  python3.11 manage.py seed_modules --all-tenants 2>/dev/null || true

  echo "[sms] Seeding roles and permissions..."
  python3.11 manage.py seed_default_permissions --assign-roles --schema="$schema" 2>/dev/null || true

  echo "[sms] Seeding full Kenya school data (idempotent)..."
  python3.11 manage.py seed_kenya_school --schema_name "$schema" 2>&1 | tail -5 || echo "[sms] Kenya seed skipped"

  echo "[sms] Seeding curriculum templates..."
  python3.11 manage.py seed_curriculum_templates --schema="$schema" 2>/dev/null || true

  echo "[sms] Seeding portal login accounts..."
  python3.11 manage.py seed_portal_accounts --schema_name "$schema" 2>&1 || echo "[sms] Portal accounts skipped"

  echo "[sms] Seeding staff user accounts for all role types..."
  python3.11 manage.py seed_staff_users --schema_name "$schema" 2>&1 || echo "[sms] Staff users skipped"

  echo "[sms] Seeding supplementary demo data (25+ records per module)..."
  python3.11 manage.py seed_extra_data --schema_name "$schema" 2>&1 || echo "[sms] Extra data seed skipped"

  echo "[sms] Seeding KICD digital textbooks and Harvard open learning materials..."
  python3.11 manage.py seed_digital_resources --schema_name "$schema" 2>&1 || echo "[sms] Digital resources seed skipped"

  echo "[sms] Seeding platform super-admin + demo data..."
  python3.11 manage.py seed_platform_data 2>&1 || echo "[sms] Platform data seed skipped"

  echo "[sms] Bootstrap complete."
fi

echo "[sms] Waiting for server process..."
wait $SERVER_PID
