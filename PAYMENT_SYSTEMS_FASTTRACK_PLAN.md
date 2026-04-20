# Payment Systems Fast-Track Build Plan

## Goal

Finish the payment build in the shortest realistic time by:

1. Using what already exists in the repo
2. Fixing the true production gaps first
3. Delaying non-critical features that add time without unlocking revenue

This plan is based on:

- `PRO_LEVEL_DEVELOPER_SKILLS.md`
- `PAYMENT_SYSTEMS_AUDIT.md`
- live repo inspection in `sms-backend` and `artifacts/rynaty-space`

---

## What The Audit Gets Right

- Stripe is still effectively unbuilt
- Bank reconciliation is only basic and needs automation
- The frontend payment experience is incomplete
- Security hardening is still needed around webhooks and payment endpoints

---

## Where The Audit Is Outdated

Some of the highest-risk claims in the audit no longer match the codebase:

- M-Pesa callback processing is not just logging. `MpesaStkCallbackView` already updates the gateway transaction, creates a payment, and attempts allocation.
- Bank reconciliation is not fully missing. `BankStatementLineViewSet` already exposes `auto-match`, and `FinanceService.reconcile_bank_line()` already performs basic exact-reference matching.
- Platform integrations listing already exists through `PlatformIntegrationViewSet`.
- Receipt endpoints already exist for finance and parent portal flows.
- Parent portal already supports non-M-Pesa payment initiation records, even though Stripe itself is not implemented.

Conclusion:

Do not treat this as a greenfield build. Treat it as:

- harden existing M-Pesa flow
- complete Stripe
- expand bank reconciliation
- add only the minimum UI needed to operate the system

---

## Shortest-Path Scope

### Build Now

1. M-Pesa production hardening
2. Stripe end-to-end MVP
3. Bank CSV import plus better matching
4. Finance operations screens for reconciliation and payment status
5. Security basics required for safe launch

### Defer

1. Stripe Connect / multi-account orchestration
2. Recurring payments
3. Full bank API integrations
4. OCR for cheques
5. Advanced fraud engine upgrades
6. Rich dashboards and analytics polish
7. Complex installment-plan workflows
8. Full PCI/compliance program work beyond launch blockers

If speed is the real priority, these deferred items should not enter the first build.

---

## Recommended Delivery Strategy

### Track 1: Revenue-Critical Backend

Own first because it unlocks actual payment completion.

#### Phase 1: Stabilize Existing M-Pesa Flow

Target: 2-3 days

Deliverables:

- enforce idempotent callback processing
- mark webhook events as processed or failed
- add manual reprocess path for failed callbacks
- add tests for duplicate callbacks and replay safety
- add clear observability for payment lifecycle states

Primary areas:

- `sms-backend/school/views.py`
- `sms-backend/school/services.py`
- `sms-backend/school/models.py`
- `sms-backend/finance/presentation/*`

Acceptance:

- repeated M-Pesa callback does not create duplicate payments
- every callback ends in a visible processing state
- failed callback can be retried safely

#### Phase 2: Stripe MVP

Target: 4-5 days

Build the simplest viable Stripe flow:

- hosted checkout or payment intent flow
- create gateway transaction before redirect
- handle webhook confirmation
- create payment and allocation on success
- handle failed and expired sessions

Do not build now:

- saved cards
- subscriptions
- wallet reuse
- advanced refund flows

Primary areas:

- `sms-backend/finance`
- `sms-backend/school/views.py` or finance presentation layer
- settings/env wiring
- `artifacts/rynaty-space/src`

Acceptance:

- user can start Stripe payment
- Stripe success webhook creates payment
- invoice balance updates correctly
- duplicate webhook is safe

#### Phase 3: Bank Import + Matching

Target: 3-4 days

Build:

- CSV upload endpoint
- parse into `BankStatementLine`
- exact match by reference
- fallback match by amount plus date window
- manual confirm / clear workflow

Do not build now:

- direct bank API sync
- international payments
- cheque OCR

Acceptance:

- finance user can upload statement
- unmatched items are visible
- likely matches are suggested
- cleared lines become auditable

---

### Track 2: Minimal UI To Operate The System

