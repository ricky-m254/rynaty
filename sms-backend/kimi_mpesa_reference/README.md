# Kimi M-Pesa Reference Implementation

**Status: REFERENCE ONLY — Do not import or run these files directly**

This folder contains the `mpesa-school-saas` reference implementation provided via
`Kimi_Agent_M-Pesa_Payment_Integration_1776357940135.zip`. It is a companion to the
earlier `mpesa_saas_reference/` folder (from the previous zip).

## Contents

| Module | Purpose |
|---|---|
| `core/` | Tenant middleware + abstract `TenantModel` base |
| `ledger/` | `Wallet` and `LedgerEntry` models (double-entry ledger) |
| `payments/` | M-Pesa STK push + B2C client, transaction models, views, tasks |
| `billing/` | SaaS billing engine, plans, revenue logs, SaaS invoices |
| `fraud_detection/` | Fraud scoring engine, duplicate detection, velocity limits |
| `audit/` | Tamper-proof `AuditLog` (SHA-256 chain), `ComplianceEngine` |
| `saas_admin/` | Super-admin dashboard API: revenue, schools, alerts, audit export |
| `config/celery.py` | Celery beat schedule for background jobs |

## Key Files

- `TASK.md` — Full 1892-line enterprise task guide (same as `TASK_1776353570136.md`)
- `QUICKSTART.md` — Quick-start guide
- `DEPLOYMENT_GUIDE.md` — Production deployment notes
- `SETTINGS_ADDITIONS.py` — Django settings additions needed
- `PROJECT_URLS.py` — URL structure reference
- `requirements.txt` — Python package dependencies

## Relationship to SmartCampus

SmartCampus already has analogous models:
- `PaymentGatewayTransaction` ≈ `payments/models.py:Transaction`
- `PaymentGatewayWebhookEvent` ≈ `payments/models.py:MpesaRawLog`
- `Invoice` / `Payment` ≈ `billing/models.py`
- `school.mpesa` ≈ `payments/mpesa_client.py:MpesaClient`

Use this reference to enhance the existing SmartCampus implementation — particularly
the Wallet/Ledger, Fraud Detection, and Audit chain systems which are not yet present.
