# Payment Systems Launch Evidence
## Baseline And Validation Tracker

**Created:** April 19, 2026  
**Purpose:** Central place to freeze the current launch-candidate baseline and capture evidence for payment launch validation

---

## Frozen Validation Baseline

Use this baseline for all launch-validation evidence unless a newer candidate is explicitly approved.

| Field | Value |
|------|-------|
| Frozen at | April 19, 2026 23:44:40 -07:00 |
| Git branch | `main` |
| Candidate commit | `e523470ebbf6d03d8ba4f2cced12d31dddd3edef` |
| Source docs | `PAYMENT_SYSTEMS_SECOND_AUDIT.md`, `PAYMENT_SYSTEMS_FASTTRACK_PLAN.md`, `PAYMENT_SYSTEMS_TASK_PLAN.md` |

### Workspace note at freeze time

The workspace was not fully clean when this baseline was recorded.

Observed local changes:

- `PAYMENT_SYSTEMS_SECOND_AUDIT.md` untracked

Interpretation:

- payment code paths were already repo-verified before this freeze
- the committed baseline includes the portal-view doc clarification and payment planning artifacts
- any staging validation should still record the exact environment, tenant, and build used

---

## Evidence Rules

Every completed task should capture at least one of:

- API response capture
- screenshot
- test run output
- staging payment reference
- gateway event ID
- bank import file name and result summary
- signoff note from finance / support / bursar

Recommended naming convention:

- `YYYY-MM-DD_<tenant>_<task-id>_<short-description>`

Examples:

- `2026-04-20_demo-school_TP-101_launch-readiness.json`
- `2026-04-20_demo-school_TP-108_stripe-checkout-success.png`
- `2026-04-20_demo-school_TP-114_gateway-event-reprocess.md`

---

## Current Launch Scope Note

As of April 20, 2026, the current Kenya launch track is focusing on M-Pesa and bank-transfer flows.

- Stripe remains implemented in the repo
- Stripe is intentionally out of current launch-gating scope by decision
- Stripe evidence stays in this tracker for later follow-up, but it should not block the current Kenya rollout

---

## Evidence Tracker

