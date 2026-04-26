# Production Secret Rotation Checklist

Last updated: 2026-04-26

## Goal

Rotate tenant-scoped encrypted secrets onto a new primary key version without breaking:

- bursar M-Pesa STK push
- parent/student portal payment flows
- Stripe webhook verification
- communication settings that depend on stored credentials

Use this together with [TENANT_SECRET_STORE.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/docs/TENANT_SECRET_STORE.md:1).

## Preconditions

- the app version that includes `TenantSecret` and `rotate_tenant_secrets` is already deployed
- database backups or snapshots are available
- you know the current active key material and the new primary key material
- you have maintenance access to the target environment

## Key Ordering Rule

`DJANGO_TENANT_SECRET_KEYS` must be ordered like this during rotation:

1. `new_primary_key`
2. `old_primary_key`
3. any other older still-needed keys

The newest key must be first so new writes and re-encrypted rows use it.

## Preflight

1. Confirm the deployed app version includes:
   - `school_tenantsecret`
   - `rotate_tenant_secrets`
   - the secret-store runtime readers for M-Pesa and Stripe
2. Confirm current app health:
   - login works
   - finance settings open
   - M-Pesa callback diagnostics load
   - Stripe webhook path is reachable
3. Confirm backups are current.
4. Export the new key list into the runtime environment without removing the old key yet.

## Dry Run

Run:

```powershell
python manage.py rotate_tenant_secrets --dry-run
```

Expected result:

- command completes successfully
- rows are reported as `would rotate`
- failures count is `0`

If failures are non-zero:

- stop
- do not remove old keys
- investigate the failing secret rows first

## Live Rotation

Run:

```powershell
python manage.py rotate_tenant_secrets
```

Optional scoped rotation:

```powershell
python manage.py rotate_tenant_secrets --key-prefix tenant_setting:integrations.mpesa:
python manage.py rotate_tenant_secrets --key-prefix tenant_setting:integrations.stripe:
```

Expected result:

- command completes successfully
- rows are reported as `rotated`
- failures count is `0`

## Immediate Verification

After live rotation, verify in this order:

1. Finance settings page loads without integration errors.
2. `GET /api/settings/` still resolves tenant integration settings for authorized users.
3. Bursar M-Pesa connection test succeeds.
4. Bursar STK push can be initiated.
5. Parent/student M-Pesa polling still resolves payment status.
6. Stripe connection test succeeds.
7. Stripe webhook verification still succeeds.

## Payment Smoke Tests

Run one end-to-end smoke per critical path:

1. Bursar STK push:
   - initiate payment
   - confirm callback lands
   - confirm receipt becomes downloadable
2. Parent or student M-Pesa:
   - initiate portal payment
   - confirm polling returns final status
3. Stripe:
   - create checkout session
   - confirm webhook settlement
   - confirm payment record and receipt availability

## Observation Window

Keep both the new and old keys configured during the observation window.

Recommended checks:

- payment error rate
- webhook signature failures
- M-Pesa token/STK failures
- finance settings load failures
- any `Unable to decrypt tenant secret` exceptions

## Final Cutover

Only after the observation window is clean:

1. remove the retired key from `DJANGO_TENANT_SECRET_KEYS`
2. redeploy
3. rerun a smaller smoke set:
   - M-Pesa connection test
   - Stripe connection test
   - one payment initiation path

## Rollback

If rotation causes issues:

1. restore the previous key ordering with the old key still present
2. redeploy if needed
3. do not rotate again until the failing path is understood

Because ciphertext remains valid for any key still in the configured key ring, the safest rollback is usually restoring the old key list rather than modifying database rows again immediately.
