# Live Payment Validation Evidence Template

Last updated: 2026-04-27

Use one copy of this template per live validation session.

Related runbooks:

- [LIVE_PAYMENT_VALIDATION_RUN_SEQUENCE.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/docs/LIVE_PAYMENT_VALIDATION_RUN_SEQUENCE.md:1)
- [LAUNCH_EVIDENCE_REFRESH_SEQUENCE.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/docs/LAUNCH_EVIDENCE_REFRESH_SEQUENCE.md:1)

## Session Metadata

| Field | Value |
|------|-------|
| Date | |
| Tenant | |
| Environment | |
| Base URL | |
| Operator | |
| Stripe in scope | Yes / No |
| Evidence folder | |

## Readiness Snapshot

| Check | Result | Evidence |
|------|--------|----------|
| `GET /api/finance/launch-readiness/` | | |
| `POST /api/finance/mpesa/test-connection/` | | |
| `GET /api/finance/mpesa/callback-url/` | | |

Notes:

- blocking issues:
- warnings:

## Bursar STK Validation

| Item | Result | Evidence |
|------|--------|----------|
| Student / invoice selected | | |
| STK initiation succeeded | | |
| Checkout request ID captured | | |
| Callback settled | | |
| Payment record created | | |
| Invoice balance updated | | |
| Receipt downloadable | | |

References:

- payment reference:
- gateway event ID:
- receipt number:

## Portal M-Pesa Validation

| Item | Result | Evidence |
|------|--------|----------|
| Portal used | Parent / Student |
| STK initiation succeeded | | |
| Checkout request ID captured | | |
| Polling reached final status | | |
| Portal history updated | | |
| Receipt downloadable | | |
| School-side record matched | | |

References:

- payment reference:
- gateway event ID:
- receipt number:

## Bank-Transfer Portal Sanity Check

| Item | Result | Evidence |
|------|--------|----------|
| Reference generated | | |
| Instructions shown | | |
| UI stayed pending / not falsely settled | | |

References:

- manual reference:

## Stripe Validation Or Waiver

| Item | Result | Evidence |
|------|--------|----------|
| Stripe in scope | | |
| Checkout initiation | | |
| Webhook settlement | | |
| Payment record created | | |
| Receipt downloadable | | |

If waived:

- waiver reason:
- owner:
- date:

## Gateway Event Sanity Check

| Query | Result | Evidence |
|------|--------|----------|
| `GET /api/finance/gateway/events/?processed=false` | | |
| `GET /api/finance/gateway/events/?provider=mpesa` | | |

Notes:

- recoverable failed events:
- reprocess performed:

## Receipt Confirmation

| Flow | Payment record | Receipt number | Receipt opened | Allocation correct | Duplicate avoided |
|------|----------------|----------------|----------------|--------------------|------------------|
| Bursar STK | | | | | |
| Portal M-Pesa | | | | | |
| Stripe or Waiver | | | | | |

## Remaining Blockers

| Blocker | Owner | Date Observed | Next Action |
|---------|-------|---------------|-------------|
| | | | |

## Go / No-Go Note

```text
Decision date:
Tenant:
Environment:
Decision: Go / Go with waiver / No-Go
Passed:
Waived:
Blocked:
Owner signoff:
```