| Task ID | Task | Status | Evidence Location | Evidence Summary | Notes |
|--------|------|--------|-------------------|------------------|-------|
| TP-001 | Confirm launch tenant list | In Progress | `docs/finance_test_report.md`, `sms-backend/clients/management/commands/seed_platform_data.py`, `sms-backend/parent_portal/tests.py` | `demo_school` chosen as the local test tenant; `demo_school_smoke_test` remains a smoke-test-only reference tenant | Final staging/production launch list still needs owner confirmation |
| TP-002 | Confirm access and credentials ownership | Blocked | TBD | TBD | Waiting on platform / finance owner confirmation |
| TP-003 | Freeze launch-candidate baseline | Complete | `PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md` | Baseline frozen at commit `e523470ebbf6d03d8ba4f2cced12d31dddd3edef` on `main` | Workspace note captured above |
| TP-004 | Create evidence tracker | Complete | `PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md` | Central validation tracker created | Use this file to append results and links |
| TP-101 | Run readiness endpoint per tenant | In Progress | `demo_school` local preflight via `FinanceLaunchReadinessView` on `test_sms_school_db` | `ready: false`; remaining blocking issues are Stripe-only and are currently outside the Kenya launch scope | Local test tenant uses HTTPS `demo.localhost`; `mpesa.callback_source: tenant_settings`; M-Pesa tenant config now passes local readiness |
| TP-102 | Defer Stripe connection validation for current Kenya launch | Deferred | April 20, 2026 scope decision recorded in this tracker and `PAYMENT_SYSTEMS_TASK_PLAN.md` | Stripe validation is parked for the current Kenya rollout | Keep repo/local Stripe findings for later if Stripe is reintroduced |
| TP-103 | Validate M-Pesa test connection | In Progress | `demo_school` local preflight via `MpesaTestConnectionView` on `test_sms_school_db` | HTTP 200: connected to Daraja sandbox and obtained OAuth token successfully | Consumer key/secret were applied locally to `demo_school` without storing raw values in this tracker; final launch tenants still need replay once confirmed |
| TP-104 | Validate public callback and webhook URLs | In Progress | `demo_school` local preflight via `MpesaCallbackUrlView` and readiness on `test_sms_school_db` | Callback URL resolves to `https://demo.localhost/api/finance/mpesa/callback/` with `source: tenant_settings` | Local callback proof is captured; external reachability still needs staging evidence |
| TP-105 | Resolve tenant config gaps | In Progress | `demo_school` local readiness, callback, and portal simulations on `test_sms_school_db` | In-scope local gaps are largely closed for the Kenya rollout simulation | External callback proof and tenant-by-tenant confirmation still remain before calling this done |
| TP-106 | Parent portal staging smoke test | In Progress | `demo_school` local dry-run via `ParentFinancePayView` on `test_sms_school_db`; `parent_portal.tests.DemoSchoolPortalSmokeTests` | Bank transfer returned HTTP `201` with manual reference; M-Pesa returned HTTP `201` with checkout request ID using mocked STK push; targeted portal smoke tests passed | Local portal behavior is proven; staging execution with live evidence still remains |
| TP-107 | Student portal staging smoke test | In Progress | `demo_school` local dry-run via `StudentFinancePayView` on `test_sms_school_db`; `parent_portal.tests.DemoSchoolPortalSmokeTests` | Bank transfer returned HTTP `201` with manual reference; M-Pesa returned HTTP `201` with checkout request ID using mocked STK push; targeted portal smoke tests passed | Local portal behavior is proven; staging execution with live evidence still remains |
| TP-108 | Validate Stripe settlement end to end if Stripe is reintroduced later | Deferred | April 20, 2026 scope decision recorded in this tracker and `PAYMENT_SYSTEMS_TASK_PLAN.md` | Stripe settlement proof is not required for the current Kenya rollout | Reopen only if Stripe returns to launch scope |
| TP-109 | M-Pesa end-to-end staging settlement | In Progress | `demo_school` local simulated settlement via `ParentFinancePayView` + `MpesaStkCallbackView` on `test_sms_school_db`; `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests` | Initiation returned HTTP `201`; callback returned HTTP `200`; duplicate callback remained safe; transaction moved to `SUCCEEDED`; payment was created and invoice balance updated; targeted M-Pesa callback tests passed | Uses a synthetic callback payload against the real callback endpoint; live staging receipt/callback proof still required |
| TP-110 | Collect real bank statement samples | Pending | TBD | TBD | Track bank name and sample owner |
| TP-111 | Import real statement file | Blocked | `demo_school` local synthetic CSV simulation via `BankStatementLineViewSet.import_csv` on `test_sms_school_db`; `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests` | Synthetic CSV import returned HTTP `201` and created two bank lines successfully; targeted CSV import test passed | Real bank statement sample is still required before this task can complete |
| TP-112 | Validate reconciliation outcomes | Blocked | `demo_school` local synthetic CSV simulation via bank-line actions on `test_sms_school_db`; `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests` | One line auto-matched, correction via `unmatch` was exercised, forced/manual match via `PATCH` was verified, the line was re-matched and cleared, one line remained `UNMATCHED`, ambiguous-match protection test passed, and manual match guardrails now reject direct status forcing while preserving safe `PATCH`-based matching | Mechanics are proven locally, but acceptance still requires a real bank statement sample |
| TP-113 | Exercise failed-event inspection | In Progress | `demo_school` local simulated failed callback via `PaymentGatewayWebhookEventViewSet.list` on `test_sms_school_db`; `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests` | Failed M-Pesa callback event appeared in `/api/finance/gateway/events/?provider=mpesa&processed=false`; targeted failed-event path test passed | Local operator path is proven; finance/support still need the staging walkthrough |
| TP-114 | Exercise manual reprocess | In Progress | `demo_school` local simulated failed callback via `PaymentGatewayWebhookEventViewSet.reprocess` on `test_sms_school_db`; `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests` | Reprocess returned HTTP `200`, cleared the event error, and created the missing payment after the gateway transaction was added; targeted reprocess test passed | Local operator path is proven; staging drill still remains |
| TP-115 | Run support / bursar walkthrough | Pending | TBD | TBD | Signoff note or annotated runbook |
| TP-116 | Produce launch go/no-go summary | Pending | TBD | TBD | Final decision note |

