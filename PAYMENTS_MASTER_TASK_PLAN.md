# Payments Master Task Plan
## School Fees + Super Tenant Billing

**Date:** April 22, 2026  
**Source:** `PAYMENTS_MASTER_AUDIT.md`, the attached PDFs, the two diagrams, and the current compiled build  
**Purpose:** Turn the payment audit into an approval-ready implementation plan before any code changes begin

---

## Planning Goal

Deliver one coherent payments system that covers:

- school fee collection from admin, parent, and student flows
- receipt generation and notifications
- tenant subscription billing for the platform owner
- automatic suspension and reactivation of overdue tenants
- revenue analytics for the super admin dashboard

without rebuilding the UI shells that already work.

---

## Planning Principles

1. Extend the existing finance and super-admin screens instead of rebuilding them.
2. Use the existing school payment ledger for student fees and the existing subscription payment ledger for tenant billing.
3. Treat M-Pesa as the primary live rail where the product spec expects it.
4. Keep bank transfer and manual confirmation as fallback paths where the current build already supports them.
5. Make payment state changes idempotent and audit logged.
6. Use one receipt contract across JSON, PDF, and SMS.
7. Require evidence for every completed task.

---

## Current Status Snapshot

| Area | Status | Notes |
|------|--------|-------|
| School payment ledger | Complete | `school.Payment` and vote-head allocation already exist |
| Finance admin payment UI | Complete | Capture card now has admission lookup, receipt handoff, and SMS target preview; list/table normalization now matches the live receipt contract |
| Parent mobile payment UI | Complete | M-Pesa-first pay-now flows and receipt links are live |
| Student payment UI | Complete | M-Pesa-first pay-now flows, receipt links, and the student receipt endpoint are live |
| Receipt contract | Complete | Shared receipt payload now powers JSON, PDF, and text output for the school flow |
| Super admin shell | Complete | Tenants, billing, revenue analytics, and impersonation pages already exist |
| Tenant payment operations | Complete | Dedicated tenant-payments queue with approve/reject/retry actions now lives in `PlatformBillingPage` |
| Subscription lifecycle automation | Complete | Expiry cron and payment reactivation now share one platform-owned lifecycle |
| Platform M-Pesa tenant billing | Complete | Paybill settings, invoice capture, tenant-payment review, and callback hardening are live |
| Revenue analytics | Complete | MRR, ARR, churn, trend charts, projections, and tenant-risk signals now exist in the compiled build |
| Regression coverage | Complete | School and tenant regression suites, compiled checks, and smoke coverage now back the rollout decision |

---

## Schema Alignment Decisions

| Requested Concept | Plan Decision | Notes |
|-------------------|---------------|-------|
| `payments` table from the user spec | Map to the existing school payment model first | Do not create a duplicate school ledger unless a migration-backed gap remains |
| `student_id` | Keep as the school payment FK | Existing model already matches the intended relationship |
| `transaction_code` | Standardize on existing reference/gateway fields | Keep transaction codes searchable and idempotent |
| `vote_head` | Normalize through vote-head allocations | Do not collapse allocations into a single text field |
| `receipt_no` | Standardize on the existing receipt number field | Receipt numbering should be deterministic and printable |
| tenant subscription payments | Use `clients.SubscriptionPayment` | Keep tenant billing separate from student fee collection |
| receipt JSON payload | Standardize one response shape | JSON and PDF should reflect the same payment data |

---

## Scope Boundaries

### In Scope

- school fee recording, settlement, receipt generation, and SMS notification
- parent and student mobile payment flows
- admin payment card cleanup and dynamic fields
- tenant billing review, invoice generation, payment verification, and suspension/reactivation
- super admin revenue analytics and operator visibility
- audit logging, callback verification, idempotency, and regression tests

### Out Of Scope For This Plan

- rebuilding the working React shells from scratch
- introducing a new standalone payments database when the existing ledgers already fit
- Flutterwave expansion unless the scope is reopened later
- bank-direct integrations beyond the fallback and reconciliation flows already present

---

## Phase Plan

## Phase 0: Scope and Data Contract Freeze
**Target:** 0.5-1 day  
**Goal:** Lock the model and receipt contract before code changes begin.

### Tasks

