# Task Execution Register

Date: 2026-04-25

## Purpose

This document is the current source of truth for the next implementation pass.

It is designed to leave no issue unclassified:

- every known task is either `Do Now`, `Merged Into Another Task`, `Deferred`, or `Already Corrected`
- every `Do Now` task has clear acceptance criteria
- every deferred item has an explicit reason

## Inputs Reviewed

- `CRITIQUE_AND_ACTIONS.md`
- `C:\Users\emuri\OneDrive\Desktop\fix.txt`
- `C:\Users\emuri\OneDrive\Desktop\Task #22.txt`

## Confirmed Current State

### M-Pesa / Payments

- `SITE_BASE_URL` is already part of the public URL resolution path in code.
- The STK push code already sends:
  - `BusinessShortCode`
  - `PartyB`
  - `CallBackURL`
- Daraja HTTP error mapping is now split so callback URL, shortcode / `PartyB`, passkey, OAuth credentials, and generic request-validation failures are no longer collapsed into one message.
- Masked DEBUG logging now exists for OAuth, STK push, and STK query request/response diagnostics.
- Callback URL settings API now returns exact callback URL, source, HTTPS state, warning text, shortcode, and read-only `PartyB`.
- Finance settings UI now exposes the callback URL override field, exact callback URL, callback source, HTTPS state, and read-only `PartyB`.
- Parent and student payment polling still appear to fall back to generic failure text instead of prioritizing `friendly_message`.
- M-Pesa reconciliation command exists.
- Focused M-Pesa regression coverage now passes for the new error mapping and callback diagnostics surface.
- A focused GitHub Actions workflow now exists for the M-Pesa regression pack.

### Approvals Hub

- The compiled approvals hub already appears corrected for some items mentioned in `fix.txt`:
  - library acquisitions uses `/library/acquisition/requests/`
  - admissions uses `status=Submitted`
  - admissions actions use `PATCH /admissions/applications/{id}/`
  - maintenance actions use `PATCH /maintenance/requests/{id}/`
- Therefore, `fix.txt` Task `#51` is only partially still open.

### Session Timeout

- Backend policy fields already exist for `session_timeout_minutes`.
- An authenticated timeout-only settings endpoint now exists for shell use.
- The root frontend session manager now fetches tenant timeout policy instead of using a fixed 15-minute timer.
- A two-minute warning modal now appears before expiry.
- Idle activity now resets on mouse, key, click, touch, scroll, and focus.
- Proactive JWT refresh is now scheduled before access-token expiry to prevent active-user early logout.

## Execution Bundle

These are the tasks to execute in order for the next pass.

### P0. Task #52
Fix M-Pesa STK Push Failure.

Status: `Completed`

Why this is first:
- It targets an active payment failure.
- It subsumes several smaller M-Pesa clarity tasks.
- It is the fastest route to restoring core payment confidence.

Acceptance criteria:
- A sandbox STK push from the Record Payment flow either:
  - reaches the phone, or
  - returns a clear, specific Safaricom error
- Callback URL shown to operators is the exact one sent to Daraja
- `PartyB` / receiving shortcode is visible and confirmed
- Error mapping no longer collapses passkey, callback, and credential problems into one generic message
- DEBUG logs allow diagnosis without exposing secrets

Primary work items:
- verify and use `SITE_BASE_URL=https://smsb.replit.app`
- improve `_friendly_daraja_error()`
- surface callback URL clearly in settings / diagnostics UI
- surface read-only `PartyB`
- add masked DEBUG logging for STK request/response

Completion snapshot:
- `_friendly_daraja_error()` now distinguishes callback URL, shortcode / `PartyB`, passkey, OAuth credential, environment, rate-limit, server, and generic validation failures
- finance settings now show the exact callback URL Daraja will receive, its resolution source, and read-only `PartyB`
- callback URL override save / return flow is working
- focused regression pack passed: `school.test_mpesa_errors` and `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests`

