# Approvals, Secretary, Library, and Procurement Rollout Runbook

This runbook covers the behavior shipped across the approvals cleanup, secretary role, teacher custody flow, and procurement redesign.

It is intended for admins, finance staff, support staff, librarians, registrars, and school operations teams that need to validate or explain the new rules.

## 1. What Should Be True Now

- Approval access is deny-by-default.
- `SECRETARY` is a real role with a narrow support baseline.
- Teachers can receive hard-copy books, issue them to assigned students, and return or reconcile them.
- Store orders now behave like procurement documents with supplier, document number, snapshot pricing, approval trail, and receiving state.
- Support should use the approval trail, receiving state, and role scope as the source of truth, not old assumptions about `send_to` or current stock cost.

## 2. Role-To-Tab Visibility

The approvals hub should only appear for users who have at least one approval category.

| Role group | Approvals hub | Notes |
|---|---|---|
| `ADMIN`, `PRINCIPAL`, `DEPUTY_PRINCIPAL`, `TENANT_SUPER_ADMIN` | Yes | Admin-family users resolve to all approval categories. |
| `ACCOUNTANT`, `BURSAR` | Yes | Finance-family users see finance approval categories and procurement screens. |
| `HR_OFFICER` | Yes | HR users see leave approvals only. |
| `LIBRARIAN` | Yes | Library users see acquisitions approvals only. |
| `HOD` | Yes | Academic lead users see timetable approvals only. |
| `REGISTRAR` | Yes | Registrar users see admissions approvals only. |
| `SECRETARY` | No | Secretary is a support role, not an approvals role. |
| `TEACHER`, `STUDENT`, `PARENT`, and other non-approver roles | No | They should not discover `/dashboard/approvals`. |

Legacy role names from older tenants can still resolve to approval categories for compatibility, but the seeded role catalog should be treated as the current source of truth.

The dashboard "Tasks & Requests" widget is narrower than the approvals hub and should not be treated as the policy source. If the widget and the hub disagree, the role scope is wrong.

## 3. Approval Category Ownership

Use the category ownership below when explaining why a user can or cannot act.

| Category | Owner scope |
|---|---|
| `writeoffs`, `reversals`, `adjustments`, `store_orders` | Finance / admin family |
| `leave` | HR |
| `acquisitions` | Library |
| `timetable` | Academic lead |
| `admissions` | Registrar |
| `maintenance` | Legacy compatibility only |

Two support rules matter here:

- visibility and action rights should match
- if a user can see a category but cannot approve it, the account likely has the wrong role assignment or a stale legacy role

## 4. Secretary Onboarding

`SECRETARY` is the role to use for school secretary accounts.

Expected baseline behavior:

- modules: `STUDENTS`, `EXAMINATIONS`, `COMMUNICATION`, `REPORTING`
- no approvals tab by default
- no finance or admin approval powers

If a staff record says "School Secretary", it should map to `SECRETARY` automatically.

If a secretary account shows approval access, check for accidental admin, finance, HR, or legacy approval-role membership before changing anything else.

## 5. Teacher Library Custody

The teacher workflow is a custody chain, not a generic librarian replacement.

Current expected flow:

1. library issues hard-copy books to a teacher
2. teacher receives the books as classroom-held inventory
3. teacher issues books to students assigned to that class
4. returns and outstanding items remain visible for reconciliation

Support checks:

- confirm the teacher is synced as a staff library member
- confirm the teacher has the correct assigned class
- confirm the student is eligible for that class
- confirm the copy still has an open loan if a return has not been posted

If the teacher portal does not show the expected students or books, the first thing to verify is class assignment, not library permissions.

## 6. Procurement Workflow

The store-order flow now behaves like procurement.

Document and pricing rules:

- document numbers are generated as `LPO-YYYY-NNNN` or `LSO-YYYY-NNNN`
- supplier should be carried through from the request to the expense
- line items snapshot quoted unit price at request/review time
- approved totals should not move when stock item cost changes later
- approval trail should record create, approve, reject, and receive activity

Operational states:

- `PENDING` means the request is awaiting review
- `APPROVED` means the request can be fulfilled or received
- `REJECTED` means the request is closed
- `PENDING`, `PARTIAL`, `RECEIVED` describe receiving progress

Support rule:

- `FULFILL` is a receiving action, not an approval action
- if an expense amount looks wrong, inspect the approval snapshot and quoted line items before changing current stock cost

## 7. Rollout Checklist

Before calling the rollout complete, verify all of these:

1. A finance or admin user can see the approvals hub and the expected categories.
2. A secretary user does not see an approvals tab.
3. A registrar user sees admissions approval access and nothing broader.
4. A librarian user sees acquisitions approval access only.
5. A teacher can receive a book, issue it to a student, and return it through the custody flow.
6. A procurement request can be created, approved, fulfilled, and converted into an expense without totals changing after the fact.
7. Support can explain the new rules without opening the codebase.

## 8. Rollback And Support Notes

If approvals leak to the wrong user:

- check the role assignment first
- check for stale legacy roles
- check the approval category map before changing the UI

If procurement totals drift:

- check quoted unit prices on the line items
- check the approved total stored on the request
- do not rely on the live stock item cost as the source of truth

If teacher custody looks empty:

- check the teacher membership sync
- check the assigned class
- check whether the loan is still open

If a secretary sees finance or approvals behavior:

- the account has been over-scoped
- fix the role assignment rather than adding special-case UI

---

Related planning docs:

- [Task plan](../APPROVALS_LIBRARY_FINANCE_SECRETARY_TASK_PLAN.md)
- [Audit](../APPROVALS_LIBRARY_FINANCE_SECRETARY_AUDIT.md)
