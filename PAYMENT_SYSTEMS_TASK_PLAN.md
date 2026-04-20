# Payment Systems Task Plan
## Execution Plan From The Second Audit

**Date:** April 19, 2026  
**Source:** `PAYMENT_SYSTEMS_SECOND_AUDIT.md`  
**Purpose:** Turn the second audit findings into a concrete execution plan that covers launch blockers, hardening work, and deferred payment roadmap items

---

## Planning Goal

Move the payment system from:

- MVP implemented in repo

to:

- validated, launch-ready, and operationally supportable

without mixing immediate launch blockers with later-phase enhancements.

---

## Planning Principles

1. Finish launch blockers before expanding scope.
2. Treat environment validation as real work, not "someone will test later."
3. Require evidence for every completed task.
4. Keep post-launch improvements visible, but do not let them delay launch.
5. Use the existing readiness endpoint and runbook as the operational source of truth.

---

## Current Status Snapshot

This task plan assumes the repo-backed payment baseline has already been verified and should not be treated as greenfield build work.

| Area | Current Status | Notes |
|------|----------------|-------|
| Portal payment entry points | Verified in repo | Parent and student portals already expose Stripe, M-Pesa, and bank-transfer initiation paths |
| Shared settlement and recovery paths | Verified in repo | Stripe webhook settlement, M-Pesa callback settlement, and gateway-event reprocess paths already exist |
| Launch tooling | Verified in repo | readiness, test-connection, callback-url, gateway-event endpoints, and runbook are present |
| Regression suites | Verified on April 19, 2026 | `school.test_finance_phase4` and `school.test_phase6_finance_collection_ops_activation_prep` passed |
| Tenant config validation | Pending | Real tenant credentials and public callback/webhook reachability still need proof |
| Staging payment validation | Pending | Parent/student staging flows still need live execution evidence |
| Real bank CSV validation | Pending | Real statement samples still need import and reconciliation proof |
| Operator recovery drill | Pending | Finance/support still need a staging reprocess exercise and runbook signoff |

The task statuses below refer to execution work in this plan, not to the repo capabilities already verified.

---

## Workstreams

| Workstream | Purpose | Priority | Target Outcome |
|------------|---------|----------|----------------|
| WS1 | Launch configuration validation | Critical | Stripe and M-Pesa are correctly configured per tenant |
| WS2 | End-to-end staging payment validation | Critical | Parent/student flows settle correctly in staging |
| WS3 | Bank statement validation | Critical | Real CSV files are imported and reconciled successfully |
| WS4 | Operator readiness | Critical | Finance/support can recover failed events without DB access |
| WS5 | Launch hardening | High | Payment initiation is safer and more production-ready |
| WS6 | Deferred roadmap | Medium | Larger follow-on features are planned with clear next steps |

---

## Phase Plan

## Phase 0: Mobilize
**Target:** 0.5-1 day  
**Goal:** Remove ambiguity before execution starts.

### Tasks

- `TP-001` Confirm the launch tenant list.
  Deliverable: named list of staging and production tenants in scope
  Acceptance: every tenant has a clear owner and environment label

- `TP-002` Confirm access and credentials ownership.
  Deliverable: owner list for Stripe keys, Stripe webhook setup, M-Pesa credentials, bank statement samples
  Acceptance: no launch-critical dependency is ownerless

- `TP-003` Freeze the launch-candidate baseline.
  Deliverable: commit hash / release candidate identifier for validation
  Acceptance: all validation activity references the same build

- `TP-004` Create an evidence folder or tracker for screenshots, test results, and runbook notes.
  Deliverable: central checklist or shared folder
  Acceptance: every validation task has a place to store proof

### Exit Criteria

- tenant list confirmed
- owners assigned
- release candidate identified
- evidence location defined

---

## Phase 1: Launch-Critical Validation
**Target:** 2-4 days  
**Goal:** Close all "pending before launch" items from the second audit.

### WS1: Launch Configuration Validation

- `TP-101` Run `GET /api/finance/launch-readiness/` for each launch tenant.
  Deliverable: per-tenant readiness snapshot
  Acceptance: all blocking issues are logged and assigned