Primary files:
- [mpesa.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/mpesa.py:171)
- [mpesa.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/mpesa.py:322)
- [mpesa.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/mpesa.py:328)
- [services.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/services.py:48)
- [views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/views.py:9289)
- [views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/views.py:9456)

### P1. Task #53
Fix Session Idle Timeout.

Status: `Completed`

Why this is second:
- It closes a real security gap.
- It also explains the reported unexpected logout behavior.

Acceptance criteria:
- App shell fetches tenant `session_timeout_minutes`
- Idle activity resets on mouse, key, click, and touch
- Warning modal appears two minutes before expiry
- Clicking `Stay logged in` resets the timer
- Expiry triggers logout and redirect
- Active users do not get logged out early because access tokens are refreshed before expiry

Primary work items:
- fetch security policy at shell startup
- implement reusable idle hook
- add warning modal with countdown
- call existing logout on expiry
- verify or add silent JWT refresh

Completion snapshot:
- added authenticated `GET /api/settings/session-timeout/` for any logged-in user
- root session manager now uses tenant `session_timeout_minutes` instead of a hardcoded 15-minute timeout
- warning modal now appears two minutes before expiry with live countdown and `Stay logged in`
- idle activity resets on mouse, key, click, touch, scroll, focus, and visibility return
- access tokens are now refreshed proactively before expiry
- regression pack passed: `school.test_session10_control_plane`

Primary files:
- [index-D7ltaYVC.js](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/frontend_build/assets/index-D7ltaYVC.js:1)
- [views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/views.py:3299)
- [urls.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/urls.py:251)
- [test_session10_control_plane.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/test_session10_control_plane.py:174)

### P2. Task #51
Approvals Hub Rewire, narrowed to only still-broken paths.

Status: `Completed`

Why this is third:
- It is important, but `fix.txt` overstated how much is still broken.
- The remaining work is an audit-and-repair task, not a full rebuild.

Acceptance criteria:
- All approval tabs load without endpoint errors
- Any still-broken staff-transfer path is rewired to live backend URLs
- Existing already-corrected admissions / maintenance / library behavior is preserved
- End-to-end tab audit confirms list and action flow per tab

Primary work items:
- verify whether staff-transfer tab or endpoint mapping is still broken
- audit all approval tabs against live backend routes
- fix only real remaining mismatches
- run end-to-end approval-tab verification

Completion snapshot:
- confirmed the current approvals hub scope is intentionally leave-only for HR; staff transfers are handled in the HR module and are not an approvals-hub tab anymore
- verified the compiled hub already points acquisitions, admissions, maintenance, finance, and timetable actions at live backend routes
- fixed the remaining real mismatch by making `POST /api/hr/leave-requests/{id}/reject/` accept the legacy approvals-hub payload field `reason` as an alias for `rejection_reason`
- added a regression proving the approvals-hub-style leave reject payload succeeds for an HR user
- focused verification passed: `hr.test_session7_workforce_operations`

Primary files:
- [ApprovalsHubPage-B_1PnNAs.js](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/frontend_build/assets/ApprovalsHubPage-B_1PnNAs.js:1)
- [hr/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/hr/views.py:1320)
- [hr/urls.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/hr/urls.py:94)
- [school/urls.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/urls.py:368)
- [test_session7_workforce_operations.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/hr/test_session7_workforce_operations.py:574)

### P3. Post-#52 M-Pesa Hardening Bundle

These are still valid and should follow after `#52`, because they either depend on it or are better implemented once the core STK failure path is fixed.

1. `#42` Add tests to catch phone number and STK push errors before they reach users - `Completed`
2. `#33` Add automated tests for the M-Pesa reconciliation job - `Completed`
3. `#43` Make M-Pesa error tests part of automated CI - `Completed`

### P4. Task #41
Use live Daraja status when polling still-pending M-Pesa payments.

Status: `Completed`