Target: 3-4 days, can overlap backend work

Build only the screens required to make the flows usable:

1. Payment method selector
2. Stripe checkout entry point
3. Bank transfer instructions screen
4. Reconciliation queue for bursar
5. Webhook/payment event status view

Do not start with:

- charts
- analytics dashboards
- polished historical reporting widgets
- advanced portal customization

Primary area:

- `artifacts/rynaty-space/src`

Acceptance:

- student or parent can choose payment method
- bursar can see pending/unmatched payment states
- finance team can resolve issues without DB access

---

### Track 3: Launch Safety

Target: 2 days

Must-have hardening:

1. webhook signature verification for Stripe
2. strict token/shared-secret validation where applicable
3. rate limiting on payment initiation endpoints
4. idempotency keys for external-facing payment creation
5. structured audit logging for payment state changes

Nice-to-have but not blocking:

1. credential vault migration
2. callback IP filtering
3. full PCI tracking workflow

---

## Fastest Realistic Timeline

### Option A: 1 Strong Developer

- Week 1: M-Pesa hardening + Stripe backend
- Week 2: Stripe frontend + bank CSV import + basic reconciliation UI
- Week 3: testing, hardening, launch fixes

Total: about 3 weeks

### Option B: 2 Developers

- Developer 1: backend payments and webhooks
- Developer 2: frontend + reconciliation screens

Total: about 8-10 working days

### Option C: 3 Developers

- Developer 1: M-Pesa hardening + shared payment service
- Developer 2: Stripe integration end-to-end
- Developer 3: bank import/reconciliation + UI

Total: about 5-7 working days for MVP, plus 3-5 days for polish

If the goal is shortest calendar time, Option B is the best tradeoff. Option C is faster but adds coordination overhead.

---

## Recommended Build Order

1. Harden M-Pesa callback processing first
2. Introduce a shared payment finalization service used by M-Pesa and Stripe
3. Build Stripe on top of that shared flow
4. Add bank statement import and better matching
5. Add minimal operator UI for reconciliation and visibility
6. Finish with launch hardening and test coverage

This order is fastest because it avoids implementing payment settlement logic twice.

---

## Architecture Decision For Speed

Do this:

- centralize payment finalization in one service
- gateway-specific handlers should only parse and verify provider payloads
- one shared flow should create or update:
  - `PaymentGatewayTransaction`
  - `Payment`
  - allocation to invoice
  - audit/event status

Do not do this:

- separate full business logic for M-Pesa, Stripe, and bank flows

That duplication will slow delivery and create inconsistent accounting behavior.

---

## Minimum Definition Of Done

The build is complete enough to launch when all of these are true:

1. M-Pesa payment settles cleanly and idempotently
2. Stripe payment settles cleanly and idempotently
3. Bank statement CSV can be imported and matched
4. Finance team can see unmatched items and resolve them
5. Receipt retrieval works for all successful payment methods
6. Payment attempts and webhook events are traceable in the UI or admin endpoints
7. Core tests cover success, duplicate webhook, failed payment, and partial allocation cases

---

## What To Avoid If You Want Speed

1. Do not rebuild M-Pesa from scratch
2. Do not start with dashboard polish
3. Do not start with platform-wide Stripe Connect complexity
4. Do not mix launch blockers with “nice to have” finance automation
5. Do not build recurring payments in the first pass
6. Do not introduce a large architectural rewrite before shipping the payment core

---

## Immediate Next Actions

### Day 1

1. Confirm current M-Pesa callback behavior with tests
2. Create a single shared payment settlement service
3. Define Stripe transaction model fields and webhook event mapping

### Day 2

1. Implement Stripe checkout creation
2. Implement Stripe webhook verification and settlement
3. Add payment method selector in frontend

### Day 3

1. Add bank CSV import
2. Add amount/date fallback matching
3. Add reconciliation list screen

### Day 4-5

1. Add retry/reprocess tooling
2. Add rate limiting and idempotency protection
3. Run end-to-end payment test matrix

---

## Final Recommendation

If we optimize for shortest completion time, the winning move is:

- treat M-Pesa as mostly existing
- use it to extract a shared settlement core
- plug Stripe into that core
- keep bank scope to CSV import plus matching
- ship only the UI needed for operations

That gives you a real, launchable payments system much faster than trying to implement every item in the audit.

---

## Where This Plan Picks Up Now

Since this draft, the repo has moved forward on several of the "build next" items. The fastest path is no longer "finish Stripe portal entry points" or "implement bank tooling from scratch." The fastest path now is:

1. validate real tenant credentials and public callback/webhook reachability
2. exercise the bank reconciliation and gateway-event recovery workflows in staging
3. run the payment regression suites and capture evidence
4. close only the hardening items that still look truly launch-blocking

---

## What Is Already Landed In The Repo

The following is already present and should be treated as existing delivery, not future scope:

- Stripe checkout session creation exists in `sms-backend/school/views.py` via `StripeCheckoutSessionView`
- generic finance gateway webhook handling exists in `sms-backend/school/views.py` via `FinanceGatewayWebhookView`
- Stripe signature verification already exists
- shared Stripe webhook settlement exists in `sms-backend/school/services.py`
- M-Pesa callback idempotency and reprocess flows already exist
- parent portal payment initiation now supports Stripe, M-Pesa, and bank transfer in `sms-backend/parent_portal/views.py`
- student portal payment initiation now supports Stripe, M-Pesa, and bank transfer in `sms-backend/parent_portal/student_portal_views.py`
- bank statement CSV import/export exists in `sms-backend/school/views.py`
- bank auto-match logic already includes exact reference plus amount/date-window fallback in `sms-backend/school/services.py`
- launch-readiness, Stripe test-connection, M-Pesa test-connection, callback-url, and gateway-event endpoints already exist
- `docs/payments_launch_runbook.md` already documents readiness, validation, recovery, and rollback steps
- finance tests already cover Stripe checkout creation, webhook completion, duplicate safety, and reprocess in `sms-backend/school/test_finance_phase4.py`
- finance activation-prep coverage already exists in `sms-backend/school/test_phase6_finance_collection_ops_activation_prep.py`

This means the original plan should now be read as a first-pass build plan plus a handoff document, not as a fully current implementation gap list.

---

## What Is Still Actually Missing

### 1. Launch Validation With Real Config

The backend flow is materially more complete than the original plan assumed, but it still needs environment validation:

- Stripe secret key
- Stripe webhook secret
- public webhook URL
- M-Pesa callback URL
- tenant-level payment settings

This is not a missing-code problem. It is an environment and go-live validation problem.

### 2. Real Bank Statement Validation

Bank CSV import and auto-match exist, but they still need proof against real statement formats:

- import a real bank statement CSV in staging
- verify at least one auto-match
- verify unmatched lines appear correctly
- verify clear / unmatch / ignore actions with realistic data

### 3. Staging Operator Exercise

The code supports operator recovery, but the workflow still needs to be exercised in staging:

- list failed gateway events
- reprocess one recoverable event
- confirm support / finance staff can follow the runbook without DB access

### 4. Remaining Hardening Gaps

The repo now has much better payment hardening than before, but a few items still look unfinished or not obvious:

- request throttling / rate limiting on payment initiation endpoints is not clearly visible in the current payment paths
- external idempotency-key handling on payment initiation endpoints is not clearly exposed
- provider-side Stripe refund automation is not clearly established from this payment audit

These are no longer "build payments from scratch" issues, but they remain real hardening and product-completeness gaps.

### 5. Deferred Later-Phase Features

The following still appear intentionally out of scope or not yet implemented:

- direct bank API integrations
- cheque OCR
- recurring card payments
- advanced fraud controls beyond the current fixes
- richer reconciliation heuristics beyond exact reference and amount/date fallback

These should be tracked as later-phase work, not confused with current launch blockers.

---

## Revised Shortest Path From Here

### Phase 4: Validate And Exercise In Staging

Target: 2 days

Build:

- run `GET /api/finance/launch-readiness/` for each launch tenant
- validate Stripe and M-Pesa test-connection checks with real tenant credentials
- confirm the public Stripe webhook URL and M-Pesa callback URL are correct and HTTPS
- import one real bank statement sample in staging
- exercise clear / unmatch / ignore actions with realistic reconciliation data
- reprocess one recoverable gateway event through the operator flow

