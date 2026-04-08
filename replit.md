# RynatySchool SmartCampus — Django Backend

## Overview
Multi-tenant Django 4.2 school management system for Kenyan secondary schools (CBE — Competency-Based Education, Grades 7-10). Custom domain: `rynatyschool.app`.

## Artifacts

### API Server (`/`)
- **Dir**: `artifacts/api-server/` (runs from `sms-backend/`)
- **Stack**: Django 4.2, Django REST Framework, django-tenants, PostgreSQL, JWT (SimpleJWT)
- **Start**: `bash /home/runner/workspace/sms-backend/start.sh`
- **Port**: `$PORT` (default 8080)

### Canvas / Mockup Sandbox (`/__mockup`)
- **Dir**: `artifacts/mockup-sandbox/`
- **Stack**: React + Vite

## Architecture
- **Multi-tenancy**: `django-tenants` — public schema for tenant management, per-school schemas for data
- **Demo tenant**: schema `demo_school` (bootstrapped via `BOOTSTRAP_DEMO_DATA=true`)
- **Frontend**: Pre-built React/Vite SPA in `sms-backend/frontend_build/` (served by Django)

## CBE Configuration (Kenya Grade 7-10)
- **Grades**: Grade 7, Grade 8, Grade 9, Grade 10 (replacing Form 1-4)
- **Streams**: East, West, North, South (16 class slots)
- **Grading Scheme**: "CBE Standard" with 4 bands:
  - EE: 86-100 (Exceeding Expectations, 4.0 pts)
  - ME: 61-85 (Meeting Expectations, 3.0 pts)
  - AE: 41-60 (Approaching Expectations, 2.0 pts)
  - BE: 0-40 (Below Expectations, 1.0 pts)
- **19 CBE Subjects**: Mathematics, English, Kiswahili, Integrated Science, Social Studies, Biology, Chemistry, Physics, History & Government, Geography, CRE, Business Studies, Agriculture, Computer Studies, Home Science, Creative Arts & Sports, Pre-Technical Studies, Life Skills Education, Physical Education, Religious Education

## 28 Modules
academics, admissions, alumni, assets, cafeteria, clockin, communication, curriculum, elearning, examinations, hostel, hr, library, maintenance, parent_portal, ptm, reporting, school, sports, staff_mgmt, timetable, token_blacklist, transport, visitor_mgmt + clients/auth

## Key Management Commands
| Command | Purpose |
|---|---|
| `seed_demo` | Create demo tenant + admin |
| `seed_kenya_school` | Full CBE school data (students, staff, fees, exams…) |
| `seed_curriculum_templates` | 20 CBE 12-week schemes of work |
| `seed_staff_users` | 19 staff role accounts |
| `seed_portal_accounts` | Student/parent portal logins |
| `seed_extra_data` | 25+ records per module (hostel, sports, alumni…) |
| `seed_digital_resources` | KICD digital textbooks + Harvard open courses |

## Digital Learning Resources
`library.LibraryResource.digital_url` (field added via migration `0004`) stores access URLs.

### Library — 47 KICD Digital Textbooks
- All 19 CBE subjects, Grades 7-10
- KICD OER links: `https://kicd.ac.ke/digital-library/<subject-grade>/`
- KICD Assessment Handbook, CBE Curriculum Design Guide
- Harvard CS50 series (5 volumes) in "Harvard Open Learning" category

### E-Learning — 13 Open Courses (85 live-linked materials)
- **Harvard CS50x** — Introduction to Computer Science (9 video/PDF materials)
- **Harvard CS50P** — Python Programming (9 lecture videos)
- **Harvard CS50 AI** — Artificial Intelligence with Python (6 materials)
- **Harvard CS50T** — Understanding Technology (6 materials)
- **CBE Mathematics** G7 & G9 — Khan Academy aligned video lessons
- **CBE Biology, Chemistry, Physics** G9 — Khan Academy video lessons
- **CBE English, History & Government, Geography, Agriculture, Business Studies** — open video/PDF lessons
- All materials link to `link_url` on `elearning.CourseMaterial`

## Demo Credentials
| Role | Username | Password |
|---|---|---|
| Admin | admin | admin123 |
| Principal | principal | principal123 |
| Deputy Principal | deputy | deputy123 |
| Bursar | bursar | bursar123 |
| Accountant | accountant | accountant123 |
| HR Officer | hr | hr123 |
| Registrar | registrar | registrar123 |
| Librarian | librarian | librarian123 |
| Teachers | teacher1-5 | teacher123 |
| Nurse | nurse | nurse123 |
| HOD Math / Science | hod.math / hod.science | hod123 |
| Store Clerk | store_clerk | store123 |
| Alumni Coordinator | alumnicoord | alumni123 |
| Students | admission number | (student portal) |
| Parents | guardian-derived | parent123 |

## Portal Fixes (completed)
- **Student E-Learning**: `StudentELearningView` now includes open courses (`school_class=None`) — previously only matched class-specific content. Now returns 88+ materials.
- **Student Report Cards**: `StudentReportCardsView` maps old KNEC grades to CBE bands (B- → ME, C+ → AE, etc.) and is null-safe for term/academic_year.
- **Parent Assignments**: `ParentAssignmentsView` returns `[]` instead of 404 when no active enrollment found.
- **Parent Report Cards**: `ParentReportCardsView` also maps grades to CBE bands with null-safety.
- **Parent Library Lookup**: `_library_member_ids_for_child()` now uses `student` FK (OneToOne) + member_id fallback to correctly find `LibraryMember` records.
- **Assignments seeded**: 320 assignments across 32 classes (10 per class from 10 templates), 100 submissions for first 20 students.
- **School Profile / Logo**: `SchoolProfile` created with `logo = 'school_logos/rynaty-logo.png'`, `primary_color = '#10b981'`, `secondary_color = '#0d1117'`. Logo served at `/media/school_logos/rynaty-logo.png`. Seed command `_seed_school_profile()` ensures this is idempotent.
- **Logo file**: `sms-backend/media/school_logos/rynaty-logo.png` (copied from `attached_assets/`).

## Important Files
- `sms-backend/start.sh` — full bootstrap pipeline
- `sms-backend/school/management/commands/seed_kenya_school.py` — main seed (4400+ lines)
- `sms-backend/school/management/commands/seed_digital_resources.py` — KICD + Harvard resources
- `sms-backend/curriculum/management/commands/seed_curriculum_templates.py` — 20 CBE schemes
- `sms-backend/library/models.py` — includes `digital_url` field (migration 0004)
- `sms-backend/parent_portal/student_portal_views.py` — student portal views (elearning, report cards, assignments)
- `sms-backend/parent_portal/views.py` — parent portal views (report cards, assignments, library)
- `sms-backend/media/school_logos/rynaty-logo.png` — Rynaty logo (served at /media/)

## Notes
- f-strings: no backslashes inside expressions (Python 3.11)
- Migrations: always `--fake-initial` to avoid conflicts with existing tables
- All seed commands are fully idempotent (safe to re-run)
- Frontend JS minified files updated: KCSE/CBC → CBE throughout
- `_library_member_ids_for_child()` returns LibraryMember PKs (integer), not string member_ids
- Tenant domain: `demo.localhost` (local), public schema at `localhost`