---

## Tenant And Owner Register

Fill this in before staging execution begins.

| Tenant | Environment | Owner | Optional Stripe Owner | M-Pesa Owner | Bank Sample Owner | Notes |
|--------|-------------|-------|--------------|--------------|-------------------|-------|
| demo_school | Selected local test tenant | TBD | TBD | TBD | TBD | Chosen for local task execution; seeded into `test_sms_school_db`; readiness snapshot captured against `https://demo.localhost` |
| demo_school_smoke_test | Test-only smoke tenant | N/A | N/A | N/A | N/A | Created in `sms-backend/parent_portal/tests.py`; useful for smoke coverage reference, not a launch tenant by default |
| TBD | TBD | TBD | TBD | TBD | TBD | TBD |

---

## Local Preflight Notes

### demo_school setup

Local dry-run execution used the temp PostgreSQL instance on port `55432` with database `test_sms_school_db`.

Successful setup steps:

- `seed_demo --schema_name demo_school --domain demo.localhost`
- `migrate_schemas --schema=demo_school --noinput`
- `seed_portal_accounts --schema_name demo_school`
- `seed_finance_config --schema demo_school`

Local credential update performed during tasking:

- sandbox M-Pesa consumer key and consumer secret were applied to `demo_school` in local `TenantSettings`
- raw secret values were intentionally not copied into this evidence file

Observed setup wrinkle:

- the first portal/finance seed attempt failed because the newly created tenant schema did not yet have app tables
- rerunning after `migrate_schemas --schema=demo_school --noinput` fixed the issue

### TP-101 demo_school readiness snapshot

Initial local result:

- `ready: false`
- `public_base_url: https://demo.localhost`
- Stripe webhook URL resolves to `https://demo.localhost/api/finance/gateway/webhooks/stripe/`
- M-Pesa callback URL resolves to `https://demo.localhost/api/finance/mpesa/callback/`
- `mpesa.callback_source: tenant_settings`

Blocking issues returned:

- missing `integrations.stripe.secret_key`
- missing `integrations.stripe.webhook_secret`
- missing M-Pesa `consumer_key`
- missing M-Pesa `consumer_secret`

Warning returned:

- no bank CSV imports recorded yet

Follow-up local result after applying sandbox M-Pesa consumer credentials:

- `ready: false`
- `public_base_url: https://demo.localhost`
- Stripe webhook URL still resolves to `https://demo.localhost/api/finance/gateway/webhooks/stripe/`
- M-Pesa callback URL still resolves to `https://demo.localhost/api/finance/mpesa/callback/`
- `mpesa.callback_source: tenant_settings`

Blocking issues returned on rerun:

- missing `integrations.stripe.secret_key`
- missing `integrations.stripe.webhook_secret`

Warning returned on rerun:

- no bank CSV imports recorded yet

Current interpretation for launch tasking:

- the rerun shows only Stripe-specific gaps
- those Stripe-specific gaps are not being treated as blockers for the current Kenya launch scope as of April 20, 2026

### TP-102 Stripe validation note for current Kenya launch

- Stripe is intentionally deferred for the current Kenya rollout
- the last local preflight result remains on record for later reference:
  HTTP `400` with `Stripe is not configured for this school. Go to Settings -> Finance -> Stripe to add your API keys.`

Local Stripe credential search notes:

- repo search found only placeholders and test literals such as `sk_test_demo`, `pk_test_...`, and `whsec_demo`
- no usable Stripe secret key or webhook secret was present in local `STRIPE_*` environment variables
- no local Stripe CLI config was present under `~/.config/stripe/config.toml`, `~/.stripe/config.toml`, or `%AppData%/stripe/config.toml`
- Stripe docs indicate real sandbox keys come from the Stripe Dashboard, while CLI-restricted keys are created after `stripe login`

### TP-103 demo_school M-Pesa test-connection result

- initial local preflight returned HTTP `400` because `consumer_key` and `consumer_secret` were missing
- after the sandbox credentials were applied locally to `demo_school`, the endpoint rerun returned HTTP `200`
- response message: `Connected to Daraja sandbox — OAuth token obtained successfully.`
- environment reported as `sandbox`
- the successful OAuth test required one outbound run outside the shell sandbox to distinguish credential validity from local network restrictions