Primary areas:

- `sms-backend/school/views.py`
- `sms-backend/school/services.py`
- `docs/payments_launch_runbook.md`
- operator finance settings and reconciliation screens

Acceptance:

- readiness reports the right blocking issues and next actions for the tenant
- Stripe and M-Pesa validation checks succeed in the target environment
- one real bank CSV import produces at least one auto-match and one unmatched line
- finance/support can reprocess a recoverable event without DB access

### Phase 5: Close Selective Launch Gaps

Target: 1-2 days

Build:

- run the payment regression suites and capture the results
- document tenant-by-tenant launch evidence and operator sign-off
- decide whether rate limiting and external idempotency support must land before go-live
- keep post-launch items separated from true launch blockers
- finalize launch, rollback, and support notes

Primary areas:

- `sms-backend/school/test_finance_phase4.py`
- `sms-backend/school/test_phase6_finance_collection_ops_activation_prep.py`
- docs and ops notes

Acceptance:

- regression suites are green
- launch evidence exists per tenant
- open items are clearly classified as launch blockers or deferred
- finance/support can follow the current runbook and rollback notes

---

## Updated Build Order

1. Validate launch-readiness and tenant payment credentials
2. Confirm public Stripe webhook and M-Pesa callback URLs in staging
3. Validate bank CSV import and reconciliation against a real statement sample
4. Exercise failed-event listing and reprocess workflow
5. Run payment regression tests and capture results
6. Close only the hardening items that remain true launch blockers

---

## Updated Definition Of Done

The payment system is now launch-ready when all of these are true:

1. student and parent portals can initiate Stripe, M-Pesa, and bank-transfer flows
2. Stripe and M-Pesa settlement paths remain idempotent and recoverable
3. `GET /api/finance/launch-readiness/` reports ready for the launch tenants
4. Stripe and M-Pesa test-connection checks succeed with real tenant credentials
5. public webhook and callback URLs are reachable over HTTPS
6. one real bank CSV sample has been imported and validated in staging
7. finance staff can inspect and reprocess recoverable gateway events without database access
8. launch configuration and operator runbook steps are documented tenant-by-tenant
9. regression tests for payment initiation, settlement, reprocess, and activation prep are green

---

## Execution Checklist

- [x] wire Stripe initiation into student portal finance flow
- [x] wire Stripe initiation into parent portal finance flow
- [x] confirm shared Stripe checkout + webhook settlement exists in backend
- [x] confirm readiness, test-connection, callback-url, and gateway-event endpoints exist
- [x] write a short launch/runbook note for support and bursar users
- [x] run `school.test_finance_phase4`
- [x] run `school.test_phase6_finance_collection_ops_activation_prep`
- [ ] confirm `integrations.stripe` contains secret and webhook secret for each launch tenant
- [ ] confirm `/api/finance/gateway/webhooks/stripe/` is reachable from Stripe in staging
- [ ] confirm `/api/finance/mpesa/callback/` is reachable from Safaricom in staging
- [ ] validate bank CSV import against real statement samples
- [ ] exercise manual reprocess flow for one M-Pesa and one Stripe failure case in staging
- [ ] classify rate limiting / external idempotency support as launch-blocking or deferred
- [ ] capture tenant-by-tenant launch evidence and sign-off

---

## Repo Caveat To Confirm Early

The workspace clearly contains compiled finance frontend assets in `sms-backend/frontend_build`, but the editable source for those finance and portal screens is not as obvious in this snapshot.

If portal UI changes are required, confirm the editable frontend source location before promising a same-day UI turnaround.

---

## Final Recommendation, Updated

The fastest move now is not another large backend implementation phase.

The fastest move is:

- validate live tenant config and public callback/webhook reachability
- exercise bank reconciliation and gateway-event recovery in staging
- trust and reuse the shared settlement logic that already exists
- ship with the current runbook and only the remaining hardening fixes that truly block launch

Most of the backend work the original fast-track plan called for is already present in the repo. The remaining work is mainly exposure, validation, and launch discipline.