Why this mattered:
- The portal and bursar polling endpoints were previously reading local `PENDING` rows only.
- Live Daraja query logic existed, but only inside the reconciliation command.

Acceptance criteria:
- pending STK polls can trigger a live Daraja query instead of waiting only for callback or batch reconciliation
- a successful live query finalizes the gateway transaction into a real `Payment`
- finance status polling returns receipt metadata after live settlement
- parent and student portal polling surfaces the live payment outcome

Completion snapshot:
- added shared pending-STK refresh logic in `FinanceService.refresh_pending_mpesa_transaction()`
- finance, parent, and student M-Pesa status endpoints now use that helper for stale `PENDING` transactions
- successful live Daraja status queries now finalize the payment, allocate it, and expose receipt metadata through the normal status responses
- parent and student polling now receive the same live outcome through the existing `message` field they already render
- focused regression pack passed: `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests` and `parent_portal.tests.ParentPortalTests`

Primary files:
- [services.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/services.py:561)
- [views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/views.py:10301)
- [parent_portal/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/parent_portal/views.py:819)
- [student_portal_views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/parent_portal/student_portal_views.py:840)
- [test_finance_phase4.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/test_finance_phase4.py:432)
- [tests.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/parent_portal/tests.py:243)

## Full Task Disposition Matrix

This section classifies every relevant task so nothing remains uncategorized.

### Task #22
Warn admins before switching M-Pesa to Production mode.

Status: `Deferred`

Reason:
- Important guardrail, but not the current top payment failure.
- Better after core STK push reliability is fixed.

### Task #23
Show friendlier error messages when an M-Pesa payment push fails.

Status: `Merged Into #52`

Reason:
- `#52` already includes Daraja error-message correction as part of the STK failure fix.

### Task #24
Add automated tests to verify M-Pesa error messages are clear and accurate.

Status: `Merged Into #42`

Reason:
- Existing error test file already exists.
- The more useful next step is broader error-path coverage under `#42`.

### Task #30
Add M-Pesa callback URL field to the settings page UI.

Status: `Merged Into #52`

Reason:
- The finance settings page now includes the callback URL override field plus exact callback diagnostics.

### Task #32
Write automated tests for the callback URL settings API.

Status: `Merged Into #52`

Reason:
- Focused callback URL API tests were added during the STK failure fix because the diagnostics surface is part of the same operator workflow.

### Task #25
Add the health-check banner to the platform admin login page.

Status: `Deferred`

Reason:
- Valid platform hardening task, but not ahead of payment failure and session security fixes.

### Task #26
Surface DB health status on the platform monitoring dashboard.

Status: `Deferred`

Reason:
- Useful, but lower urgency than live payment and security issues.

### Task #27
Keep the health banner from covering fixed navigation bars.

Status: `Deferred`

Reason:
- UX/layout hardening, not higher priority than payment or security work.

### Task #28
Add automated tests to confirm DB errors return 503, not auth errors.

Status: `Deferred`

Reason:
- Important reliability guardrail, but not in the immediate bundle selected by `fix.txt`.

### Task #29
Extend DB-error protection to finance and HR serializers.

Status: `Deferred`

Reason:
- High-value backend hardening, but still behind current payment and session issues.

### Task #30
Add M-Pesa callback URL field to the settings page UI.

Status: `Do After #52`

Reason:
- Directly supports callback visibility and operator diagnosis.

### Task #31
Validate that the callback URL is reachable before saving it.

Status: `Deferred`

Reason:
- Good hardening step after callback URL visibility and API tests are in place.

### Task #32
Write automated tests for the callback URL settings API.

Status: `Merged Into #52`

Reason:
- Covered during the STK diagnostics pass because callback URL visibility and exact Daraja diagnostics shipped together.

### Task #33
Add automated tests for the M-Pesa reconciliation job.

Status: `Completed`

