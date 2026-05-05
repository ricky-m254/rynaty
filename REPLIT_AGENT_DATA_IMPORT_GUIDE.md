# Replit Agent Data Import Guide

## Objective

Use this guide whenever importing tenant data into RynatySchool SmartCampus.

The goal is not only to load records, but to make every enabled module operational:

1. Core reference data exists.
2. Student, parent, staff, and admin accounts work.
3. Cross-module links are created.
4. No enabled module is left empty by accident.
5. Derived module data is backfilled where the platform does not do it automatically.

If a module is enabled for a tenant, it must end the import in one of these states:

1. Populated with real imported data.
2. Populated with safe derived baseline data.
3. Explicitly marked as intentionally unused for that tenant in the final import report.

## Hard Rules

### 1. Do not use demo seeding for real tenant imports

`POST /api/school/seed/` and `python manage.py seed_kenya_school` are for sample/demo data, not production migration.

Use them only for:

- smoke testing
- demo tenants
- development verification

Do not mix demo seed data into a real tenant migration.

### 2. Always bootstrap tenant RBAC and modules first

Before importing business data, run:

```bash
python manage.py seed_roles --schema=<schema>
python manage.py seed_modules --schema=<schema>
python manage.py seed_default_permissions --schema=<schema> --assign-roles
python manage.py backfill_role_module_baselines --schema=<schema>
```

This ensures:

- roles exist
- module definitions exist
- default permissions exist
- baseline `UserModuleAssignment` rows are restored for scoped staff roles

### 3. Always dry-run CSV imports first

The built-in CSV import endpoints support preview validation. Use `validate_only=true` before committing.

Available built-in CSV import endpoints:

- `GET /api/settings/import/students/template/`
- `GET /api/settings/import/staff/template/`
- `GET /api/settings/import/fees/template/`
- `GET /api/settings/import/payments/template/`
- `POST /api/settings/import/students/`
- `POST /api/settings/import/staff/`
- `POST /api/settings/import/fees/`
- `POST /api/settings/import/payments/`

### 4. Do not assume the student CSV importer finishes the job

The current `StudentsBulkImportView` is not a complete tenant-onboarding pipeline.

Treat it as student row ingestion only.

Do not depend on it to make enrollments correct. Create and validate active `Enrollment` rows explicitly in a separate step.

After student import, you must still verify and, if needed, create:

- `Guardian` rows
- active `Enrollment` rows
- student auth users
- parent auth users
- `ParentStudentLink` rows
- library member sync
- finance assignments/invoices
- transport/hostel/library/student-life links

Important current limitation:

- the student import template includes `parent_name`, `parent_phone`, and `parent_email`
- the current importer does not persist those parent fields into `Guardian` or portal link records

Therefore, parent creation must be handled separately.

### 5. Do not rely on fallback parent matching

Parent portal access is correct only when explicit `ParentStudentLink` rows exist.

Do not treat name/email fallback matching as completion.

Definition of done for parent access:

- parent auth user exists
- `UserProfile.role = PARENT`
- parent can resolve at least one child via `ParentStudentLink`

### 6. Do not assume library sync covers all member types

`POST /api/library/members/sync/` currently auto-syncs:

- active students
- active HR employees
- active staff management members

It does **not** automatically create library members for:

- parents
- alumni
- external borrowers

If the tenant expects parents or alumni to borrow books, create those `LibraryMember` rows explicitly.

### 7. Do not assume alumni are auto-created unless enrollment is completed

Alumni auto-creation happens only when an `Enrollment` is saved with `status='Completed'`.

That is useful for lifecycle progression, but not enough for historical migrations.

If importing past graduates, create `AlumniProfile` rows explicitly.

## Canonical Import Order

Run imports in this order. Do not skip ahead.

### Phase 0. Tenant bootstrap

Required:

- tenant schema exists
- migrations applied
- `seed_roles`
- `seed_modules`
- `seed_default_permissions --assign-roles`
- `backfill_role_module_baselines`

Validate:

- all 28 module definitions exist
- enabled modules are correct for the tenant
- school admin can log in

### Phase 1. Foundation reference data

Create or verify:

- `SchoolProfile`
- academic years
- terms
- grade levels
- school classes
- departments
- subjects
- subject mappings

Without this phase, later imports will break or create unusable records.

### Phase 2. People and identity roots

Import or create:

- staff users
- HR employees
- staff management members
- students
- guardians
- active enrollments
- teacher assignments where applicable

This phase is the root for almost every module.

### Phase 3. Access and portal readiness

Run:

```bash
python manage.py seed_portal_accounts --schema_name=<schema>
```

Then verify:

- every active student has a Django auth user
- each student user has `UserProfile(role=STUDENT, admission_number=<student admission number>)`
- every active guardian has a parent auth user
- each parent user has `UserProfile(role=PARENT, phone=guardian.phone when available)`
- every parent-child relation has `ParentStudentLink`

