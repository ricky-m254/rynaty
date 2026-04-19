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

Since this draft, the repo has moved forward on several of the "build next" items. The fastest path is no longer "implement Stripe and bank tooling from scratch." The fastest path now is:

1. finish the portal-facing entry points
2. validate the shared settlement paths already in the repo
3. document launch and recovery steps

---

## What Is Already Landed In The Repo

The following is already present and should be treated as existing delivery, not future scope:

- Stripe checkout session creation exists in `sms-backend/school/views.py` via `StripeCheckoutSessionView`
- generic finance gateway webhook handling exists in `sms-backend/school/views.py` via `FinanceGatewayWebhookView`
- Stripe signature verification already exists
- shared Stripe webhook settlement exists in `sms-backend/school/services.py`
- M-Pesa callback idempotency and reprocess flows already exist
- bank statement CSV import/export exists in `sms-backend/school/views.py`
- bank auto-match logic already includes exact reference plus amount/date-window fallback in `sms-backend/school/services.py`
- finance tests already cover Stripe checkout creation, webhook completion, duplicate safety, and reprocess in `sms-backend/school/test_finance_phase4.py`

This means the original plan should now be read as a first-pass build plan plus a handoff document, not as a fully current implementation gap list.

---

## What Is Still Actually Missing

### 1. Student Portal Stripe Path

The student portal still explicitly allows only M-Pesa payment initiation today.

Primary area:

- `sms-backend/parent_portal/student_portal_views.py`

Impact:

- students cannot yet start a real Stripe payment flow from the portal even though Stripe settlement exists downstream

### 2. Parent Portal Online Payment Completion

The parent portal can create non-M-Pesa initiation rows, but non-M-Pesa methods still stop at a placeholder initiation record instead of handing off to Stripe Checkout.

Primary area:

- `sms-backend/parent_portal/views.py`

Impact:

- parents can mark intent for "Online" payment, but that is not the same as a true hosted card checkout flow

### 3. Launch Validation With Real Config

The backend flow is materially more complete than the original plan assumed, but it still needs environment validation:

- Stripe secret key
- Stripe webhook secret
- public webhook URL
- M-Pesa callback URL
- tenant-level payment settings

### 4. Operator Runbook And Real-File Validation

Bank CSV import and auto-match exist, but they still need validation with real statement formats and a clear operating procedure for bursar and finance users.

---

## Revised Shortest Path From Here

### Phase 4: Finish Portal Entry Points

Target: 2-3 days

Build:

- allow `payment_method=stripe` from student and parent payment flows
- route those requests into the existing Stripe checkout session flow
- return checkout session URL and reference metadata to portal clients
- keep the current M-Pesa flow unchanged

Primary areas:

- `sms-backend/parent_portal/student_portal_views.py`
- `sms-backend/parent_portal/views.py`
- any shared request/response serializers used by portal finance endpoints

Acceptance:

- student can select Stripe and receive a hosted checkout URL
- parent can select Stripe and receive a hosted checkout URL
- successful Stripe completion settles through the existing shared webhook path
- duplicate completion remains idempotent

### Phase 5: Validate And Launch

Target: 2 days

Build:

- validate Stripe webhook delivery against the existing endpoint
- validate M-Pesa callback routing in the target environment
- test bank CSV import with real sample statements
- verify manual webhook reprocess works for recoverable failures
- document launch checklist, rollback steps, and support procedure

Primary areas:

- `sms-backend/school/views.py`
- `sms-backend/school/services.py`
- `sms-backend/finance`
- docs and ops notes

Acceptance:

- finance admin can see and reprocess failed webhook events safely
- bursar can import a statement and act on unmatched lines
- launch checklist exists and has been exercised once in staging
- payment credentials and callback/webhook URLs are documented per tenant

---

## Updated Build Order

1. Finish Stripe entry points in student and parent portals
2. Reuse the existing shared settlement/webhook path; do not fork business logic
3. Validate bank CSV import and matching with real statement samples
4. Confirm Stripe and M-Pesa configuration in staging
5. Run payment regression tests and capture results
6. Launch with operator checklist and reprocess procedure

---

## Updated Definition Of Done

The payment system is now launch-ready when all of these are true:

1. student portal can initiate M-Pesa and Stripe flows
2. parent portal can initiate M-Pesa and Stripe flows
3. Stripe webhook completes payment settlement using the existing shared flow
4. duplicate M-Pesa and Stripe callbacks remain safe
5. bank CSV import works with real statement samples
6. finance staff can inspect gateway transactions and webhook events
7. finance staff can reprocess recoverable failed events without database access
8. launch configuration is documented tenant-by-tenant
9. regression tests for payment initiation, settlement, reprocess, and matching are green

---

## Execution Checklist

- [ ] wire Stripe initiation into student portal finance flow
- [ ] wire Stripe initiation into parent portal finance flow
- [ ] confirm `integrations.stripe` contains secret and webhook secret
- [ ] confirm `/api/finance/gateway/webhooks/stripe/` is reachable from Stripe
- [ ] confirm `/api/finance/mpesa/callback/` is reachable from Safaricom
- [ ] validate bank CSV import against real statement samples
- [ ] exercise manual reprocess flow for one M-Pesa and one Stripe failure case
- [ ] run `school.test_finance_phase4`
- [ ] run the relevant finance activation prep tests before launch
- [ ] write a short launch/runbook note for support and bursar users

---

## Repo Caveat To Confirm Early

The workspace clearly contains compiled finance frontend assets in `sms-backend/frontend_build`, but the editable source for those finance and portal screens is not as obvious in this snapshot.

If portal UI changes are required, confirm the editable frontend source location before promising a same-day UI turnaround.

---

## Final Recommendation, Updated

The fastest move now is not another large backend implementation phase.

The fastest move is:

- finish the Stripe handoff in student and parent portals
- trust and reuse the shared settlement logic that already exists
- validate real callbacks, webhooks, and bank files in staging
- ship with a runbook and reprocess procedure

Most of the backend work the original fast-track plan called for is already present in the repo. The remaining work is mainly exposure, validation, and launch discipline.
