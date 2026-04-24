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
| TP-001 | Confirm launch tenant list | In Progress | `docs/finance_test_report.md`, `sms-backend/clients/management/commands/seed_platform_data.py`, `sms-backend/clients/management/commands/seed_olom_tenant.py`, `sms-backend/parent_portal/tests.py`, `sms-backend/start.sh` | Repo-backed launch list is now narrowed to `demo_school` for local validation and `olom` for the runtime production tenant; `demo_school_smoke_test` remains excluded as smoke-test-only coverage | Environment labels are now explicit; owner and credential confirmation still belongs to TP-002 |
| TP-002 | Confirm access and credentials ownership | In Progress | `docs/payments_launch_runbook.md`, `QUICKSTART.md`, `sms-backend/config/settings.py`, `.replit` | Provisional functional owners are now mapped for database access, demo-tenant bootstrap, tenant M-Pesa settings, callback host control, and bank statement sourcing, but no human owner register is present in the repo | Human names are still missing for production Daraja credentials, callback host control, and real bank statement samples |
| TP-003 | Freeze launch-candidate baseline | Complete | `PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md` | Baseline frozen at commit `e523470ebbf6d03d8ba4f2cced12d31dddd3edef` on `main` | Workspace note captured above |
| TP-004 | Create evidence tracker | Complete | `PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md` | Central validation tracker created | Use this file to append results and links |
| TP-101 | Run readiness endpoint per tenant | In Progress | `demo_school` local preflight via `FinanceLaunchReadinessView` on `test_sms_school_db` | `ready: false`; remaining blocking issues are Stripe-only and are currently outside the Kenya launch scope | Local test tenant uses HTTPS `demo.localhost`; `mpesa.callback_source: tenant_settings`; M-Pesa tenant config now passes local readiness |
| TP-102 | Defer Stripe connection validation for current Kenya launch | Deferred | April 20, 2026 scope decision recorded in this tracker and `PAYMENT_SYSTEMS_TASK_PLAN.md` | Stripe validation is parked for the current Kenya rollout | Keep repo/local Stripe findings for later if Stripe is reintroduced |
| TP-103 | Validate M-Pesa test connection | In Progress | `demo_school` local preflight via `MpesaTestConnectionView` on `test_sms_school_db` | HTTP 200: connected to Daraja sandbox and obtained OAuth token successfully | Consumer key/secret were applied locally to `demo_school` without storing raw values in this tracker; final launch tenants still need replay once confirmed |
| TP-104 | Validate public callback and webhook URLs | In Progress | `demo_school` local preflight via `MpesaCallbackUrlView` and readiness on `test_sms_school_db` | Callback URL resolves to `https://demo.localhost/api/finance/mpesa/callback/` with `source: tenant_settings` | Local callback proof is captured; external reachability still needs staging evidence |
| TP-105 | Resolve tenant config gaps | In Progress | `demo_school` local readiness, callback, and portal simulations on `test_sms_school_db` | In-scope local gaps are largely closed for the Kenya rollout simulation | External callback proof and tenant-by-tenant confirmation still remain before calling this done |
| TP-106 | Parent portal staging smoke test | In Progress | `demo_school` local dry-run via `ParentFinancePayView` on `test_sms_school_db`; `parent_portal.tests.DemoSchoolPortalSmokeTests` | Bank transfer returned HTTP `201` with manual reference; M-Pesa returned HTTP `201` with checkout request ID using mocked STK push; targeted portal smoke tests passed and were re-covered by the April 23, 2026 39-test DB-backed rerun | Local portal behavior is proven; staging execution with live evidence still remains |
| TP-107 | Student portal staging smoke test | In Progress | `demo_school` local dry-run via `StudentFinancePayView` on `test_sms_school_db`; `parent_portal.tests.DemoSchoolPortalSmokeTests` | Bank transfer returned HTTP `201` with manual reference; M-Pesa returned HTTP `201` with checkout request ID using mocked STK push; targeted portal smoke tests passed and were re-covered by the April 23, 2026 39-test DB-backed rerun | Local portal behavior is proven; staging execution with live evidence still remains |
| TP-108 | Validate Stripe settlement end to end if Stripe is reintroduced later | Deferred | April 20, 2026 scope decision recorded in this tracker and `PAYMENT_SYSTEMS_TASK_PLAN.md` | Stripe settlement proof is not required for the current Kenya rollout | Reopen only if Stripe returns to launch scope |
| TP-109 | M-Pesa end-to-end staging settlement | In Progress | `demo_school` local simulated settlement via `ParentFinancePayView` + `MpesaStkCallbackView` on `test_sms_school_db`; `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests` | Initiation returned HTTP `201`; callback returned HTTP `200`; duplicate callback remained safe; transaction moved to `SUCCEEDED`; payment was created and invoice balance updated; targeted M-Pesa callback tests passed and were re-covered by the April 23, 2026 39-test DB-backed rerun | Uses a synthetic callback payload against the real callback endpoint; live staging receipt/callback proof still required |
| TP-110 | Collect real bank statement samples | Blocked | Workspace search across `docs`, `attached_assets`, and `sms-backend` on April 23, 2026 | No real bank statement CSV/XLS/XLSX sample was found in the normal repo working folders; only reconciliation code paths and runbook references are present | External sample handoff is still required before TP-111 and TP-112 can proceed |
| TP-111 | Import real statement file | Blocked | `demo_school` local synthetic CSV simulation via `BankStatementLineViewSet.import_csv` on `test_sms_school_db`; `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests` | Synthetic CSV import returned HTTP `201` and created two bank lines successfully; targeted CSV import behavior passed and was re-covered by the April 23, 2026 39-test DB-backed rerun | Real bank statement sample is still required before this task can complete |
| TP-112 | Validate reconciliation outcomes | Blocked | `demo_school` local synthetic CSV simulation via bank-line actions on `test_sms_school_db`; `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests` | One line auto-matched, correction via `unmatch` was exercised, forced/manual match via `PATCH` was verified, the line was re-matched and cleared, one line remained `UNMATCHED`, ambiguous-match protection test passed, manual match guardrails rejected direct status forcing, and the path was re-covered by the April 23, 2026 39-test DB-backed rerun | Mechanics are proven locally, but acceptance still requires a real bank statement sample |
| TP-113 | Exercise failed-event inspection | In Progress | `demo_school` local simulated failed callback via `PaymentGatewayWebhookEventViewSet.list` on `test_sms_school_db`; `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests` | Failed M-Pesa callback event appeared in `/api/finance/gateway/events/?provider=mpesa&processed=false`; targeted failed-event path passed and was re-covered by the April 23, 2026 39-test DB-backed rerun | Local operator path is proven; finance/support still need the staging walkthrough |
| TP-114 | Exercise manual reprocess | In Progress | `demo_school` local simulated failed callback via `PaymentGatewayWebhookEventViewSet.reprocess` on `test_sms_school_db`; `school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests` | Reprocess returned HTTP `200`, cleared the event error, and created the missing payment after the gateway transaction was added; targeted reprocess behavior passed and was re-covered by the April 23, 2026 39-test DB-backed rerun | Local operator path is proven; staging drill still remains |
| TP-115 | Run support / bursar walkthrough | Pending | TBD | TBD | Signoff note or annotated runbook |
| TP-116 | Produce launch go/no-go summary | Pending | TBD | TBD | Final decision note |