Reason:
- Added focused command coverage for successful reconciliation, failed reconciliation, and dry-run safety on `reconcile_mpesa_pending`.
- Focused verification passed: `school.test_mpesa_reconciliation_command`

### Task #34
Make the reconciliation interval configurable from the Settings page.

Status: `Deferred`

Reason:
- Configuration improvement, but not blocking current payment diagnosis.

### Task #35
Add automated tests to confirm finance staff get notified when an M-Pesa payment lands.

Status: `Deferred`

Reason:
- Valuable, but behind payment correctness and diagnostics.

### Task #36
Let finance staff choose which payment events trigger a notification.

Status: `Deferred`

Reason:
- Nice operational refinement after core payment correctness.

### Task #40
Show payment failure reasons to students and parents in the portal.

Status: `Completed`

Reason:
- The portal bundles already render backend `message`, `error`, and `detail` values.
- `#52` fixed initiation-path Daraja error clarity, and `#41` now feeds live failure/success messages through the polling path.

### Task #41
Use live Daraja status when polling still-pending M-Pesa payments.

Status: `Completed`

Reason:
- Completed by moving live Daraja query/reconciliation into the finance, parent, and student status endpoints.

### Task #42
Add tests to catch phone number and STK push errors before they reach users.

Status: `Completed`

Reason:
- Added focused initiation-path and validation-path coverage for bursar, parent, and student M-Pesa flows.
- Focused verification passed: `school.test_mpesa_errors`, `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests`, and `parent_portal.tests.ParentPortalTests`

### Task #43
Make M-Pesa error tests part of automated CI.

Status: `Completed`

Reason:
- Added a focused GitHub Actions workflow for the M-Pesa regression pack.
- Workflow scope is intentionally narrow: `school.test_mpesa_errors`, `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests`, `parent_portal.tests.ParentPortalTests`, and `school.test_mpesa_reconciliation_command`
- Local CI rehearsal passed: `98 tests, OK`

### Task #51
Approvals Hub - Full Endpoint Rewire.

Status: `Completed, narrowed`

Reason:
- Completed as a narrowed audit-and-repair pass.
- The only real defect left was the leave reject payload alias; staff transfers were a stale report item, not an active approvals-hub tab defect.

### Task #52
Fix M-Pesa STK Push Failure.

Status: `Completed`

Reason:
- Highest-value active payment issue, now closed.

### Task #53
Fix Session Idle Timeout.

Status: `Completed`

Reason:
- Highest-value security/session issue, now closed.

## Already Corrected Items

These items from `fix.txt` should not be re-planned as open work unless a fresh audit proves otherwise:

- approvals hub library acquisitions URL appears corrected
- approvals hub admissions `status=Submitted` appears corrected
- approvals hub admissions action style appears corrected
- approvals hub maintenance action style appears corrected

## No Open Ambiguities

The plan intentionally leaves no uncategorized issue:

- all relevant tasks from `Task #22.txt` are classified
- all three tasks introduced by `fix.txt` are classified
- stale substeps in `#51` are explicitly marked as already corrected rather than silently ignored
- M-Pesa follow-up tasks are tied to `#52` so they are not left floating

## Final Execution Order

1. `#52` Fix M-Pesa STK Push Failure
2. `#53` Fix Session Idle Timeout
3. `#51` Narrowed approvals-hub audit and rewire
4. `#41` Use live Daraja status when polling still-pending M-Pesa payments
5. `#40` Show payment failure reasons to students and parents in the portal
6. `#42` Add tests to catch phone number and STK push errors before they reach users
7. `#32` Write automated tests for the callback URL settings API
8. `#30` Add M-Pesa callback URL field to the settings page UI
9. `#33` Add automated tests for the M-Pesa reconciliation job
10. `#43` Make M-Pesa error tests part of automated CI

Current outcome:
- all active `Do Now` tasks from this register are complete
- the remaining items are either deferred by priority or already merged into completed work