- `PAY-001` Freeze the build baseline and evidence locations.
  Deliverable: list of current build assets, backend modules, and evidence folders
  Acceptance: the team agrees which compiled pages and backend modules are in scope

- `PAY-002` Map the requested `payments` schema to the existing school payment ledger.
  Deliverable: schema mapping note and minimal migration decision
  Acceptance: we agree not to add a duplicate school payments table

- `PAY-003` Define the receipt contract.
  Deliverable: one JSON receipt shape plus PDF fields for the school flow
  Acceptance: `receipt_no`, `student`, `amount`, `method`, and `date` are consistent everywhere

- `PAY-004` Confirm payment rails by track.
  Deliverable: decision note for school fees and tenant billing
  Acceptance: school payments, tenant billing, and fallback rails are all explicitly documented

### Exit Criteria

- schema mapping is signed off
- receipt contract is signed off
- rail decisions are explicit
- evidence locations exist

---

## Phase 1: School Payment Ledger And Admin Capture
**Target:** 2-4 days  
**Goal:** Make the school payment record flow match the requested admin card and receipt design.

### Tasks

- `PAY-101` Refresh the finance admin payment card.
  Deliverable: one payment form that supports admission lookup, student autofill, amount, method, dynamic fields, record, receipt, and SMS
  Acceptance: bursar can record a payment without hunting through separate screens
  Status: Complete

- `PAY-102` Standardize payment detail and payment list fields.
  Deliverable: transaction code, vote head, receipt number, status, and created date surfaced in one consistent table
  Acceptance: payment rows are readable and searchable from the finance UI
  Status: Complete

- `PAY-103` Tighten allocation, reversal, and duplicate protection rules.
  Deliverable: clear backend rules for allocation to vote heads, reversal, and callback dedupe
  Acceptance: one payment cannot be created twice from retry or callback replay
  Status: complete

- `PAY-104` Standardize receipt generation.
  Deliverable: JSON receipt and PDF receipt that share one data source
  Acceptance: the receipt content matches the payment record exactly
  Status: complete

- `PAY-105` Add SMS notification on successful payment.
  Deliverable: SMS trigger for the school payment completion path
  Acceptance: payment completion produces the expected notification payload
  Status: complete

### Implemented In This Slice

- shared payment receipt payload added in `sms-backend/school/payment_receipts.py`
- school and finance payment serializers now expose `receipt_no`, `transaction_code`, `status`, `created_at`, and receipt URLs
- `GET /api/finance/payments/{id}/receipt/?format=json` now returns the canonical receipt payload
- the receipt PDF now reads from the same payload as the JSON and text responses
- `school.test_phase6_finance_receivables_activation_prep` now covers the JSON receipt contract alongside PDF/text parity
- the finance admin payment card now supports admission-number lookup, student autofill, and post-save receipt/SMS actions in `FinancePaymentFormPage-Dh2R-Fpu.js`
- the finance payment list now surfaces receipt number, transaction code, vote head summary, status, and created date in `FinancePaymentsPage-Dwws6qtb.js`
- successful payment recording now creates an SMS audit trail via `school.signals.notify_on_payment_recorded`
- historical payment imports now suppress notification dispatch so only live payment captures trigger SMS side effects
- vote-head allocation create now upserts the payment/vote-head pair so duplicate replays update the existing allocation instead of creating a second row
- payment and allocation create endpoints now return `200 OK` on replayed duplicates so callback retries stay idempotent
- `school.test_phase6_finance_receivables_activation_prep` now covers the payment SMS audit trail alongside receipt parity

### Exit Criteria

- admin can record and view payments cleanly
- receipt output is standardized
- duplicate callbacks do not duplicate payments
- allocations stay in sync with the ledger

### Implemented In This Slice

- parent portal payment history now exposes receipt links, and the quick pay action defaults to M-Pesa first
- student portal payment history now exposes receipt links and a printable student receipt endpoint
- parent and student payment modals now default to M-Pesa first while keeping Stripe and bank transfer as fallback options
- payment history tables now scroll horizontally on smaller screens instead of trapping content

---

## Phase 2: Parent And Student Mobile Payments
**Target:** 2-4 days  
**Goal:** Make the mobile payment path simple, readable, and safe on small screens.

### Tasks

- `PAY-201` Refine the parent mobile-first fees summary and Pay Now card.
  Deliverable: balance summary, amount, phone, and M-Pesa action clearly visible on mobile
  Acceptance: a parent can understand what is owed and start payment in one view
  Status: Complete