### TP-104 demo_school callback URL proof

- `MpesaCallbackUrlView` returned `callback_base_url: https://demo.localhost`
- `effective_base_url: https://demo.localhost`
- `full_callback_url: https://demo.localhost/api/finance/mpesa/callback/`
- `source: tenant_settings`
- the readiness rerun matched the same callback URL and source
- this proves stable local callback resolution; public external reachability still needs staging proof

### TP-106 demo_school parent portal local smoke

- bank transfer initiation returned HTTP `201`
- response `payment_method: Bank Transfer`
- response `status: INITIATED`
- response `requires_manual_confirmation: true`
- created transaction provider: `parent_portal`
- local reference captured: `PPORT-02F8EF69`

- M-Pesa initiation returned HTTP `201`
- response `payment_method: M-Pesa`
- response `status: PENDING`
- response `checkout_request_id: ws_CO_demo_parent_livecheck_001`
- created transaction provider: `mpesa`
- mocked STK push received callback URL `https://demo.localhost/api/finance/mpesa/callback/`

Interpretation:

- parent portal initiation logic works locally for the current Kenya in-scope methods
- M-Pesa initiation evidence here is a local dry-run with the STK push mocked, not a live settlement proof

### TP-107 demo_school student portal local smoke

- bank transfer initiation returned HTTP `201`
- response `payment_method: Bank Transfer`
- response `status: INITIATED`
- response `requires_manual_confirmation: true`
- created transaction provider: `student_portal`
- local reference captured: `STPORT-E76FDD25`

- M-Pesa initiation returned HTTP `201`
- response `payment_method: M-Pesa`
- response `status: PENDING`
- response `checkout_request_id: ws_CO_demo_student_livecheck_001`
- created transaction provider: `mpesa`
- mocked STK push received callback URL `https://demo.localhost/api/finance/mpesa/callback/`

Interpretation:

- student portal initiation logic works locally for the current Kenya in-scope methods
- M-Pesa initiation evidence here is a local dry-run with the STK push mocked, not a live settlement proof

### TP-109 demo_school local M-Pesa settlement simulation

- simulation suffix: `043444`
- parent portal M-Pesa initiation returned HTTP `201`
- the real callback endpoint `MpesaStkCallbackView` accepted the synthetic success payload with HTTP `200`
- replaying the same callback a second time also returned HTTP `200`
- gateway transaction `ws_CO_stage_settle_043444` finished as `SUCCEEDED`
- gateway transaction reconciliation flag became `true`
- payment `MPESA-STAGE-043444` was created for `KES 250.00`
- invoice balance moved from `KES 1000.00` to `KES 750.00`
- the stored callback event was marked processed with no error

Interpretation:

- the local callback settlement path works end to end for a simulated success case
- duplicate callback replay remained safe in this simulation
- one non-fatal billing-fee warning appeared because the callback was invoked directly in shell without full tenant middleware context; settlement itself still completed

### TP-111 and TP-112 demo_school local bank reconciliation simulation

- simulation suffix: `043444`
- synthetic CSV import returned HTTP `201`
- import created `2` bank statement lines
- line `BANK-SIM-043444` auto-matched successfully with HTTP `200`
- the correction path was exercised with `unmatch`, returning the line to `UNMATCHED`
- the same line was re-matched successfully with HTTP `200`
- clearing the matched line returned HTTP `200` and final status `CLEARED`
- the second imported line `BANK-UNMATCHED-043444` remained `UNMATCHED`

Interpretation:

- local reconciliation mechanics work for import, auto-match, correction, re-match, and clear
- this remains simulation evidence only until a real bank statement sample is supplied

Additional manual-match verification:

- verification suffix: `80B41E`
- `PATCH /api/finance/reconciliation/bank-lines/{id}/` successfully set `matched_payment` and `status: MATCHED`
- the patched line exposed `matched_payment_reference: BANK-MANUAL-80B41E`
- `POST /api/finance/reconciliation/bank-lines/{id}/clear/` then returned HTTP `200`
- final line status became `CLEARED`

Interpretation:

- the backend already supports a forced/manual bank-line match through the standard `PATCH` update path
- this means the remaining bank blockers are real-sample and operator-evidence gaps, not a missing forced-match capability

### TP-113 and TP-114 demo_school local operator recovery simulation

- failed-event/reprocess verification suffix: `F4ADB0`
- a synthetic M-Pesa callback with no matching gateway transaction returned HTTP `200` to the caller but stored an unprocessed gateway event
- the event error before reprocess was:
  `Unknown M-Pesa checkout_request_id: ws_CO_stage_retryverify_F4ADB0`
- the failed event appeared in `/api/finance/gateway/events/?provider=mpesa&processed=false`
- after the missing gateway transaction was added, manual reprocess returned HTTP `200`
- the event then became processed with an empty error string
- payment `MPESA-RETRYVERIFY-F4ADB0` was created during reprocess

Interpretation:

- the local operator recovery path works for inspect-failed-event and manual reprocess
- this still needs a real staging walkthrough by finance/support before signoff

### Automated simulation test run

Targeted Django test run completed against the local temp PostgreSQL instance on port `55432` with `--keepdb`.

Passed tests:

- `parent_portal.tests.DemoSchoolPortalSmokeTests.test_demo_school_parent_bank_transfer_flow`
- `parent_portal.tests.DemoSchoolPortalSmokeTests.test_demo_school_parent_mpesa_flow`
- `parent_portal.tests.DemoSchoolPortalSmokeTests.test_demo_school_student_bank_transfer_flow`
- `parent_portal.tests.DemoSchoolPortalSmokeTests.test_demo_school_student_mpesa_flow`
- `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests.test_bank_line_import_csv_creates_rows_and_supports_match_then_clear`
- `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests.test_bank_line_auto_match_leaves_ambiguous_amount_matches_unmatched`
- `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests.test_mpesa_callback_is_idempotent_for_duplicate_payloads`
- `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests.test_mpesa_callback_can_be_reprocessed_after_missing_transaction_is_fixed`
- `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests.test_mpesa_callback_records_billing_fee_using_active_tenant_context`
- `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests.test_mpesa_callback_retry_path_logs_at_info_for_missing_transaction`

Result:

- `10` tests run
- overall result: `OK`
- runtime: about `216` seconds

Follow-up log cleanup result:

- rerun completed without the earlier billing-fee warning
- rerun completed without the earlier retry-path warning being emitted as a warning
- new regression coverage now verifies:
  billing fee recording resolves tenant context from the active schema when `request.tenant` is absent
  the expected missing-transaction retry path logs at `INFO`, not `WARNING`

Interpretation:

- the targeted automated tests align with the local shell simulations for portal initiation, M-Pesa callback idempotency, manual reprocess, and bank import/reconciliation mechanics
- the non-fatal log issues observed earlier are now resolved in code and covered by regression tests
- the remaining blockers are still real staging evidence and real bank samples, not failing local simulation tests

### Follow-up bank reconciliation guardrail test run

Targeted Django test rerun completed against the same temp PostgreSQL instance on port `55432` with `--keepdb` after tightening bank-line `PATCH` behavior.

Passed tests:

- `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests.test_bank_line_auto_match_uses_payment_reference`
- `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests.test_bank_line_import_csv_creates_rows_and_supports_match_then_clear`
- `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests.test_bank_line_manual_patch_match_sets_status_to_matched`
- `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests.test_bank_line_patch_rejects_direct_status_changes`
- `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests.test_bank_line_auto_match_leaves_ambiguous_amount_matches_unmatched`

Result:

- `5` tests run
- overall result: `OK`
- runtime: about `104` seconds

Interpretation:

- manual reconciliation via `PATCH` remains available for attaching a payment safely
- direct status forcing through `PATCH` is now rejected with a clear validation message, so operators must use the dedicated `clear`, `unmatch`, or `ignore` actions for state changes
- existing auto-match, import, clear, and ambiguous-match protections still passed after the serializer hardening

---

## Signoff Log

| Date | Area | Decision / Signoff | Owner | Notes |
|------|------|--------------------|-------|-------|
| TBD | TBD | TBD | TBD | TBD |