- `TP-102` Validate Stripe test connection per tenant.
  Deliverable: result from `POST /api/finance/stripe/test-connection/`
  Acceptance: success response, correct account identity, correct mode

- `TP-103` Validate M-Pesa test connection per tenant.
  Deliverable: result from `POST /api/finance/mpesa/test-connection/`
  Acceptance: success response in the intended environment

- `TP-104` Validate public callback and webhook URLs per tenant.
  Deliverable: screenshots or API responses from readiness and callback-url endpoints
  Acceptance:
  Stripe webhook URL is HTTPS and externally reachable
  M-Pesa callback URL is HTTPS and externally reachable
  `mpesa.callback_source` is not `request_fallback`

- `TP-105` Resolve tenant-level configuration gaps.
  Deliverable: updated tenant settings and rerun readiness results
  Acceptance: each launch tenant returns `ready: true`

### WS2: End-to-End Staging Payment Validation

- `TP-106` Run parent portal smoke tests in staging.
  Deliverable: evidence of Stripe, M-Pesa, and bank transfer initiation
  Acceptance:
  Stripe returns hosted checkout URL
  M-Pesa returns checkout request ID
  bank transfer returns manual reference and instructions

- `TP-107` Run student portal smoke tests in staging.
  Deliverable: evidence of Stripe, M-Pesa, and bank transfer initiation
  Acceptance: same as parent portal, but from student flow

- `TP-108` Validate Stripe settlement end to end.
  Deliverable: one successful staging Stripe payment
  Acceptance:
  webhook is received
  payment is created
  invoice balance updates correctly
  duplicate completion remains safe

- `TP-109` Validate M-Pesa settlement end to end.
  Deliverable: one successful staging M-Pesa payment
  Acceptance:
  callback is received
  gateway transaction updates
  payment is created
  invoice balance updates correctly

### WS3: Real Bank Statement Validation

- `TP-110` Collect at least one real bank statement CSV sample per supported bank format.
  Deliverable: sample files approved for staging validation
  Acceptance: finance confirms sample realism

- `TP-111` Import a real staging statement file.
  Deliverable: successful `import-csv` run
  Acceptance: file imports without blocking parse failures

- `TP-112` Validate reconciliation outcomes.
  Deliverable: matched, unmatched, and cleared examples
  Acceptance:
  at least one line auto-matches
  at least one unmatched line remains visible
  at least one matched line is cleared successfully
  one incorrect or forced match can be corrected through operator actions

### WS4: Operator Readiness

- `TP-113` Exercise failed-event inspection.
  Deliverable: evidence of finance staff using `/api/finance/gateway/events/`
  Acceptance: operators can find failed/unprocessed events without DB access

- `TP-114` Exercise manual reprocess for one recoverable event.
  Deliverable: reprocess test record and outcome
  Acceptance: reprocess succeeds without duplicate settlement

- `TP-115` Run support / bursar walkthrough using `docs/payments_launch_runbook.md`.
  Deliverable: annotated runbook or signoff notes
  Acceptance: support and bursar can complete the documented steps unaided

- `TP-116` Produce launch go/no-go summary.
  Deliverable: one-page readiness decision note
  Acceptance: every critical validation task is either passed or explicitly waived by owner

### Exit Criteria

- all launch tenants pass readiness
- parent and student portals are smoke-tested in staging
- one real Stripe and one real M-Pesa payment are validated
- one real bank statement file is validated
- one manual reprocess drill is completed
- support / bursar signoff is captured

---

## Phase 2: Launch Hardening
**Target:** 3-5 days  
**Goal:** Decide and close the highest-value hardening gaps called out in the second audit without confusing optional hardening with launch validation.

### WS5: Hardening Tasks

- `TP-200` Decide which hardening items are true launch blockers.
  Deliverable: decision note covering rate limiting, initiation idempotency, and refund/reversal posture
  Acceptance:
  each item is explicitly marked as launch-blocking or deferred
  owner approval is recorded before implementation starts