If the import created new staff users after RBAC backfill, run:

```bash
python manage.py backfill_role_module_baselines --schema=<schema>
```

again.

### Phase 4. Library member readiness

Run:

`POST /api/library/members/sync/`

This ensures:

- active students become `LibraryMember(member_type='Student')`
- active staff become `LibraryMember(member_type='Staff')`

Then manually create additional member types if required:

- parents
- alumni
- external members

### Phase 5. Finance core

Import or create:

- fee structures
- fee assignments
- invoices
- invoice line items
- payments
- payment allocations
- chart of accounts
- vote heads if finance reporting is enabled

Use built-in imports where possible:

- fees via `POST /api/settings/import/fees/`
- payments via `POST /api/settings/import/payments/`

Do not import payments before the matching students exist.

### Phase 6. Academic delivery

Import or create:

- attendance records
- behavior incidents
- assessments
- assessment grades
- term results
- report cards
- timetable slots
- examination sessions/papers/results
- curriculum schemes/lessons/resources
- e-learning courses/materials/quizzes
- assignments and submissions

### Phase 7. Operational modules

Import or create as applicable:

- library resources, copies, circulation rules, borrowings, fines, reservations
- transport vehicles, routes, stops, student assignments
- hostel dormitories, bed spaces, allocations, attendance, leave
- dispensary stock, visits, prescriptions, records
- assets, assignments, depreciation, warranties, maintenance
- store categories, items, opening balances, transactions
- cafeteria meal plans, menus, enrollments, logs, payments
- visitor management logs and authorized pickups
- maintenance requests and checklists
- clock-in devices, shifts, person registry, attendance events

### Phase 8. Engagement modules

Import or create:

- communication announcements/messages/notifications
- PTM sessions, slots, bookings
- sports teams/clubs/tournaments/awards
- alumni profiles, events, attendees, mentorships, donations

### Phase 9. Analytics and reporting verification

Analytics should not be imported first. It should become meaningful after the upstream modules are populated.

Final validation must confirm dashboards are not empty because of missing source records.

## Module Readiness Matrix

Use this as the minimum checklist per module.

| Module key | Minimum required data |
| --- | --- |
| `CORE` | `SchoolProfile`, roles, modules, admin user, tenant settings |
| `STUDENTS` | students, guardians, active enrollments, student accounts |
| `ADMISSIONS` | inquiries/applications, review pipeline, admissions decisions, enrollment outcomes |
| `FINANCE` | fee structures, invoices, payments, allocations, finance settings, chart/vote-head data where used |
| `ACADEMICS` | academic year, terms, classes, subjects, mappings, attendance, assessments, grades, report cards |
| `HR` | employees, departments, leave/payroll/compliance data as applicable |
| `STAFF` | staff directory users, staff management member records, teacher/staff role assignments |
| `PARENTS` | parent auth users, `ParentStudentLink`, guardian contact fidelity, parent-facing communication/finance visibility |
| `LIBRARY` | categories, resources, copies, circulation rules, members, transactions or at least borrowable catalog inventory |
| `ASSETS` | asset categories, asset register, assignments, depreciation/maintenance/warranty rows where relevant |
| `COMMUNICATION` | messages, announcements, notifications, channel preferences/templates where used |
| `REPORTING` | underlying student/finance/academic data present so reports are meaningful |
| `STORE` | categories, inventory items, stock levels/opening balances, suppliers or transactions |
| `DISPENSARY` | medical stock, visits, prescriptions, health records as applicable |
| `TRANSPORT` | vehicles, routes, route stops, student assignments, incidents if historical data exists |
| `VISITOR_MGMT` | visitor records, sign-ins, pickups/authorizations |
| `EXAMINATIONS` | exam sessions, papers, grades/results, setters/seating if the school uses them |
| `ALUMNI` | alumni profiles at minimum; ideally events, attendees, mentorship, donations |
| `HOSTEL` | dormitories, bed spaces, allocations, attendance, leave |
| `PTM` | sessions, time slots, bookings |
| `SPORTS` | clubs/teams, participation, tournaments, awards |
| `CAFETERIA` | meal plans, menus, student meal enrollments/logs/payments as applicable |
| `CURRICULUM` | schemes, lesson plans, curriculum resources, syllabus/topic coverage |
| `MAINTENANCE` | request categories, requests, work items/checklists |
| `ELEARNING` | courses, course materials, quizzes/attempts where available |
| `ANALYTICS` | enough upstream module data to produce non-empty KPIs |
| `CLOCKIN` | devices, shifts, person registry, attendance events |
| `TIMETABLE` | timetable slots tied to class/teacher/subject context |

## Student, Parent, Library, and Alumni Rules

### Student accounts

Every active student must end with:

- `auth.User.username == student.admission_number`
- active user
- `UserProfile.role = STUDENT`
- `UserProfile.admission_number = student.admission_number`

Student portal resolution depends on either:

- `UserProfile.admission_number`, or
- username matching admission number

Do not leave student accounts partially linked.

### Parent accounts

Every active guardian must end with:

- active parent auth user
- `UserProfile.role = PARENT`
- phone carried into the profile when available
- `ParentStudentLink(parent_user, student, guardian)` rows

Default password behavior from the management command currently uses `parent123`.

If this is a production tenant, force an immediate credential reset after migration.

### Library

For library readiness, do all of the following:

1. import library catalog
2. import or create resource copies
3. create circulation rules
4. sync student and staff members
5. manually create alumni/parent members if the school uses them
6. import outstanding borrowings/fines/reservations if historical circulation matters

Teacher classroom library flow additionally requires:

- teacher user
- teacher staff/employee linkage
- class assignment access
- synced staff library membership
- eligible students with active enrollments

### Alumni

There are two valid alumni paths:

1. lifecycle-driven:
   completed enrollments create alumni automatically
2. historical migration:
   import `AlumniProfile` rows directly

If alumni should also appear in library workflows, create matching `LibraryMember(member_type='Alumni')` rows explicitly.

## Safe Derivation Policy

When the source system does not contain data for some enabled modules, use this rule:

### Safe to derive or generate baseline records

- module settings
- library categories and circulation rules
- timetable slot skeletons
- curriculum shells
- sports club/team shells
- maintenance categories
- visitor reason/category lists
- cafeteria menus/meal-plan shells
- transport route metadata

### Do not invent without explicit approval

- payments
- invoice balances
- payroll
- medical history
- discipline incidents
- exam results
- alumni donations
- legal identity or guardian contacts

If real data is missing for these high-risk areas, report the gap instead of fabricating it.

## Recommended Execution Algorithm For The Replit Agent

1. Identify tenant schema and enabled modules.
2. Run tenant bootstrap commands.
3. Load source files and classify them into: foundation, people, finance, academics, operations, engagement.
4. Create foundation reference data first.
5. Import staff and students.
6. Create guardians explicitly.
7. Create active enrollments explicitly.
8. Run `seed_portal_accounts`.
9. Re-run role baseline backfill if new staff users were created.
10. Run library member sync.
11. Import finance structures and then payments.
12. Import academics and operations data.
13. Import alumni, PTM, sports, and communication data.
14. Validate each enabled module against the readiness matrix.
15. Produce a final import report listing:
   - records created
   - records updated
   - records skipped
   - modules fully ready
   - modules intentionally unused
   - modules blocked by missing source data

## Mandatory Validation Checklist

Before declaring success, verify all of the following:

### Identity and portal checks

- every active student resolves through the student portal mapping
- every active parent resolves at least one child through `ParentStudentLink`
- no duplicate admission numbers
- no orphaned active guardians without parent links

### Library checks

- `LibraryResource` count > 0 if library module is enabled
- `ResourceCopy` count > 0 if library module is enabled
- student/staff library members exist after sync
- any required parent/alumni borrowers were created manually

### Finance checks

- fee structures exist
- invoices exist for imported fee-paying students
- payments reference valid students
- no duplicate payment reference numbers

### Academics checks

- classes exist
- active enrollments exist
- subjects exist
- timetable or assessment/report data exists if those modules are enabled

### Alumni checks

- alumni profiles exist if alumni module is enabled
- if historical graduates were part of the migration, they are not waiting on enrollment completion signals

### Module readiness checks

- no enabled module dashboard is blank because a dependency was skipped
- any intentionally unused enabled module is called out in the report

## Useful References In This Repo

- module catalog: `sms-backend/school/management/commands/seed_modules.py`
- role catalog: `sms-backend/school/management/commands/seed_roles.py`
- default permissions: `sms-backend/school/management/commands/seed_default_permissions.py`
- baseline module backfill: `sms-backend/school/management/commands/backfill_role_module_baselines.py`
- portal account creation: `sms-backend/school/management/commands/seed_portal_accounts.py`
- sample full-tenant seeding order: `sms-backend/school/management/commands/seed_kenya_school.py`
- student/staff/fees/payments CSV import endpoints: `sms-backend/school/views.py`
- library member sync and circulation: `sms-backend/library/views.py`
- teacher/student library custody helpers: `sms-backend/library/classroom_custody.py`
- parent-child link model: `sms-backend/parent_portal/models.py`
- alumni auto-create signal: `sms-backend/alumni/signals.py`

## Final Instruction To The Agent

Do not stop after "data imported successfully".

The import is only complete when:

1. accounts are created
2. links are backfilled
3. library members are synced
4. alumni are present where expected
5. every enabled module is either populated, safely derived, or explicitly reported as intentionally unused
