# Task Plan: Approvals, Library Teacher Flow, Procurement, and Secretary Role

**Date:** April 21, 2026  
**Source:** `APPROVALS_LIBRARY_FINANCE_SECRETARY_AUDIT.md`  
**Purpose:** Turn the audit into a phased implementation plan and track what has already landed

---

## Planning Goal

Move the current mixed role-and-approval behavior to a state where:

- users only see tabs and approval queues that match their role and scope
- users with no approval responsibility do not get an approvals tab at all
- teachers can receive hard-copy books and issue them to students with traceable custody
- finance has explicit local purchase and local supply workflows instead of generic store requests
- `SECRETARY` is a real system role with valid defaults and provisioning support

---

## Current Status Snapshot

| Area | Status | Notes |
|------|--------|-------|
| Phase 1 approvals backend policy | Complete | `school/approval_scope.py` now drives deny-by-default approval authority |
| Phase 1 approvals frontend visibility | Complete | approvals hub fallback removed, shell route hidden for non-approvers, finance/admin dashboard widget narrowed |
| Phase 1 regression coverage | Complete | `school.test_approval_scope_phase1` passed with 9 tests |
| Secretary role definition | Complete | `SECRETARY` is now seeded, scoped, provisionable, and labeled correctly in the shell |
| Teacher library custody workflow | Complete | teacher custody chain, teacher portal workflow, and library reporting are live |
| Procurement redesign | Complete | LPO/LSO procurement fields, approval trail, receiving state, and finance/store screens are live |
| Documentation and rollout safety | Complete | rollout runbook now covers visibility, onboarding, custody, procurement, and rollback checks |

---

## Workstreams

| Workstream | Purpose | Priority | Target Outcome |
|------------|---------|----------|----------------|
| WS1 | Approvals scope cleanup | Critical | Only true approvers see approvals UI and actions |
| WS2 | Secretary role definition | Critical | Secretary can be provisioned and scoped correctly |
| WS3 | Teacher library circulation | High | Teacher custody and student issuance are traceable |
| WS4 | Procurement redesign | High | LPO/LSO workflows are explicit, auditable, and finance-ready |
| WS5 | Documentation and regression coverage | Critical | Behavior is documented and protected by tests |

---

## Phase 0: Design Freeze and Policy Alignment

**Target:** 0.5-1 day  
**Goal:** Lock the rules before implementation.

### Tasks

- `ALF-001` Define canonical approval-capable roles.
  Deliverable: one matrix of roles vs approval categories
  Acceptance: every approval category has named viewer roles and actor roles

- `ALF-002` Decide how secretary should be scoped.
  Deliverable: secretary module baseline and default permission list
  Acceptance: secretary is classified as admin support, not a free-form custom role

- `ALF-003` Decide teacher library workflow shape.
  Deliverable: one chosen model for classroom custody
  Acceptance:
  either teacher custody is implemented as a dedicated transaction state
  or it is implemented as a linked handoff record with equivalent traceability

- `ALF-004` Decide whether procurement extends `StoreOrderRequest` or introduces dedicated LPO/LSO models.
  Deliverable: architecture note
  Acceptance: decision is explicit before code changes begin

### Exit Criteria

- approval matrix agreed
- secretary scope agreed
- teacher library workflow agreed
- procurement model direction agreed

---

## Phase 1: Approvals and Role Scope Cleanup

**Target:** 1-2 days  
**Goal:** Remove approval leakage and align UI with backend authority.

### Tasks

- `ALF-101` Create a backend source of truth for approval visibility and action rights.
  Deliverable: shared policy map or resolver
  Acceptance: frontend and backend consume the same approval scope rules

- `ALF-102` Hide the approvals route for users with zero actionable approval categories.
  Scope:
  app shell route search
  quick access cards
  sidebar or dashboard entry points
  Acceptance: non-approver users do not discover `/dashboard/approvals`

- `ALF-103` Fix the approvals hub to deny by default.
  Deliverable: no fallback to all categories for unknown roles
  Acceptance: unknown roles receive zero categories, not full access

- `ALF-104` Align dashboard "Tasks & Requests" with true approval scope.
  Deliverable: dashboard widget visibility and payload gating
  Acceptance: only roles with relevant approvals see approval-like widgets

- `ALF-105` Align backend approval endpoints to the same actor matrix.
  Scope:
  finance adjustments
  finance reversals
  finance write-offs
  store order review
  Acceptance: action rights are consistent across modules

- `ALF-106` Add regression tests for approvals scope.
  Acceptance:
  non-approvers cannot see approvals entry points
  approvers only see their categories
  unauthorized approval actions return forbidden

### Exit Criteria

- approvals tab appears only for true approvers
- approvals categories are role-correct
- dashboard approval widgets are role-correct
- backend actions enforce the same matrix

**Status:** Complete on April 21, 2026

---

## Phase 2: Secretary Role Definition

**Target:** 0.5-1 day  
**Goal:** Make secretary a real first-class role.

### Tasks

- `ALF-201` Add `SECRETARY` to the role catalog and role choices.
  Deliverable: seeded role + model support
  Acceptance: secretary is a valid system role

- `ALF-202` Add secretary scope profile and module baseline.
  Deliverable: secretary scope in `role_scope.py`
  Acceptance: secretary modules are explicit and documented

