# Super Admin Tenant Payments Task Plan
## Execution Plan For Tenant Billing And Revenue Ops

> Note: the combined school + tenant payments source of truth is now `PAYMENTS_MASTER_TASK_PLAN.md`.  
> Keep this file as the super-admin tenant-billing subtrack reference.

**Date:** April 22, 2026  
**Source:** `SUPER_ADMIN_TENANT_PAYMENTS_AUDIT.md` and `attached_assets/SmartCampus_SuperAdmin_Spec_1776271963249.docx`  
**Purpose:** Turn the super-admin billing audit into an approval-ready implementation plan before any code changes begin

---

## Planning Goal

Extend the existing super-admin dashboard so it can:

- manage tenant subscriptions
- process tenant payments
- auto-disable overdue schools
- reactivate tenants when payment is confirmed
- surface revenue analytics for the platform owner

without rebuilding the UI shell that already works.

---

## Planning Principles

1. Keep the current super-admin React shell and extend it.
2. Put platform-owned M-Pesa paybill at the center of tenant billing.
3. Treat expiry, suspension, and reactivation as one lifecycle.
4. Deny-by-default for expired tenants and duplicate payment events.
5. Require evidence for every completed task.
6. Defer Flutterwave unless scope is explicitly reopened.

---

## Current Status Snapshot

| Area | Status | Notes |
|------|--------|-------|
| Super admin shell | Complete | Existing compiled pages already cover tenants, billing, revenue analytics, and impersonation |
| Tenant payment operations | Pending | No dedicated payments queue with approve/reject/retry actions |
| Subscription lifecycle automation | Pending | Expiry/reactivation needs one explicit platform-owned flow |
| Platform M-Pesa paybill intake | Partial | Paybill settings and payment capture exist, but tenant-level billing workflow still needs a hardened path |
| Revenue analytics | Partial | MRR/ARR/churn/LTV exist, but projections and payment-ops context need expansion |
| Audit and support visibility | Partial | Impersonation exists, but payment actions need a clearer operator audit trail |
| Regression coverage | Pending | New tenant-payment and expiry tests still need to be added |

---

## Workstreams

| Workstream | Purpose | Priority | Target Outcome |
|------------|---------|----------|----------------|
| WS1 | Tenant payment operations | Critical | Super admin can review, approve, reject, and recheck tenant payments |
| WS2 | Subscription lifecycle automation | Critical | Overdue tenants are auto-disabled and reactivated on confirmed payment |
| WS3 | M-Pesa tenant billing | Critical | Platform-owned paybill flow records and verifies tenant payments safely |
| WS4 | Revenue analytics | High | Super admin sees MRR, ARR, churn, active subscriptions, and projections |
| WS5 | Audit, security, and rollout | High | Actions are logged, callbacks are verified, and the build is testable |

---

## Phase Plan

## Phase 0: Mobilize
**Target:** 0.5-1 day  
**Goal:** Lock the scope before writing code.

### Tasks

- `TPAY-001` Freeze the current baseline and confirm the exact files in scope.
  Deliverable: list of current build assets and backend modules to extend
  Acceptance: we agree not to rebuild the admin shell

- `TPAY-002` Confirm payment status vocabulary.
  Deliverable: one status map for tenant payments, subscription state, and verification state
  Acceptance: approve/reject/retry and expiry states are consistent across backend and UI

- `TPAY-003` Confirm the payment rail.
  Deliverable: decision note that platform-owned M-Pesa paybill is the first payment rail
  Acceptance: Flutterwave remains deferred unless reintroduced later

- `TPAY-004` Confirm evidence storage.
  Deliverable: tracker location for screenshots, API responses, and test results
  Acceptance: every completed task has proof

### Exit Criteria

- scope is frozen
- payment states are defined
- payment rail is confirmed
- evidence tracking exists

---

## Phase 1: Tenant Payment Operations
**Target:** 2-4 days  
**Goal:** Add the missing operations lane for tenant payment review.

### Tasks

- `TPAY-101` Add a dedicated tenant payments data contract and API surface.
  Deliverable: list endpoints for payment rows, detail view, and status updates
  Acceptance: super admin can list tenant payments with school, amount, method, transaction code, status, and date

- `TPAY-102` Add payment verification actions.
  Deliverable: `Approve`, `Reject`, and `Retry Verification` actions for pending tenant payments
  Acceptance: each action updates backend state and writes an audit log

- `TPAY-103` Add a `View Payments` drill-down from the tenant row.
  Deliverable: payment history drawer or page for each tenant
  Acceptance: super admin can see payment history without leaving the tenant context

- `TPAY-104` Keep impersonation as debug-only support.
  Deliverable: tenant-row action or linked debug flow that opens impersonation only when intended
  Acceptance: impersonation is clearly separated from payment processing

### Exit Criteria

- payments can be listed
- payments can be verified or rejected
- tenants can open payment history
- audit logs capture all actions

---

## Phase 2: Subscription Lifecycle Automation
**Target:** 2-3 days  
**Goal:** Auto-disable overdue schools and bring them back when payment clears.

### Tasks

- `TPAY-201` Implement a daily expiry job for subscriptions.
  Deliverable: cron job with lock protection that marks overdue tenants inactive or suspended
  Acceptance: expired tenants are disabled only once per run and do not flap