- `TP-201` Add clear rate limiting to payment initiation endpoints if `TP-200` keeps it in pre-launch scope.
  Scope:
  parent portal finance pay endpoint
  student portal finance pay endpoint
  finance-side payment initiation endpoints
  Deliverable: code + tests + documented throttle behavior
  Acceptance: abusive repeat initiation is blocked predictably

- `TP-202` Add explicit idempotency support for payment initiation if `TP-200` keeps it in pre-launch scope.
  Scope:
  external-facing initiation paths for Stripe and M-Pesa
  Deliverable: request contract, persistence behavior, tests
  Acceptance: duplicate initiation requests return safe, deterministic results

- `TP-203` Review and decide Stripe refund / reversal automation scope.
  Deliverable: design note or decision memo
  Acceptance:
  either refund automation is implemented for MVP
  or it is explicitly deferred with approved manual process and UI/runbook coverage

- `TP-204` Extend automated regression coverage for whichever hardening changes land in this phase.
  Deliverable: tests covering throttling, duplicate initiation, refund/reversal decision path, or any approved equivalent scope
  Acceptance: test suite protects the hardening rules that remain in launch scope

### Exit Criteria

- an approved decision exists for rate limiting, initiation idempotency, and refund/reversal scope
- any hardening items kept in launch scope are implemented and tested
- Stripe refund handling is either implemented or formally deferred with operator process

---

## Phase 3: Post-Launch Expansion
**Target:** 2-6 weeks, staged  
**Goal:** Cover the deferred items without blocking launch.

### WS6: Deferred Roadmap Tasks

- `TP-301` Direct bank API discovery and feasibility.
  Deliverable: vendor/options comparison and recommendation
  Acceptance: clear decision on whether to build bank-direct integration

- `TP-302` Cheque OCR feasibility assessment.
  Deliverable: technical options, cost, and operational fit
  Acceptance: go / no-go decision with recommended approach

- `TP-303` Recurring card payments discovery.
  Deliverable: product + compliance assessment for recurring Stripe flows
  Acceptance: decision on whether recurring payments belong in the next finance phase

- `TP-304` Advanced fraud controls backlog.
  Deliverable: prioritized list of fraud/risk improvements beyond current fixes
  Acceptance: backlog items ranked by risk reduction and effort

- `TP-305` Reconciliation intelligence expansion.
  Deliverable: plan for smarter matching heuristics
  Acceptance: approved next-step design for matching beyond exact reference and amount/date fallback

### Exit Criteria

- every deferred item has either a scoped design, feasibility note, or explicit no-go decision

---

## Priority Order

1. `TP-001` to `TP-004`
2. `TP-101` to `TP-116`
3. `TP-200` to `TP-204`
4. `TP-301` to `TP-305`

This ordering keeps launch work ahead of hardening, and hardening ahead of roadmap expansion.

---

## Status Legend

Status reflects the next meaningful action at plan time. Dependencies still govern actual sequencing.

- `Complete`: finished with evidence captured
- `In Progress`: active discovery or execution has started, but acceptance is not yet met
- `Ready Now`: can be started immediately with the current repo and workspace context
- `Ready for Staging`: implementation is present; next step is tenant or staging execution with evidence capture
- `Blocked`: waiting on owner input, real-world samples, or upstream validation results
- `Decision Pending`: requires an explicit launch-scope decision before implementation should start
- `Deferred`: intentionally post-launch

---

## Task Tracker

