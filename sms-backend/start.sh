#!/usr/bin/env bash
set -euo pipefail

cd /home/runner/workspace/sms-backend

echo "[sms] Running shared migrations..."
python3.11 manage.py migrate_schemas --shared --noinput --fake-initial 2>&1 | grep -v "^$" || true

echo "[sms] Pre-faking contenttypes 0002 on schemas missing the 'name' column..."
python3.11 manage.py shell -c "
from django.db import connection
from django_tenants.utils import get_public_schema_name

PUBLIC = get_public_schema_name()

# Collect all tenant schema names from the public schema
connection.set_schema_to_public()
with connection.cursor() as cur:
    cur.execute(\"SELECT schema_name FROM clients_tenant WHERE schema_name <> %s\", [PUBLIC])
    schemas = [r[0] for r in cur.fetchall()]

for schema in schemas:
    connection.set_schema(schema)
    with connection.cursor() as cur:
        # Skip if contenttypes 0002 already recorded as applied
        cur.execute(
            \"SELECT 1 FROM django_migrations WHERE app='contenttypes' AND name='0002_remove_content_type_name' LIMIT 1\"
        )
        if cur.fetchone():
            continue
        # Check if the 'name' column actually exists
        cur.execute(
            \"SELECT 1 FROM information_schema.columns WHERE table_schema=%s AND table_name='django_content_type' AND column_name='name' LIMIT 1\",
            [schema],
        )
        col_exists = cur.fetchone()
        if not col_exists:
            # Column already absent — fake the migration so migrate_schemas won't crash
            cur.execute(
                \"INSERT INTO django_migrations (app, name, applied) VALUES ('contenttypes', '0002_remove_content_type_name', NOW()) ON CONFLICT DO NOTHING\"
            )
            print(f'  [contenttypes] Faked 0002 on schema: {schema}')
connection.set_schema_to_public()
print('  Done.')
" 2>&1 | grep -v "^$" || true

echo "[sms] Running tenant migrations..."
python3.11 manage.py migrate_schemas --noinput --fake-initial 2>&1 | grep -v "^$" || true

echo "[sms] Collecting static files..."
python3.11 manage.py collectstatic --noinput 2>/dev/null || true

echo "[sms] Starting server on port ${PORT:-8080}..."
python3.11 manage.py runserver 0.0.0.0:${PORT:-8080} --noreload &
SERVER_PID=$!

echo "[sms] Server started (PID: $SERVER_PID)"

# Always register all known domains for the demo tenant so tenant middleware
# can route requests correctly in every environment (dev, staging, production).
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

# Always register the production domains for the demo school
for d in ['rynatyschool.app', 'www.rynatyschool.app']:
    candidates.add(d)

replit_domains = os.environ.get('REPLIT_DOMAINS', '')
for d in replit_domains.split(','):
    d = d.strip()
    if d:
        candidates.add(d)

extra = os.environ.get('EXTRA_TENANT_DOMAINS', '')
# Only add root-level domains (no more than one dot) to avoid registering
# tenant subdomains (e.g. olom.rynatyschool.app) under the demo school.
for d in extra.split(','):
    d = d.strip()
    if d and d.count('.') <= 1:
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

# Ensure olom tenant exists and its domain (olom.rynatyschool.app) is registered.
# Creates the tenant + schema + admin user the first time in production.
echo "[sms] Ensuring olom tenant exists with correct domain..."
python3.11 manage.py seed_olom_tenant 2>&1 || echo "[sms] Olom tenant seed skipped"

# Seed platform super-admin IMMEDIATELY after server start and domain registration,
# before any heavy tenant seeding — so platform login works from the first second.
echo "[sms] Seeding platform super-admin (unconditional, runs before heavy seeding)..."
python3.11 manage.py seed_platform_data 2>&1 || echo "[sms] Platform data seed skipped"

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

  echo "[sms] Bootstrap complete."
fi

echo "[sms] Rotating insecure default admin credentials..."
python3.11 manage.py rotate_admin_credentials 2>&1 || echo "[sms] Credential rotation skipped"

echo "[sms] Waiting for server process..."
wait $SERVER_PID