- `TPAY-202` Add a tenant access guard for expired subscriptions.
  Deliverable: middleware or request gate that blocks expired tenants from protected flows
  Acceptance: expired tenants receive a clear renewal message instead of partial access

- `TPAY-203` Reactivate tenants when payment is confirmed.
  Deliverable: backend update path that sets subscription active and extends the next period
  Acceptance: confirmed payment restores access automatically

- `TPAY-204` Add expiry and renewal notifications.
  Deliverable: email or SMS notices for upcoming expiry, suspension, and successful renewal
  Acceptance: operators and tenant contacts know what happened without checking the DB

### Exit Criteria

- overdue tenants are automatically disabled
- confirmed payment restores access
- notifications fire for the lifecycle events

---

## Phase 3: Platform M-Pesa Tenant Billing
**Target:** 3-5 days  
**Goal:** Make the paybill flow safe and operational for tenant subscription payments.

### Tasks

- `TPAY-301` Implement the tenant payment initiation flow for platform-owned M-Pesa.
  Deliverable: STK push or paybill instruction flow that charges the platform, not the school
  Acceptance: the transaction is tied to a tenant subscription or invoice

- `TPAY-302` Harden callback verification and duplicate protection.
  Deliverable: verified callback handling, dedupe on transaction code, and idempotent settlement
  Acceptance: duplicate callbacks do not duplicate revenue or subscription extension

- `TPAY-303` Link payment confirmation to invoice and subscription records.
  Deliverable: payment settlement that updates invoice state and subscription dates
  Acceptance: the ledger, invoice, and tenant access state agree

- `TPAY-304` Add a manual fallback path for verification failures.
  Deliverable: retry or manual verification action for operators
  Acceptance: failed verification does not strand a legitimate payment

### Exit Criteria

- payment initiation works
- callbacks are verified
- duplicates are blocked
- invoice and subscription state stay in sync

---

## Phase 4: Revenue Analytics
**Target:** 2-4 days  
**Goal:** Make the revenue dashboard reflect the platform business accurately.

### Tasks

- `TPAY-401` Extend revenue cards in the existing analytics page.
  Deliverable: Total Revenue, Monthly Revenue, Active Subscriptions, Churn Rate
  Acceptance: the cards use real backend data, not mock values

- `TPAY-402` Add revenue projections and trend charts.
  Deliverable: simple forecast and monthly trend view for platform billing
  Acceptance: the dashboard shows the direction of the business, not just raw totals

- `TPAY-403` Add plan and tenant segment breakdowns.
  Deliverable: revenue by plan, active vs expired tenants, and churn risk visibility
  Acceptance: super admin can see where revenue comes from

### Exit Criteria

- dashboard is business-useful
- projections are visible
- churn and segmentation are easy to read

---

## Phase 5: Audit, Testing, And Rollout
**Target:** 2-4 days  
**Goal:** Prove the system is safe enough to use in production.

### Tasks

- `TPAY-501` Add backend regression tests for tenant payments and expiry.
  Deliverable: test coverage for payment approval, rejection, retry, expiry, and reactivation
  Acceptance: the core lifecycle cannot regress silently

- `TPAY-502` Add frontend verification on the compiled admin build.
  Deliverable: syntax and route checks for the updated compiled pages
  Acceptance: the super-admin shell still loads correctly

- `TPAY-503` Run a demo-school dry run for the full tenant payment loop.
  Deliverable: evidence of payment initiation, verification, expiry handling, and reactivation
  Acceptance: one end-to-end scenario is proven before wider rollout

- `TPAY-504` Produce a support runbook.
  Deliverable: operator guide for payment failures, expiry, manual verification, and impersonation use
  Acceptance: support can follow the process without developer help

### Exit Criteria

- automated tests pass
- the compiled shell still loads
- one demo-school flow is proven
- support has a runbook

---

## Priority Order

1. `TPAY-001` to `TPAY-004`
2. `TPAY-101` to `TPAY-104`
3. `TPAY-201` to `TPAY-204`
4. `TPAY-301` to `TPAY-304`
5. `TPAY-401` to `TPAY-403`
6. `TPAY-501` to `TPAY-504`

This keeps the payment operations lane ahead of automation, automation ahead of analytics polish, and rollout last.

---

## Status Legend

- `Complete`: finished with evidence captured
- `In Progress`: active implementation or validation
- `Ready Now`: can be started immediately
- `Blocked`: waiting on owner input or external proof
- `Decision Pending`: needs approval before work starts
- `Deferred`: intentionally later-phase work

---

## Evidence Required Per Task

Each completed task should capture at least one of:

- API response capture
- screenshot
- test run output
- payment reference
- callback event ID
- audit log entry
- support signoff note

---

## Recommended Owners

| Area | Recommended Owner |
|------|-------------------|
| Tenant payment workflow | backend engineer + platform admin |
| Subscription expiry automation | backend engineer |
| M-Pesa paybill processing | backend engineer + finance owner |
| Revenue dashboard | frontend engineer + platform admin |
| Rollout and support | support lead + platform admin |

---

## Definition Of Success

This plan is successful when:

1. the existing super-admin UI is extended, not rebuilt
2. tenant payments can be reviewed and verified from the platform dashboard
3. overdue tenants are disabled automatically and restored after valid payment
4. M-Pesa paybill payments settle safely and idempotently
5. revenue analytics show accurate business metrics
6. support can operate the workflow using documented steps

---

## Immediate Next Step

Review and approve this plan before any implementation begins.