| Task ID | Task | Priority | Phase | Status | Dependencies |
|---------|------|----------|-------|--------|--------------|
| TP-001 | Confirm launch tenant list | Critical | 0 | In Progress | None |
| TP-002 | Confirm access and credentials ownership | Critical | 0 | Blocked | TP-001 |
| TP-003 | Freeze launch-candidate baseline | Critical | 0 | Complete | TP-001 |
| TP-004 | Create evidence tracker | Critical | 0 | Complete | TP-001 |
| TP-101 | Run readiness endpoint per tenant | Critical | 1 | Ready for Staging | TP-001, TP-003 |
| TP-102 | Validate Stripe test connection | Critical | 1 | Ready for Staging | TP-101 |
| TP-103 | Validate M-Pesa test connection | Critical | 1 | Ready for Staging | TP-101 |
| TP-104 | Validate public callback/webhook URLs | Critical | 1 | Ready for Staging | TP-101 |
| TP-105 | Resolve tenant config gaps | Critical | 1 | Blocked | TP-102, TP-103, TP-104 |
| TP-106 | Parent portal staging smoke test | Critical | 1 | Ready for Staging | TP-105 |
| TP-107 | Student portal staging smoke test | Critical | 1 | Ready for Staging | TP-105 |
| TP-108 | Stripe end-to-end staging settlement | Critical | 1 | Ready for Staging | TP-102, TP-106, TP-107 |
| TP-109 | M-Pesa end-to-end staging settlement | Critical | 1 | Ready for Staging | TP-103, TP-106, TP-107 |
| TP-110 | Collect real bank statement samples | Critical | 1 | Blocked | TP-002 |
| TP-111 | Import real statement file | Critical | 1 | Blocked | TP-110 |
| TP-112 | Validate reconciliation outcomes | Critical | 1 | Blocked | TP-111 |
| TP-113 | Exercise failed-event inspection | Critical | 1 | Ready for Staging | TP-105 |
| TP-114 | Exercise manual reprocess | Critical | 1 | Ready for Staging | TP-113 |
| TP-115 | Run support/bursar walkthrough | Critical | 1 | Blocked | TP-112, TP-114 |
| TP-116 | Produce launch go/no-go summary | Critical | 1 | Blocked | TP-108, TP-109, TP-115 |
| TP-200 | Decide launch-blocking hardening scope | High | 2 | Decision Pending | TP-116 or launch freeze decision |
| TP-201 | Add rate limiting to initiation endpoints | High | 2 | Decision Pending | TP-200 |
| TP-202 | Add initiation idempotency support | High | 2 | Decision Pending | TP-200 |
| TP-203 | Decide Stripe refund automation scope | High | 2 | Decision Pending | TP-116 |
| TP-204 | Extend regression suite for hardening | High | 2 | Blocked | TP-200, TP-201, TP-202, TP-203 |
| TP-301 | Bank API feasibility | Medium | 3 | Deferred | TP-116 |
| TP-302 | Cheque OCR feasibility | Medium | 3 | Deferred | TP-116 |
| TP-303 | Recurring card payments discovery | Medium | 3 | Deferred | TP-116 |
| TP-304 | Advanced fraud controls backlog | Medium | 3 | Deferred | TP-116 |
| TP-305 | Reconciliation intelligence expansion | Medium | 3 | Deferred | TP-112 |

---

## Evidence Required Per Task

Each completed task should attach at least one of:

- API response capture
- screenshot
- test run output
- staging payment reference
- gateway event ID
- bank import file name and result summary
- signoff note from finance / support / bursar

Current tracker location:

- `PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md`

No task should be marked complete without evidence.

---

## Recommended Owners

| Area | Recommended Owner |
|------|-------------------|
| tenant settings and credentials | platform / finance admin |
| Stripe validation | backend engineer + finance admin |
| M-Pesa validation | backend engineer + finance admin |
| portal smoke tests | QA or product engineer |
| bank statement validation | bursar / finance operations |
| reprocess drill and runbook signoff | support + finance operations |
| hardening implementation | backend engineer |
| deferred roadmap investigations | engineering lead / product lead |

---

## Definition Of Success

This plan is successful when:

1. every launch-critical task in Phase 1 is complete with evidence
2. launch readiness is green for all target tenants
3. real staging flows are proven for Stripe, M-Pesa, and bank reconciliation
4. support and finance teams can operate the system using the documented runbook
5. hardening tasks and deferred roadmap items are clearly tracked instead of left implicit

---

## Immediate Next Step

Start with:

- `TP-001` Confirm launch tenant list
- `TP-002` Confirm credential owners
- `TP-101` Run readiness snapshots for each launch tenant once `TP-001` is complete
- record proof in `PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md`

That gives the fastest path to converting the second audit into active execution.
