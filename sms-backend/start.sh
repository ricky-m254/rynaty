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

echo "[sms] Repairing diverged migration state (0058: photo/bio; 0059: wallet/ledger)..."
# Step 1: per-schema detection of drift for migrations 0058 and 0059.
#         Each schema is wrapped in its own try/except so a failure on one
#         schema never prevents the others from being processed.
#         Writes schema names that need a targeted migrate to /tmp/_repair_drift.txt.
python3.11 manage.py shell -c "
import sys
from django.db import connection
from django_tenants.utils import get_public_schema_name

PUBLIC = get_public_schema_name()
connection.set_schema_to_public()
with connection.cursor() as cur:
    cur.execute(\"SELECT schema_name FROM clients_tenant WHERE schema_name <> %s ORDER BY schema_name\", [PUBLIC])
    schemas = [r[0] for r in cur.fetchall()]

repaired = []
for schema in schemas:
    try:
        connection.set_schema(schema)
        with connection.cursor() as cur:
            # ── 0058: check photo + bio columns on school_userprofile ─────
            cur.execute(
                \"SELECT column_name FROM information_schema.columns \"
                \"WHERE table_schema=%s AND table_name='school_userprofile' \"
                \"AND column_name IN ('photo','bio')\",
                [schema],
            )
            existing_cols = {r[0] for r in cur.fetchall()}
            if 'photo' not in existing_cols or 'bio' not in existing_cols:
                cur.execute(
                    \"DELETE FROM django_migrations WHERE app='school' AND name='0058_userprofile_photo'\"
                )
                missing = {'photo','bio'} - existing_cols
                print(f'  [repair-0058] {schema}: cleared stale record (missing cols: {missing})')
                if schema not in repaired:
                    repaired.append(schema)

            # ── 0059: check school_wallet table ───────────────────────────
            cur.execute(
                \"SELECT 1 FROM information_schema.tables \"
                \"WHERE table_schema=%s AND table_name='school_wallet' LIMIT 1\",
                [schema],
            )
            wallet_exists = cur.fetchone() is not None
            if not wallet_exists:
                # Only clear if 0059 is recorded as applied (stale record)
                cur.execute(
                    \"SELECT 1 FROM django_migrations WHERE app='school' AND name='0059_wallet_ledger_fraud_audit' LIMIT 1\"
                )
                if cur.fetchone():
                    cur.execute(
                        \"DELETE FROM django_migrations WHERE app='school' \"
                        \"AND name IN ('0059_wallet_ledger_fraud_audit','0060_financeauditlog_created_at_stable')\"
                    )
                    print(f'  [repair-0059] {schema}: cleared stale 0059/0060 records (wallet table missing)')
                    if schema not in repaired:
                        repaired.append(schema)
    except Exception as exc:
        print(f'  [repair] WARNING: schema {schema!r} check failed — {exc}', file=sys.stderr)

connection.set_schema_to_public()
if repaired:
    print(f'  [repair] Will re-migrate {len(repaired)} schema(s): {repaired}')
    with open('/tmp/_repair_drift.txt', 'w') as f:
        f.write('\n'.join(repaired) + '\n')
else:
    print('  [repair] All schemas OK — no drift detected.')
    open('/tmp/_repair_drift.txt', 'w').close()
" 2>&1 | grep -v "^$" || true

# Step 2: for each drifted schema, run a targeted migration immediately
#         so columns/tables exist before any seeding or login touches them.
if [ -s /tmp/_repair_drift.txt ]; then
  while IFS= read -r _schema; do
    [ -z "$_schema" ] && continue
    echo "  [repair] Applying migrations to schema: $_schema"
    python3.11 manage.py migrate_schemas --noinput --schema="$_schema" school 2>&1 | grep -v "^$" || true
  done < /tmp/_repair_drift.txt
fi

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

# ── Structural seeding — runs unconditionally for EVERY tenant ─────────────
# These commands are fully idempotent (get_or_create / skip-if-exists).
# They ensure every school has modules, RBAC grants, curriculum templates,
# and e-learning content regardless of the BOOTSTRAP_DEMO_DATA flag.

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
fi

echo "[sms] Seeding modules for all tenants..."
python3.11 manage.py seed_modules --all-tenants 2>&1 | grep -E "^\[|Error|error" || true

echo "[sms] Seeding roles and permissions for all tenants..."
python3.11 manage.py seed_default_permissions --assign-roles --all-tenants 2>&1 | grep -E "^\[|Error|error" || true

echo "[sms] Seeding school profile and academic structure for all tenants..."
python3.11 manage.py seed_school_data --all-tenants 2>&1 | grep -E "^\[|Error|error" || true

echo "[sms] Seeding curriculum templates for all tenants..."
python3.11 manage.py seed_curriculum_templates --all-tenants 2>&1 | grep -E "^\[|Seeding|Done|Error" || true

echo "[sms] Seeding KICD digital textbooks and Harvard open learning for all tenants..."
python3.11 manage.py seed_digital_resources --all-tenants 2>&1 | grep -E "^\[|Error|error" || true

if [ "${BOOTSTRAP_DEMO_DATA:-false}" = "true" ]; then
  schema="${DEMO_SCHEMA_NAME:-demo_school}"

  echo "[sms] Seeding full Kenya school data (idempotent)..."
  python3.11 manage.py seed_kenya_school --schema_name "$schema" 2>&1 | tail -5 || echo "[sms] Kenya seed skipped"

  echo "[sms] Seeding portal login accounts..."
  python3.11 manage.py seed_portal_accounts --schema_name "$schema" 2>&1 || echo "[sms] Portal accounts skipped"

  echo "[sms] Seeding staff user accounts for all role types..."
  python3.11 manage.py seed_staff_users --schema_name "$schema" 2>&1 || echo "[sms] Staff users skipped"

  echo "[sms] Seeding supplementary demo data (25+ records per module)..."
  python3.11 manage.py seed_extra_data --schema_name "$schema" 2>&1 || echo "[sms] Extra data seed skipped"

  echo "[sms] Bootstrap complete."
fi

# ── M-Pesa callback URL auto-configuration ──────────────────────────────────
# Runs AFTER all tenant creation/seeding so every schema (including ones just
# created by seed_olom_tenant or seed_demo) receives the system.callback_base_url
# setting.  The M-Pesa STK push view reads this key so Safaricom's callback always
# reaches the correct publicly-accessible host regardless of deployment environment.
echo "[sms] Configuring M-Pesa callback base URL for all tenants..."
_mpesa_callback_base=""
if [ -n "${SITE_BASE_URL:-}" ]; then
  _mpesa_callback_base="${SITE_BASE_URL%/}"
elif [ -n "${REPLIT_DOMAINS:-}" ]; then
  _first_domain="$(echo "$REPLIT_DOMAINS" | cut -d',' -f1 | tr -d ' ')"
  _mpesa_callback_base="https://${_first_domain}"
fi

if [ -n "$_mpesa_callback_base" ]; then
  echo "[sms] M-Pesa callback URL: ${_mpesa_callback_base}/api/finance/mpesa/callback/"
else
  echo "[sms] WARNING: No SITE_BASE_URL or REPLIT_DOMAINS set — M-Pesa callbacks will fall back to request host."
fi

python3.11 manage.py configure_mpesa_callback 2>&1 | grep -E "^\[|Detected|Full callback|WARNING|Error" || true

echo "[sms] Rotating insecure default admin credentials..."
python3.11 manage.py rotate_admin_credentials 2>&1 || echo "[sms] Credential rotation skipped"

# ── Trial expiry check (spec §6.3) ──────────────────────────────────────────
# Run once at startup to catch any trials that expired while the server was down.
# In production with cron access, schedule: 0 2 * * * manage.py check_trial_expiry
echo "[sms] Checking trial expirations at startup..."
python3.11 manage.py check_trial_expiry 2>&1 || echo "[sms] Trial expiry check skipped"

# ── Background cron loop: check trial expiry every 6 hours ──────────────────
(
  while true; do
    sleep 21600  # 6 hours
    python3.11 manage.py check_trial_expiry 2>&1 || true
  done
) &

echo "[sms] Waiting for server process..."
wait $SERVER_PID
