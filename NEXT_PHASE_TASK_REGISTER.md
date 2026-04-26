# Next-Phase Task Register

Date: 2026-04-26

## Purpose

This register starts after the closure of [task.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/task.md:1).

The previous register is complete. This one tracks the next operational and product-hardening wave.

## Current Baseline

- legacy issue register is closed
- M-Pesa hardening, session timeout, approvals-hub repair, DB-health surfacing, and finance ops controls are complete
- tenant secret storage and key rotation support are complete in code
- tenant secret settings now return masked reads instead of decrypted API payloads
- tenant secret inspection, connection-test, and rotation actions now emit audit trail entries
- dark-theme clarity tuning is applied at the shared theme layer to reduce blur and raise text contrast
- the approvals hub now uses real `approve`, `clarify`, and `reject` actions across the supported approval domains
- approval scope regression coverage passed against the local trust-auth Postgres instance on `127.0.0.1:55432`

## Do Now

### P0. Production Secret Rotation Rollout

Status: `Do Now`

Goal:
- roll the encrypted tenant secret store safely into staging/production

Acceptance criteria:
- `DJANGO_TENANT_SECRET_KEYS` is configured with a new primary key followed by the old key
- dry-run rotation completes with zero failures
- live rotation completes with zero failures
- no decrypt failures appear during the observation window

Primary references:
- [PRODUCTION_SECRET_ROTATION_CHECKLIST.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/docs/PRODUCTION_SECRET_ROTATION_CHECKLIST.md:1)
- [TENANT_SECRET_STORE.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/docs/TENANT_SECRET_STORE.md:1)

### P1. Live Payment Validation

Status: `Do Now`

Goal:
- confirm real-environment payment flows after the secret rotation rollout

Acceptance criteria:
- one bursar STK payment completes end to end
- one portal M-Pesa payment completes end to end
- one Stripe checkout/webhook flow completes end to end
- downloadable receipts are confirmed on the resulting records

### P2. Launch Evidence Refresh

Status: `Do Now`

Goal:
- refresh rollout evidence using live-environment results instead of only repo-backed proof

Acceptance criteria:
- payment launch evidence reflects the current tenant list, callback URL state, and live smoke results
- any remaining external blockers are named explicitly with owner and date

## Do After

### P3. Mask Secret Values In Settings Reads

Status: `Complete`

Outcome:
- settings APIs now return masked secret metadata instead of decrypted integration secrets
- settings save flows preserve existing stored secrets when blank or omitted secret fields are submitted
- the finance settings UI still detects configured M-Pesa and Stripe secrets without exposing raw values

Verification:
- focused tenant-secret and M-Pesa settings regression pack passed on the local trust-auth Postgres instance
- compiled finance settings bundle passed syntax verification

### P4. Audit Secret Access Events

Status: `Complete`

Outcome:
- masked tenant settings reads now emit `SECRET_READ` audit events
- Stripe and M-Pesa test-connection actions now emit `SECRET_TEST` audit events
- secret rotation command runs now emit `SECRET_ROTATE` or `SECRET_ROTATE_PREVIEW` audit events
- rotation can be attributed to a named operator with `--actor-username`

Verification:
- focused settings, rotation, and finance audit regressions passed locally

### P5. Workspace Hygiene Automation

Status: `Complete`

Outcome:
- root runtime artifact patterns are now ignored in git
- a scoped cleanup helper exists at [cleanup_local_artifacts.ps1](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/tools/cleanup_local_artifacts.ps1:1)
- cleanup behavior is documented in [WORKSPACE_HYGIENE.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/WORKSPACE_HYGIENE.md:1)

Verification:
- helper logic is path-scoped to the repo-root `artifacts/` directory
- ignore rules do not overlap with tracked files under `sms-backend/artifacts/`

### P6. Approval Workflow Clarification States

Status: `Complete`

Outcome:
- finance, store orders, library acquisitions, timetable, admissions, maintenance, and HR leave requests now have explicit clarification states and action endpoints
- the approvals hub exposes a real `clarify` action instead of a dead-end placeholder
- approval scope regression coverage was extended and passed for the backend clarification flows

Follow-up:
- if the product later needs multi-step requester resubmission loops after clarification, that should be tracked as a new workflow enhancement rather than reopening this task

## Deferred

### P7. Settings API Contract Tightening

Status: `Deferred`

Reason:
- secret masking is more important than broader payload redesign
- contract changes should follow after live rollout is stable

## Execution Order

1. `P0` Production Secret Rotation Rollout
2. `P1` Live Payment Validation
3. `P2` Launch Evidence Refresh
4. `P7` Settings API Contract Tightening
