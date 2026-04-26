# Production Secret Rotation Run Sequence

Last updated: 2026-04-27

Use this together with:

- [PRODUCTION_SECRET_ROTATION_CHECKLIST.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/docs/PRODUCTION_SECRET_ROTATION_CHECKLIST.md:1)
- [TENANT_SECRET_STORE.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/docs/TENANT_SECRET_STORE.md:1)

Operator helper:

- [run_secret_rotation_sequence.ps1](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/tools/run_secret_rotation_sequence.ps1:1)

This is the exact operator flow for `P0`.

## Placeholders To Replace

Before you run anything, replace:

- `<APP_DIR>` with the deployed backend directory
- `<VENV_PYTHON>` with the deployed Python executable
- `<ADMIN_USERNAME>` with the named operator account
- `<NEW_PRIMARY_KEY>` with the new key material
- `<OLD_PRIMARY_KEY>` with the current key material

Example placeholders:

```powershell
$APP_DIR = 'C:\srv\sms-backend'
$VENV_PYTHON = 'C:\srv\sms-backend\.venv\Scripts\python.exe'
$ADMIN_USERNAME = 'platformops'
```

## Phase 1. Confirm Deployed Capability

Open a shell on the target host and run:

```powershell
Set-Location <APP_DIR>
& <VENV_PYTHON> manage.py showmigrations school | Select-String '0065_tenantsecret_encrypted_store'
& <VENV_PYTHON> manage.py help rotate_tenant_secrets
```

Expected result:

- migration `0065_tenantsecret_encrypted_store` is listed as applied
- the `rotate_tenant_secrets` command is available

If either check fails:

- stop
- do not rotate secrets on that host

## Phase 2. Export The Key Ring

Keep the old key during rotation.

PowerShell example:

```powershell
$env:DJANGO_TENANT_SECRET_KEYS = '<NEW_PRIMARY_KEY>,<OLD_PRIMARY_KEY>'
Write-Host $env:DJANGO_TENANT_SECRET_KEYS
```

Ordering rule:

1. new key first
2. old key second

Do not remove the old key yet.

## Phase 3. Preflight Health

Run:

```powershell
& <VENV_PYTHON> manage.py check
```

Then manually confirm in the live app:

1. finance settings page loads
2. M-Pesa diagnostics page loads
3. Stripe configuration page loads
4. platform login works

If any of those fail:

- stop before rotation

## Phase 4. Dry Run Rotation

Run:

```powershell
& <VENV_PYTHON> manage.py rotate_tenant_secrets --dry-run --actor-username <ADMIN_USERNAME>
```

Expected result:

- command exits successfully
- rows show as `would rotate`
- failures count is `0`

If failures are non-zero:

1. keep both keys configured
2. stop
3. inspect the named secret rows before retrying

## Phase 5. Optional Scoped Dry Runs

If you want to reduce risk by checking critical integrations first:

```powershell
& <VENV_PYTHON> manage.py rotate_tenant_secrets --dry-run --actor-username <ADMIN_USERNAME> --key-prefix tenant_setting:integrations.mpesa:
& <VENV_PYTHON> manage.py rotate_tenant_secrets --dry-run --actor-username <ADMIN_USERNAME> --key-prefix tenant_setting:integrations.stripe:
& <VENV_PYTHON> manage.py rotate_tenant_secrets --dry-run --actor-username <ADMIN_USERNAME> --key-prefix tenant_setting:integrations.push:
```

## Phase 6. Live Rotation

Run:

```powershell
& <VENV_PYTHON> manage.py rotate_tenant_secrets --actor-username <ADMIN_USERNAME>
```

Expected result:

- command exits successfully
- rows show as `rotated`
- failures count is `0`

If you need a scoped live rotation instead:

```powershell
& <VENV_PYTHON> manage.py rotate_tenant_secrets --actor-username <ADMIN_USERNAME> --key-prefix tenant_setting:integrations.mpesa:
& <VENV_PYTHON> manage.py rotate_tenant_secrets --actor-username <ADMIN_USERNAME> --key-prefix tenant_setting:integrations.stripe:
```

## Phase 7. Immediate API Verification

Run or verify immediately after live rotation:

```powershell
& <VENV_PYTHON> manage.py shell -c "from school.models import TenantSettings; print(TenantSettings.objects.filter(key__startswith='integrations.').count())"
```

Then verify in the app:

1. finance settings still load
2. masked secret metadata still shows configured state
3. M-Pesa test connection succeeds
4. Stripe connection test succeeds

## Phase 8. Live Payment Smoke Tests

Run one smoke for each critical path:

1. Bursar STK push
   - start STK
   - confirm callback settles
   - confirm receipt downloads
2. Parent or student M-Pesa payment
   - start portal payment
   - confirm polling reaches final status
   - confirm payment history reflects the settled payment
3. Stripe
   - create checkout session
   - complete settlement
   - confirm webhook updates records
   - confirm receipt availability

## Phase 9. Observation Window

Keep both keys configured during the observation window.

Watch for:

- `Unable to decrypt tenant secret`
- M-Pesa token or STK failures
- Stripe webhook signature failures
- communication transport failures
- settings load errors

Recommended minimum window:

- one business cycle with at least one real M-Pesa flow and one Stripe flow

## Phase 10. Final Cutover

Only after the observation window is clean:

```powershell
$env:DJANGO_TENANT_SECRET_KEYS = '<NEW_PRIMARY_KEY>'
Write-Host $env:DJANGO_TENANT_SECRET_KEYS
```

Then restart or redeploy the app, and rerun this smaller smoke set:

1. M-Pesa connection test
2. Stripe connection test
3. one payment initiation path
4. one communication test send if those integrations are configured

## Rollback

If anything fails after live rotation:

```powershell
$env:DJANGO_TENANT_SECRET_KEYS = '<NEW_PRIMARY_KEY>,<OLD_PRIMARY_KEY>'
Write-Host $env:DJANGO_TENANT_SECRET_KEYS
```

Then restart or redeploy if required by the environment.

Rollback rule:

- restore the old key ring first
- do not immediately rewrite database rows again
- stabilize reads and writes before attempting another rotation pass
