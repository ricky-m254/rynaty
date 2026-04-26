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
- communication transport realism, parent-portal contract repair, and operator workflow completion are complete in code
- the main remaining next-phase work is now operational rollout: secret rotation, live payment validation, and evidence refresh

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
- downloadable receipts are confirmed on the resulting records
- if Stripe is enabled in the target environment or returns to launch scope, one Stripe checkout/webhook flow completes end to end
- if Stripe remains out of the current Kenya launch scope, an explicit waiver note is captured with owner and date

Primary references:
- [LIVE_PAYMENT_VALIDATION_RUN_SEQUENCE.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/docs/LIVE_PAYMENT_VALIDATION_RUN_SEQUENCE.md:1)
- [payments_launch_runbook.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/docs/payments_launch_runbook.md:1)

### P2. Launch Evidence Refresh

Status: `Do Now`

Goal:
- refresh rollout evidence using live-environment results instead of only repo-backed proof

Acceptance criteria:
- payment launch evidence reflects the current tenant list, callback URL state, and live smoke results
- any remaining external blockers are named explicitly with owner and date

Primary references:
- [LAUNCH_EVIDENCE_REFRESH_SEQUENCE.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/docs/LAUNCH_EVIDENCE_REFRESH_SEQUENCE.md:1)
- [PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md:1)

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

### P8. Parent Portal Communications Contract Repair

Status: `Complete`

Outcome:
- parent messages, announcements, notifications, and conversation rows now expose a normalized compatibility contract through shared portal adapters
- parent communication payloads now carry stable aliases like `created_at` and `content/body` so the portal UI no longer depends on brittle field guessing
- parent announcements now respect publish windows and audience targeting instead of exposing every active record
- student dashboard announcements now use the same publish-window and audience-targeting rules
- legacy parent message dependencies remain in place for now, but are explicitly retained behind a tested compatibility adapter in [communication_contracts.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/parent_portal/communication_contracts.py:1)

Verification:
- `py_compile` passed for the changed parent portal modules
- `parent_portal.tests.ParentPortalTests`: `27 tests, OK` against the local trust-auth Postgres instance on `127.0.0.1:55432`

Primary references:
- [communication_contracts.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/parent_portal/communication_contracts.py:1)
- [views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/parent_portal/views.py:972)
- [student_portal_views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/parent_portal/student_portal_views.py:192)
- [tests.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/parent_portal/tests.py:1)

### P9. Real Communication Transport Integration

Status: `Complete`

Outcome:
- SMS dispatch now uses tenant-secret-backed provider configuration from the active school profile instead of global `COMMUNICATION_SMS_API_KEY` fallbacks
- supported SMS providers now dispatch through real HTTP integrations for Africa's Talking, Twilio, Infobip, and Vonage
- WhatsApp dispatch now uses tenant-secret-backed Meta Cloud credentials from the active school profile
- push notifications now use tenant-secret-backed `integrations.push` / `integrations.fcm` server keys instead of global push settings
- communication test endpoints now fail honestly when transport credentials are missing instead of pretending delivery succeeded
- library reminders, finance payment SMS notifications, school communication tests, and communication admin sends all inherit the same hardened transport path through the shared service layer

Verification:
- `py_compile` passed for the changed communication, school, and parent-portal modules
- focused Django pack passed on the local trust-auth Postgres instance at `127.0.0.1:55432`
- `parent_portal.tests.ParentPortalTests`, `communication.tests.CommunicationModuleTests`, and `school.test_settings_communication_endpoints`: `40 tests, OK`

Primary references:
- [communication/services.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/services.py:29)
- [school/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/views.py:3199)
- [SettingsCommunicationPage-CFoSf_AU.js](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/frontend_build/assets/SettingsCommunicationPage-CFoSf_AU.js:1)

### P10. Communications Operator Workflow Completion

Status: `Complete`

Outcome:
- email campaigns now support real scheduled queueing, explicit due-dispatch, and honest `Scheduled` / `Sent` workflow states instead of a misleading static label
- notification compose now supports admin recipient browsing, multi-recipient targeting, and bulk creation through `recipient_ids`
- admins can audit notification history beyond their own inbox using scoped notification listing and recipient filtering
- the communication dashboard now reports actual reply-lag analytics instead of a fake proxy metric, and the dashboard cards are wired to live data endpoints
- the notifications, email, and dashboard bundles now reflect the real backend workflow instead of placeholder operator affordances

Verification:
- `py_compile` passed for the changed communication, school, and parent-portal modules
- `node --check` passed for `CommunicationNotificationsPage-DW-k8B60.js`, `CommunicationEmailPage-IVp1q3cA.js`, and `CommunicationDashboardPage-Vh9v6l8X.js`
- focused Django pack passed on the local trust-auth Postgres instance at `127.0.0.1:55432`
- `parent_portal.tests.ParentPortalTests`, `communication.tests.CommunicationModuleTests`, and `school.test_settings_communication_endpoints`: `43 tests, OK`

Primary references:
- [communication/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/views.py:294)
- [communication/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/views.py:383)
- [communication/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/views.py:723)
- [CommunicationNotificationsPage-DW-k8B60.js](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/frontend_build/assets/CommunicationNotificationsPage-DW-k8B60.js:1)
- [CommunicationEmailPage-IVp1q3cA.js](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/frontend_build/assets/CommunicationEmailPage-IVp1q3cA.js:1)

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