- `ALF-203` Add default secretary permissions.
  Deliverable: RBAC permission defaults
  Acceptance: HR provisioning and validation accept `SECRETARY`

- `ALF-204` Update HR role suggestion logic for school secretary positions.
  Acceptance: "School Secretary" titles resolve to `SECRETARY`

- `ALF-205` Add secretary tests and documentation.
  Acceptance:
  provisioning works
  unsupported-role errors no longer occur for secretary

### Exit Criteria

- secretary can be provisioned end to end
- secretary receives the intended tabs and permissions

**Status:** Complete on April 22, 2026

---

## Phase 3: Teacher Hard-Copy Library Workflow

**Target:** 2-3 days  
**Goal:** Support teacher receipt and student issuance of physical books.

### Tasks

- `ALF-301` Add teacher library access model.
  Deliverable: role/module/permission setup for teacher circulation actions
  Acceptance: teachers can access only the teacher-safe library workflow

- `ALF-302` Add teacher custody data model.
  Deliverable: transaction or handoff structure for:
  library to teacher
  teacher to student
  student return to teacher or library
  Acceptance: chain of custody is queryable and auditable

- `ALF-303` Build teacher-facing circulation components.
  Scope:
  receive hard-copy books from library
  view classroom-held books
  issue books to students
  process returns or mark outstanding
  Acceptance: teachers do not need full librarian screens

- `ALF-304` Update librarian workflows to support teacher handoff.
  Acceptance: librarians can issue books to teachers as a distinct action

- `ALF-305` Add library reporting for teacher custody.
  Acceptance: overdue and current-holder reporting includes teacher-held inventory

- `ALF-306` Add regression tests for teacher book workflow.
  Acceptance:
  teacher can receive books
  teacher can issue to students
  unauthorized users cannot use teacher circulation actions
  returns and status transitions stay consistent

### Exit Criteria

- teacher custody exists as a first-class flow
- student issuance through teachers is traceable
- librarians and teachers each get the right UI surface

**Status:** Complete on April 22, 2026

---

## Phase 4: Procurement Redesign for Local Purchase and Local Supply

**Target:** 2-4 days  
**Goal:** Replace generic store-order handling with auditable procurement workflows.

### Tasks

- `ALF-401` Design explicit LPO/LSO entities or extend store order with procurement-grade fields.
  Required fields:
  supplier
  document number
  quoted unit price
  approved quantity
  approved total
  office ownership
  approval trail
  receiving state
  Acceptance: procurement totals are snapshot-based, not derived from mutable stock cost

- `ALF-402` Implement local purchase and local supply API flows.
  Acceptance:
  finance and admin responsibility boundaries are explicit
  `send_to` is no longer just metadata

- `ALF-403` Build finance-facing procurement components.
  Scope:
  list/filter LPOs and LSOs
  review/approve/reject
  generate expense from approved procurement
  view supplier and pricing detail
  Acceptance: finance screens reflect real procurement data

- `ALF-404` Build store-facing request initiation and fulfillment flow.
  Acceptance: requestors, approvers, and receivers have separate states and actions

- `ALF-405` Fix valuation and expense posting logic.
  Acceptance:
  expense generation uses approved procurement totals
  supplier/vendor details carry through correctly

- `ALF-406` Add procurement regression tests.
  Acceptance:
  approval authority is enforced
  totals remain stable after item cost changes
  free-text items do not create zero-value expenses silently

### Exit Criteria

- LPO/LSO workflow is explicit
- procurement totals are auditable
- finance and store roles are separated correctly

**Status:** Complete on April 22, 2026

---

## Phase 5: Documentation and Rollout Safety

**Target:** 0.5-1 day  
**Goal:** Make the new behavior understandable and supportable.

### Tasks

- `ALF-501` Document role-to-tab visibility rules.
- `ALF-502` Document approval category ownership and action rights.
- `ALF-503` Document secretary baseline and onboarding rules.
- `ALF-504` Document teacher library circulation workflow.
- `ALF-505` Document LPO/LSO workflow and finance/store responsibilities.

### Exit Criteria

- support and admins can explain the new rules without reading code
- documentation matches implemented behavior

**Status:** Complete on April 22, 2026

---

## Priority Order

1. `ALF-001` to `ALF-004`
2. `ALF-101` to `ALF-106`
3. `ALF-201` to `ALF-205`
4. `ALF-301` to `ALF-306`
5. `ALF-401` to `ALF-406`
6. `ALF-501` to `ALF-505`

This order fixes cross-cutting access control first, then closes the missing secretary role, then implements the operational workflows that depend on correct scope behavior.

---

## Definition of Success

This plan is successful when:

1. users only receive tabs aligned to their role and scope
2. users with no approval responsibility do not receive an approvals tab
3. approval visibility and approval action rights come from one consistent policy
4. teachers can receive and issue hard-copy library books with a visible custody trail
5. local purchase and local supply order flows are explicit and auditable
6. `SECRETARY` is a valid role that can be provisioned and assigned safely

---

## Immediate Next Step

Phases 1 through 5 are complete. The rollout runbook now covers the support and validation steps for the shipped behavior.

If new behavior is added later, open a fresh audit and plan rather than extending this completed implementation plan.