---

## Tenant And Owner Register

Fill this in before staging execution begins.

| Tenant | Environment | Owner | Optional Stripe Owner | M-Pesa Owner | Bank Sample Owner | Notes |
|--------|-------------|-------|--------------|--------------|-------------------|-------|
| demo_school | Local validation tenant | Platform Admin (provisional) | Platform Admin (deferred for current Kenya scope) | Finance Admin / Bursar (tenant credentials) + Platform Admin (callback host) | Finance Admin / Bursar | Chosen for local task execution; seeded into `test_sms_school_db`; readiness snapshot captured against `https://demo.localhost` |
| olom | Production runtime tenant | Platform Admin (provisional) | Platform Admin (deferred unless Stripe returns to scope) | Finance Admin / Bursar (tenant credentials) + Platform Admin (callback host) | Finance Admin / Bursar | Explicitly maintained by `seed_olom_tenant`; production domain is `olom.rynatyschool.app`; startup bootstrap ensures the tenant/domain exist |
| demo_school_smoke_test | Test-only smoke tenant | N/A | N/A | N/A | N/A | Created in `sms-backend/parent_portal/tests.py`; useful for smoke coverage reference, not a launch tenant |

---

## Local Preflight Notes

### TP-001 repo-backed tenant confirmation

The current repo identifies these tenant roles for launch validation:

- `demo_school` is the local validation tenant used by the finance end-to-end report, portal smoke coverage, and platform demo seed data.
- `olom` is the explicit runtime production tenant maintained by `seed_olom_tenant` with production domain `olom.rynatyschool.app`.
- `demo_school_smoke_test` is only a smoke-test fixture and is excluded from the launch list.

Additional caution:

- a live tenant-table check against the local Django database was attempted on April 23, 2026
- that check failed because the local PostgreSQL credentials for `postgres@localhost:5432` were not available in this workspace context
- until TP-002 is closed, treat the list above as repo-backed confirmation rather than environment-owner confirmation

### Role UI verification snapshot

The current compiled frontend still exposes the payment interfaces required by the main launch users:

- Super admin: `PlatformLayout-CNHzKJMQ.js`, `PlatformBillingPage-CEcBPZ52.js`, and `PlatformRevenueAnalyticsPage-BdFivJgi.js` expose billing navigation, tenant payment review actions, plan and subscription flows, and revenue analytics.
- Finance admin: `FinancePaymentsPage-Dwws6qtb.js` and `FinancePaymentFormPage-Dh2R-Fpu.js` expose payment history, receipt access, reversal handling, student lookup, manual payment capture, and hosted Stripe checkout launch.
- Parent and student users: `ParentPortalFinancePage-C4iG-P9o.js` and `StudentPortalFeesPage-LL9vjGLP.js` expose M-Pesa, bank-transfer, Stripe, receipt, and payment-history flows.
- Supporting operator flow: `ApprovalsHubPage-B_1PnNAs.js` still parses cleanly in the current build.

Verification performed on April 23, 2026:

- `node --check sms-backend/frontend_build/assets/PlatformBillingPage-CEcBPZ52.js`
- `node --check sms-backend/frontend_build/assets/PlatformLayout-CNHzKJMQ.js`
- `node --check sms-backend/frontend_build/assets/PlatformRevenueAnalyticsPage-BdFivJgi.js`
- `node --check sms-backend/frontend_build/assets/FinancePaymentsPage-Dwws6qtb.js`
- `node --check sms-backend/frontend_build/assets/FinancePaymentFormPage-Dh2R-Fpu.js`
- `node --check sms-backend/frontend_build/assets/ParentPortalFinancePage-C4iG-P9o.js`
- `node --check sms-backend/frontend_build/assets/StudentPortalFeesPage-LL9vjGLP.js`
- `node --check sms-backend/frontend_build/assets/ApprovalsHubPage-B_1PnNAs.js`
- `node --check sms-backend/frontend_build/assets/AppShell-51i8-bQf.js`

### April 23 DB-backed regression replay

The payment verification cutoff was resumed against the temp PostgreSQL cluster at `artifacts/temp_pg_mpesa_ui_run2` on `localhost:55432`, using the repo venv and the preserved `test_sms_school_db` database.

Command shape:

- `manage.py test clients.tests.PlatformTenantBillingLifecycleTests parent_portal.tests.DemoSchoolPortalSmokeTests school.test_finance_phase4.FinancePhase4WebhookAndReconciliationTests --keepdb --noinput`

Result summary:

- 39 tests ran in 398.092 seconds
- status: `OK`
- Django reported `System check identified no issues (0 silenced).`
- the existing test database for alias `default` was preserved

Coverage proven again in this DB-backed rerun:

- super-admin tenant billing lifecycle actions, callback settlement, idempotency, and expiry suspension
- parent and student portal payment, invoice, and receipt flows
- M-Pesa callback settlement, bank-line import/match paths, failed-event inspection, and manual reprocess

Execution note:

- the workspace venv had a broken `pkg_resources` namespace for `rest_framework_simplejwt`, so a test-only shim was injected through `PYTHONPATH` from `sms-backend/artifacts/test_shims/pkg_resources.py` for this verification run only

### TP-002 technical ownership inputs

The repo does identify where launch-critical configuration is expected to come from:

- database access is driven by `DATABASE_URL` or the `POSTGRES_*` environment variables in `config.settings`
- the shared demo bootstrap currently pins `DEMO_SCHEMA_NAME=demo_school` and `DEMO_TENANT_DOMAIN=demo.localhost` in `.replit`
- launch operations expect tenant-level M-Pesa credentials to be stored in `TenantSettings.integrations.mpesa`
- the launch runbook assigns the work operationally to finance admins, bursars, platform admins, and support staff, but it does not name specific humans

Provisional functional-owner mapping for launch work:

- platform admin owns runtime tenant bootstrap, public callback host correction, and environment-level database access
- finance admin or bursar owns tenant-side payment configuration checks and the real bank statement sample needed for reconciliation validation
- support staff own operator recovery familiarity and staged walkthrough coverage, but not payment credentials
- Stripe remains deferred for the current Kenya launch scope, so its owner stays platform-admin-only unless the scope reopens

Still unresolved:

- the specific human who owns production Daraja credentials for `olom`
- the specific human who controls the final public callback host / DNS path in staging or production
- the specific human who will provide the real bank statement sample required by `TP-110` through `TP-112`

### TP-110 workspace sample check

On April 23, 2026, a targeted workspace search was run across `docs`, `attached_assets`, and `sms-backend` for bank statement and spreadsheet files.

Result:

- no real bank statement sample file was found in the normal repo working folders
- the repo contains reconciliation endpoints, tests, and runbook instructions, but not the staging bank file needed for acceptance

Implication:

- `TP-110` is externally blocked on sample delivery rather than internally blocked on implementation

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
