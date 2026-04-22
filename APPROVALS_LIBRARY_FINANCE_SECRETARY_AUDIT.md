# Approvals, Library, Procurement, and Secretary Audit

**Date:** April 22, 2026  
**Scope:** approvals tab visibility and authority, teacher library circulation, finance local purchase/local supply flows, and secretary role definition

---

## Executive Summary

The audit started from a system with working pieces in each area, but the role and approval boundaries were not aligned end to end. The execution updates below record what has since landed.

The highest-risk findings at audit time were:

1. The approvals experience is driven by hard-coded frontend role maps that do not match the seeded RBAC role catalog.
2. Users can still see approval-like UI even when they are not true approvers, and some true backend approval actions are stricter than the UI suggests.
3. Store finance workflows are generic store-order approvals, not dedicated local purchase order or local supply order workflows.
4. Teachers can exist as library members, but there is no teacher-specific hard-copy custody and student issuance workflow.
5. `SECRETARY` is not a seeded system role even though "School Secretary" exists in staff data and other module copy.

---

## Execution Update

**Implemented on April 21, 2026**

The first approval-scope cleanup slice has now landed in code:

- backend approval authority is centralized in `sms-backend/school/approval_scope.py`
- finance, store, library, timetable, admissions, and maintenance approval actions now enforce deny-by-default approval-category checks
- the admissions module now allows `REGISTRAR` scope users to operate admissions flows instead of blocking them behind `IsTeacher`
- the approvals hub no longer falls back to all categories for unknown roles
- the app shell no longer exposes the approvals route from quick navigation or sidebar navigation for users with no approval categories
- the welcome dashboard approval widget is now limited to the finance/admin roles it currently serves

**Verification**

- targeted Python approval-scope suite: `school.test_approval_scope_phase1` passed with `9` tests
- frontend syntax checks passed for:
  - `AppShell-51i8-bQf.js`
  - `DashboardPage-Dt6RX_j5.js`
  - `ApprovalsHubPage-B_1PnNAs.js`

**Implemented on April 22, 2026**

The secretary-role slice has now landed in code:

- `SECRETARY` is now part of the seeded role catalog and model role choices
- `school/role_scope.py` now defines the `SECRETARY_SUPPORT` scope profile and module baseline
- default permission seeding now includes a secretary baseline for student read access, examinations read access, communication, and reporting
- HR identity suggestion and provisioning flows now recognize "School Secretary" and provision secretary accounts successfully
- seeded staff users and shell role labels now include secretary explicitly

**Verification**

- focused Phase 2 suite passed with `46` tests:
  - `school.test_phase5_seed_alignment`
  - `school.test_phase5_role_scope_bridge`
  - `school.test_phase5_module_baselines`
  - `school.test_phase3_core_business`
  - `hr.test_session6_identity_onboarding`
- frontend syntax check passed for:
  - `AppShell-51i8-bQf.js`

**Implemented on April 22, 2026**

The teacher library custody slice has now landed in code, addressing the missing hard-copy handoff flow:

- the backend now tracks classroom custody with a teacher-to-student loan model on top of the existing librarian-to-teacher circulation
- teacher portal library endpoints now list held books, eligible students, active student loans, and recent returns for assigned classes
- teacher issue and return actions enforce assigned-class checks and custody checks before changing state
- library lookup and return flows now expose and close the classroom custody chain when a copy reaches the desk again
- the teacher portal resources page now consumes the live custody endpoints instead of relying on static placeholder content
- library reporting now includes teacher-held inventory and student-loan counts for operational visibility

**Verification**

- focused backend slice passed with `10` tests:
  - `library.test_phase3_teacher_custody`
  - `school.test_phase5_seed_alignment`
- frontend syntax check passed for:
  - `TeacherPortalResourcesPage-yD5oLmvL.js`

**Implemented on April 22, 2026**

The procurement redesign slice has now landed in code, replacing the generic store-order-only flow with explicit procurement-grade behavior:

- `StoreOrderRequest` now carries procurement document numbers, supplier references, office ownership, approval trail data, approved totals, and receiving state
- `StoreOrderItem` now snapshots quoted unit price and approved totals so valuation is no longer dependent on mutable stock cost
- inventory repository and service flows now preserve procurement totals, approval history, and receiving state through review and fulfillment
- finance and store-facing procurement screens now expose the LPO/LSO-style fields, approval actions, and expense generation paths
- procurement reporting now includes procurement-specific totals and breakdowns for finance visibility

**Verification**

- focused procurement service/report tests passed with `13` tests:
  - `domains.tests.test_inventory_store_services`
  - `domains.tests.test_inventory_store_reports_contract`
- frontend syntax checks passed for:
  - `StoreOrdersPage-DuzIfSJX.js`
  - `FinanceStoreRequestsPage-t8BwopMh.js`
- migration `0062_procurement_workflow_fields` applied successfully in the test database

**Implemented on April 22, 2026**

The rollout-safety docs slice has now landed, giving support one place to validate the shipped behavior:

- `docs/approvals_rollout_runbook.md` documents role-to-tab visibility, approval ownership, secretary onboarding, teacher custody, procurement flow, and rollback checks
- `APPROVALS_LIBRARY_FINANCE_SECRETARY_TASK_PLAN.md` now marks Phase 5 complete and points operators to the runbook
- the support guidance now matches the implemented approval scope, role scope, custody, and procurement rules

**Verification**

- manual cross-check completed against the current shipped code paths for approvals scope, role scope, teacher custody, and procurement behavior

The remaining audit items below are still valid for historical context unless explicitly noted otherwise. Section C documents the pre-Phase-4 procurement state and is now superseded by the implementation update above.

---

## Audit Scope

This audit reviewed the live code paths currently shaping behavior in:

- approvals and dashboard navigation
- role catalog, scope baselines, and permission defaults
- library members and circulation
- store and finance request workflows
- HR role suggestion and provisioning

Key files reviewed include:

- `sms-backend/frontend_build/assets/AppShell-51i8-bQf.js`
- `sms-backend/frontend_build/assets/DashboardPage-Dt6RX_j5.js`
- `sms-backend/frontend_build/assets/ApprovalsHubPage-B_1PnNAs.js`
- `sms-backend/frontend_build/assets/LibraryLayout-BJGqMhZw.js`
- `sms-backend/school/role_scope.py`
- `sms-backend/school/permissions.py`
- `sms-backend/school/models.py`
- `sms-backend/library/models.py`
- `sms-backend/library/views.py`
- `sms-backend/domains/inventory/application/services.py`
- `sms-backend/domains/inventory/infrastructure/django_store_repository.py`
- `sms-backend/domains/inventory/presentation/views.py`
- `sms-backend/domains/inventory/presentation/serializers.py`
- `sms-backend/finance/presentation/viewsets.py`
- `sms-backend/hr/identity.py`
- `sms-backend/hr/views.py`

---

## Findings

## A. Approvals Tab and Role Scope

### A1. The command palette exposes `Approvals` globally

The global quick-search page registry in `AppShell-51i8-bQf.js` includes:

- `id:"approvals"`
- `route:"/dashboard/approvals"`
- `category:"Core"`

That entry is registered alongside every other module route, not behind a role-specific filter. A user can discover the approvals route even if they should not have any approval responsibilities.

### A2. The dashboard still loads approval-like data for broad role sets

`DashboardPage-Dt6RX_j5.js` loads:

- `/store/orders/`
- `/finance/payment-reversals/`
- `/finance/write-offs/`

and builds `pendingItems` from those results. The widget is hidden only when the current role is:

- `LIBRARIAN`
- `ACCOUNTANT`
- `BURSAR`

This means many non-approver roles can still receive a "Tasks & Requests" section even though they do not need an approvals surface.

### A3. The approvals hub uses a frontend-only role map that does not match the backend role catalog

`ApprovalsHubPage-B_1PnNAs.js` defines approval categories:

- `writeoffs`
- `reversals`
- `adjustments`
- `store_orders`
- `leave`
- `acquisitions`
- `timetable`
- `admissions`
- `maintenance`

It then chooses visible categories from a hard-coded role map using role names such as:

- `OWNER`
- `FINANCE`
- `LIBRARY_STAFF`
- `HR_STAFF`
- `ADMISSIONS_OFFICER`
- `TIMETABLE_OFFICER`
- `MAINTENANCE_STAFF`

Those role names do not exist in the seeded role catalog in `school/role_scope.py` and `school/models.py`, which currently centers on roles like:

- `ADMIN`
- `ACCOUNTANT`
- `BURSAR`
- `REGISTRAR`
- `TEACHER`
- `LIBRARIAN`

This is a direct mismatch between frontend approval visibility and backend RBAC.

### A4. Unknown roles currently fall back to all approval categories

The approvals hub falls back to the full category list when a role does not match one of its hard-coded checks.

That means unrecognized or newer roles can inherit the entire approvals center instead of seeing no approvals tab.

This is the single biggest approvals-tab leakage found in the audit.

### A5. Finance approvals are inconsistent between frontend visibility and backend authority

The approvals hub explicitly shows finance categories to:

- `ACCOUNTANT`
- `FINANCE`

But the backend finance approval actions in `finance/presentation/viewsets.py` require admin-like authority for final decisions:

- invoice adjustments: admin-only approve/reject
- payment reversals: admin-only approve/reject
- write-offs: admin-only approve/reject

So the current UI suggests finance staff can work an approvals queue that the backend may still reject.

### A6. Store approvals are too permissive on the backend

`domains/inventory/presentation/views.py` protects store review flows with:

- `permissions.IsAuthenticated`
- `HasModuleAccess`
- `module_key = "STORE"`

There is no additional backend restriction tying review authority to:

- the user's role
- the order's `send_to`
- approver scope

So any user with `STORE` module access can review orders if they can hit the endpoint. That is the opposite problem from the finance endpoints, which are too strict relative to the UI.

### A7. Approval policy is split across too many layers

Current approval behavior is distributed across:

- frontend route registry
- frontend dashboard widgets
- frontend approvals hub role map
- scope baselines in `school/role_scope.py`
- module access checks in `school/permissions.py`
- per-endpoint role checks in finance and HR

There is no single approval policy source of truth.

---

## B. Teacher Hard-Copy Library Flow

### B1. Teachers can already exist in the library membership model

`LibraryMember` supports:

- `Student`
- `Staff`
- `Parent`
- `Alumni`
- `External`

`LibraryMemberViewSet.sync()` already creates active `Staff` members from:

- `hr.Employee`
- `staff_mgmt.StaffMember`

So teachers can be represented today as staff library members.

### B2. The circulation model can record who performed an issue

`CirculationTransaction` already stores:

- `member` as the borrower
- `issued_by` as the acting user

`IssueResourceView` creates an issue row with `issued_by=request.user`.

That means the model can already remember that a teacher or librarian executed a circulation action.

### B3. Teachers do not currently get library circulation capability by default

The teacher default permissions in `seed_default_permissions.py` include:

- `library.book.read`

but do not include:

- `library.circulation.manage`

The teacher scope baseline in `school/role_scope.py` also does not include the `LIBRARY` module.

So a default teacher cannot reliably access library circulation screens or issue books.

### B4. The current library UI is librarian-oriented, not teacher-oriented

`LibraryLayout-BJGqMhZw.js` exposes the full library menu:

- Dashboard
- Catalog
- Circulation
- Reservations
- Members
- Fines & Fees
- Inventory
- Acquisition
- Reports

There is no teacher-scoped library workspace. If a teacher is given `LIBRARY`, they inherit the full module shell instead of a narrower classroom-book workflow.

### B5. There is no explicit teacher custody or teacher-to-student handoff workflow

The current library flow supports:

- direct issue to a member
- reservation
- return
- renew

What is missing for the requested workflow is an explicit chain of custody:

1. library issues hard-copy books to a teacher
2. teacher issues hard-copy books to students
3. the system can still tell whether the copy is with the library, with the teacher, or with the student
4. returns and reconciliation can be handled cleanly

Today the system can issue to one `LibraryMember`, but it does not model classroom custody as a first-class workflow.

---

## C. Finance Local Purchase and Local Supply Order