- `PAY-202` Align the student portal payment flow with the same contract.
  Deliverable: same receipt and balance behavior as the parent path
  Acceptance: student and parent see the same payment state once settlement completes
  Status: Complete

- `PAY-203` Keep the bank-transfer fallback path intact.
  Deliverable: manual-confirmation flow remains available where the current build already supports it
  Acceptance: fallback payments still land in the ledger and can be reconciled
  Status: Complete

- `PAY-204` Refresh balances and payment history after settlement.
  Deliverable: post-payment balance update and receipt visibility
  Acceptance: the UI reflects the payment without requiring the user to guess whether it worked
  Status: Complete

### Exit Criteria

- mobile payment paths are clear and usable
- balance and receipt states refresh correctly
- fallback flows remain intact

---

## Phase 3: Super Tenant Billing And Subscription Control
**Target:** 3-5 days  
**Goal:** Give the platform owner one clean tenant-payments lane and one clear subscription lifecycle.

### Tasks

- `PAY-301` Add a dedicated tenant payments operations lane.
  Deliverable: tenant payments page or panel with school, amount, method, transaction code, status, and date
  Acceptance: super admin can review tenant payments without mixing them into tenant profile edits
  Status: complete

- `PAY-302` Add tenant payment review actions.
  Deliverable: `Approve`, `Reject`, `Retry Verification`, and `View Payments`
  Acceptance: each action updates state and writes an audit log
  Status: complete

- `PAY-303` Tie subscription payment confirmation to tenant access.
  Deliverable: confirmed tenant payment extends access and reactivates the school if needed
  Acceptance: a paid tenant moves back to active state automatically
  Status: complete

- `PAY-304` Add automatic expiry and disable logic.
  Deliverable: daily subscription check with lock protection and one clear suspend policy
  Acceptance: overdue tenants are disabled once, not repeatedly, and can be restored safely after payment
  Status: complete

- `PAY-305` Harden platform-owned M-Pesa tenant billing.
  Deliverable: STK push or paybill instruction flow, callback verification, and idempotent settlement
  Acceptance: tenant subscription payments settle safely and do not duplicate on callback replay
  Status: complete

### Implemented In This Slice

- `PlatformBillingPage-CEcBPZ52.js` now exposes a dedicated Tenant Payments queue with `Approve`, `Reject`, `Retry Verification`, and a `View Payments` shortcut.
- invoice payment capture now creates subscription payment queue rows through `/api/platform/subscription-payments/` instead of only updating the old invoice action path.
- tenant payment approvals now reuse the backend settlement and reactivation flow, so a paid tenant moves back to active state from the same review lane.
- the existing expiry cron and subscription reactivation policy already cover the auto-disable/restore lifecycle from the backend side.
- the platform now exposes a public M-Pesa callback endpoint at `/api/platform/subscription-payments/mpesa/callback/` that settles, dedupes, and audit-logs tenant payments.
- focused tenant-billing regression tests now cover success, replay, and amount-mismatch callback behavior.

### Exit Criteria

- tenant payments are visible and operable
- overdue tenants are auto-disabled and reactivated on payment
- paybill callbacks are verified and deduped
- billing actions are fully audited

---

## Phase 4: Revenue Analytics And Operator Visibility
**Target:** 2-4 days  
**Goal:** Make the platform owner dashboard reflect billing reality and forward-looking risk.

### Tasks

- `PAY-401` Extend the revenue cards and charts.
  Deliverable: Total Revenue, Monthly Revenue, Active Subscriptions, Churn Rate, and trend charts
  Acceptance: the dashboard uses real backend data, not placeholder values
  Status: Complete

- `PAY-402` Add projections and plan breakdowns.
  Deliverable: forecast view plus revenue by plan and tenant segment
  Acceptance: the super admin can see where revenue comes from and where it is likely going
  Status: Complete

- `PAY-403` Add churn-risk signals.
  Deliverable: active, overdue, and at-risk tenant signals in analytics or ops views
  Acceptance: the platform can surface schools that need follow-up before churn
  Status: Complete

- `PAY-404` Keep impersonation separate from payment actions.
  Deliverable: debug-only impersonation flow with clear audit and visual warning
  Acceptance: impersonation is impossible to confuse with payment processing
  Status: Complete

