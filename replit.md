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

## Important Files
- `sms-backend/start.sh` — full bootstrap pipeline
- `sms-backend/school/management/commands/seed_kenya_school.py` — main seed (4000+ lines)
- `sms-backend/school/management/commands/seed_digital_resources.py` — KICD + Harvard resources
- `sms-backend/curriculum/management/commands/seed_curriculum_templates.py` — 20 CBE schemes
- `sms-backend/library/models.py` — includes `digital_url` field (migration 0004)

## Notes
- f-strings: no backslashes inside expressions (Python 3.11)
- Migrations: always `--fake-initial` to avoid conflicts with existing tables
- All seed commands are fully idempotent (safe to re-run)
- Frontend JS minified files updated: KCSE/CBC → CBE throughout