### C1. The current workflow is generic store-order approval, not dedicated LPO/LSO

The current persisted model is `StoreOrderRequest` plus `StoreOrderItem`.

It provides:

- `title`
- `description`
- `send_to`
- `status`
- `reviewed_by`
- `reviewed_at`
- `generated_expense`

It does not provide dedicated local purchase or local supply workflow concepts such as:

- LPO number
- LSO number
- supplier quotation or selected supplier
- quoted unit price snapshot
- delivery status and receiving checkpoints
- finance vs admin approval chain
- procurement document attachments

There is no dedicated `LocalPurchaseOrder` or `LocalSupplyOrder` object in the repo.

### C2. `send_to` is metadata, not a real approval boundary

`StoreOrderRequest.send_to` supports:

- `FINANCE`
- `ADMIN`
- `BOTH`

But backend review is not restricted by that field. The review endpoint does not enforce that only the intended office can approve the request.

### C3. Expense generation is under-modeled

`generate_expense()` currently creates an expense with:

- category `Store Purchase`
- vendor `Store Department`

This loses supplier fidelity and does not match a real procurement ledger flow.

### C4. Order valuation depends on current stock item cost, not a stored procurement price

`DjangoStoreRepository.calculate_order_total()` multiplies:

- `quantity_approved` or `quantity_requested`
- current `StoreItem.cost_price`

That means totals are not frozen to the approved procurement value at review time.

If:

- the request uses a free-text item
- the item has no linked `StoreItem`
- the `StoreItem.cost_price` changes later

then the generated expense can be wrong or incomplete.

### C5. The finance UI expects pricing detail that the serializer does not provide

`FinanceStoreRequestsPage-t8BwopMh.js` estimates total cost using `item.cost_price`, but `StoreOrderItemSerializer` does not expose any cost-price field.

So the UI is attempting to display cost-based calculations without a reliable payload contract.

This is both a data-contract bug and an auditability gap.

---

## D. Secretary Role Definition

### D1. `SECRETARY` is not a seeded RBAC role

The built-in role catalog in `school/role_scope.py` and `school/models.py` includes roles like:

- `REGISTRAR`
- `TEACHER`
- `LIBRARIAN`

but does not include:

- `SECRETARY`

### D2. The product already talks about a school secretary

The repo already references secretary behavior in multiple places:

- `School Secretary` appears in seeded staff data
- exam paper upload UI says papers are forwarded to secretary for printing
- staff UI labels include `School Secretary`

So the business concept exists in the product, but the system role does not.

### D3. HR identity logic recognizes secretary as staff category, but cannot assign a secretary account role

`hr/identity.py` classifies titles containing `SECRETARY` as support staff, but `suggest_account_role_name()` has no `SECRETARY` mapping.

Because supported role names come from the seeded role catalog, HR validation and provisioning reject unsupported role names.

Effectively:

- "School Secretary" exists as a position title
- but not as a valid account role

This is a clear provisioning gap.

---

## Overall Assessment

### What is already usable

- module baselines and module assignment plumbing exist
- finance approval requests exist
- store request and expense generation scaffolding exists
- library member sync and basic circulation exist
- staff onboarding already supports role suggestion and provisioning

### What is not ready

- role-scoped approvals visibility
- role-scoped approvals authority
- teacher classroom-book handoff flow
- real LPO/LSO procurement model
- secretary as a first-class system role

---

## Recommended Direction

1. Make approvals visibility backend-driven and deny-by-default.
2. Separate "can see approval queue" from "can take approval action."
3. Add a teacher-specific library circulation workflow instead of handing teachers the full librarian module.
4. Treat local purchase and local supply order as explicit finance/procurement workflows, not just store requests.
5. Add `SECRETARY` as a real role with scope, default permissions, onboarding support, and dashboard/tab behavior.

---

## Suggested Implementation Order

1. Approval scope matrix and tab cleanup
2. Secretary role definition and provisioning
3. Teacher library custody and student issuance flow
4. Local purchase/local supply order redesign and implementation

This order reduces the highest cross-cutting access-control risk first, then fixes the missing role, then addresses the operational workflows that depend on correct scope boundaries.
