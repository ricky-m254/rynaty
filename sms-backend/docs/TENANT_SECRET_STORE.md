# Tenant Secret Store

Last updated: 2026-04-26

## Purpose

This project now stores tenant-sensitive configuration outside plain `SchoolProfile` fields and outside raw `TenantSettings.value` JSON.

At-rest secrets are stored in the tenant schema in `school_tenantsecret` and encrypted before save.

## What Is Protected

Current protected values include:

- `SchoolProfile.smtp_password`
- `SchoolProfile.sms_api_key`
- `SchoolProfile.whatsapp_api_key`
- `integrations.mpesa.consumer_key`
- `integrations.mpesa.consumer_secret`
- `integrations.mpesa.passkey`
- `integrations.stripe.secret_key`
- `integrations.stripe.webhook_secret`

The secret layer also supports additional integration keys through secret-field detection in [tenant_secrets.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/tenant_secrets.py:1).

## Storage Model

Core files:

- [TenantSecret model](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/models.py:2226)
- [tenant_secrets.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/tenant_secrets.py:1)
- [migration 0065](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/migrations/0065_tenantsecret_encrypted_store.py:1)

Behavior:

- non-secret metadata stays in `SchoolProfile` and `TenantSettings`
- secret values are encrypted and stored separately in `TenantSecret`
- runtime readers merge decrypted secret values back into the in-memory config when needed
- deleting a tenant setting also deletes its related secret rows

## Settings API Behavior

Sensitive settings reads no longer return decrypted secret material to the client.

Current behavior:

- secret-backed settings payloads return only non-secret fields plus `__secret_meta__`
- each secret field is represented with configured-state metadata and a masked preview
- blank or omitted secret fields on save preserve the existing encrypted secret unless a non-empty replacement is supplied

Example secret metadata:

```json
{
  "integrations.mpesa": {
    "shortcode": "174379",
    "environment": "sandbox",
    "__secret_meta__": {
      "consumer_key": {
        "configured": true,
        "masked_label": "Configured (hidden)",
        "preview": "ck••••23"
      }
    }
  }
}
```

## Key Source

Encryption keys are derived from:

- `DJANGO_TENANT_SECRET_KEYS`, if configured
- otherwise a fallback derived from `SECRET_KEY`

Config reference:

- [settings.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/config/settings.py:110)

Operational guidance:

- put the newest key first in `DJANGO_TENANT_SECRET_KEYS`
- keep older keys after it during transition so old ciphertext can still decrypt
- once rotation is complete and verified, remove retired keys deliberately

## Rotation Command

Management command:

- [rotate_tenant_secrets.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/management/commands/rotate_tenant_secrets.py:1)
- production runbook: [PRODUCTION_SECRET_ROTATION_CHECKLIST.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/docs/PRODUCTION_SECRET_ROTATION_CHECKLIST.md:1)

Examples:

```powershell
python manage.py rotate_tenant_secrets --dry-run
python manage.py rotate_tenant_secrets
python manage.py rotate_tenant_secrets --key-prefix tenant_setting:integrations.mpesa:
```

What it does:

- decrypts each secret with any available key in the configured key ring
- re-encrypts it with the current primary key version
- supports dry-run reporting before making changes
- supports prefix scoping for targeted rotations
- supports `--actor-username` so the rotation audit trail can be attributed to a named operator

## Audit Trail

Secret inspection and handling actions now emit `AuditLog` entries in the tenant schema.

Current audit actions:

- `SECRET_READ` for masked settings reads that expose secret-backed configuration state
- `SECRET_TEST` for M-Pesa and Stripe connection-test actions
- `SECRET_ROTATE_PREVIEW` for dry-run rotation previews
- `SECRET_ROTATE` for live secret rotation runs

The audit trail records the acting user when one is available and never stores raw secret values in the log details.

## Verification

Focused regression coverage:

- [test_tenant_secret_store.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/test_tenant_secret_store.py:1)
- [test_tenant_secret_rotation.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/test_tenant_secret_rotation.py:1)
- [test_mpesa_settings_roundtrip.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/test_mpesa_settings_roundtrip.py:1)
- [test_finance_phase4.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/test_finance_phase4.py:1)

Verified behaviors:

- profile secret writes clear plaintext model columns
- M-Pesa settings round-trip still works for authorized callers with masked reads
- Stripe and M-Pesa runtime readers use decrypted secrets
- sensitive settings reads and connection-test actions create audit trail entries
- dry-run rotation reports correctly
- live rotation updates ciphertext to the current primary key version without losing plaintext meaning
- rotation runs can be attributed to a named operator

## Close-Out State

As of 2026-04-26:

- the tracked task register is closed
- the tenant secret store is live in code
- key rotation support is implemented and tested