### Implemented In This Slice

- `PlatformRevenueAnalyticsPage-BdFivJgi.js` now shows a fifth KPI card for the next-month forecast and a clearer risk-oriented subtitle.
- the analytics backend now returns forecast, plan breakdown, and tenant risk summaries alongside MRR, ARR, churn, and trend data.
- the platform analytics API now exposes month-aligned revenue series and a growth view shape that matches the compiled dashboard.
- focused regression coverage now proves the revenue projection and risk-signaling contract end to end.

### Exit Criteria

- analytics are business-useful
- projections are visible
- risk signals are readable
- impersonation remains safely separated

---

## Phase 5: Tests, Rollout, And Evidence
**Target:** 2-4 days  
**Goal:** Prove the combined payment system is safe enough for production use.

### Tasks

- `PAY-501` Add backend regression tests for school payments.
  Deliverable: tests for payment recording, receipt generation, callback dedupe, reversal, and allocation
  Acceptance: the school ledger cannot regress silently
  Status: Complete

- `PAY-502` Add backend regression tests for tenant billing.
  Deliverable: tests for invoice generation, payment verification, expiry, reactivation, and paybill settlement
  Acceptance: the super-tenant billing lifecycle cannot regress silently
  Status: Complete

- `PAY-503` Add frontend checks for the compiled build.
  Deliverable: syntax checks and route visibility checks for the edited assets
  Acceptance: the existing shells still load correctly after payment changes
  Status: Complete

- `PAY-504` Run a demo-school and tenant dry run.
  Deliverable: one end-to-end school payment scenario and one tenant billing scenario with evidence
  Acceptance: each major flow is proven once in a realistic environment
  Status: Complete

- `PAY-505` Produce the rollout runbook and go/no-go summary.
  Deliverable: support guide plus launch decision note
  Acceptance: support can operate the system and the owner can approve release
  Status: Complete

### Implemented In This Slice

- `docs/payments_launch_runbook.md` now covers both school and tenant launch steps and points to the evidence files.
- `docs/payments_phase5_go_no_go.md` captures the launch decision and the verification results.
- school, tenant, and portal regression suites now pass for the current payments build.
- the compiled finance, portal, billing, analytics, and student bundles now pass syntax checks.

### Exit Criteria

- backend tests pass
- frontend checks pass
- one realistic dry run is captured for both flows
- support has a runbook
- go/no-go is explicit

---

## Priority Order

1. `PAY-001` to `PAY-004`
2. `PAY-101` to `PAY-105`
3. `PAY-201` to `PAY-204`
4. `PAY-301` to `PAY-305`
5. `PAY-401` to `PAY-404`
6. `PAY-501` to `PAY-505`

This keeps schema alignment first, school payments second, tenant billing third, analytics fourth, and rollout last.

---

## Status Legend

- `Complete`: finished with evidence captured
- `In Progress`: active implementation or validation
- `Ready Now`: can start immediately with current context
- `Blocked`: waiting on owner input or real-world evidence
- `Decision Pending`: needs approval before implementation
- `Deferred`: intentionally later-phase work

---

## Evidence Required Per Task

Each completed task should capture at least one of:

- API response capture
- screenshot
- test run output
- receipt PDF or JSON sample
- payment reference
- callback event ID
- audit log entry
- support signoff note

---

## Recommended Owners

| Area | Recommended Owner |
|------|-------------------|
| School payment ledger and receipts | backend engineer + bursar/finance owner |
| Parent and student portal payments | frontend engineer + backend engineer |
| Tenant billing and subscription control | backend engineer + platform admin |
| Revenue analytics | frontend engineer + platform admin |
| Rollout and support | support lead + platform admin |

---

## Definition Of Success

This plan is successful when:

1. the existing school payment and super-admin shells are extended, not rebuilt
2. the requested payment contract is aligned to the existing ledgers
3. school receipts, SMS, and callback settlement are idempotent and auditable
4. tenant payments can be reviewed, verified, and linked to subscription state
5. overdue tenants are disabled automatically and restored after valid payment
6. revenue analytics show real billing health and churn risk
7. support can operate the system using a documented runbook

---

## Immediate Next Step

Proceed with production rollout and support monitoring using the go/no-go note.
