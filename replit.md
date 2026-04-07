# RynatySchool SmartCampus

## Overview
A comprehensive School Management System built with Django 4.2 backend serving a pre-built React/Vite frontend. Supports multi-tenant schools via `django-tenants`, JWT authentication, PostgreSQL, and 28+ integrated modules.

## Architecture
- **Backend**: Django 4.2.7 (Python 3.11) in `/home/runner/workspace/sms-backend/`
- **Frontend**: Pre-built React/Vite SPA in `sms-backend/frontend_build/`, served by WhiteNoise
- **Database**: PostgreSQL with django-tenants for multi-tenancy
- **Port**: 8080 (`$PORT` env var)
- **Routing**: Public URLs handled by `config/public_urls.py`; tenant-scoped API URLs at `/api/` via `config/urls.py` with `X-Tenant-ID` header for tenant resolution

## Starting the Application
The workflow "Start application" runs `bash /home/runner/workspace/sms-backend/start.sh` which:
1. Runs `migrate_schemas --shared` (shared/public schema migrations)
2. Runs `migrate_schemas` (all tenant schema migrations)
3. Collects static files
4. Starts Django development server on port 8080
5. Bootstraps demo tenant data in the background (if `BOOTSTRAP_DEMO_DATA=true`)

## Demo Access
- **URL**: Root path `/`
- **School ID**: `demo_school`

### Admin Account
- **Username**: `admin` | **Password**: `admin123`
- **Role**: TENANT_SUPER_ADMIN — full access to all 28 modules

### Parent Accounts (20 accounts)
- **Usernames**: `parent.stm2025001` through `parent.stm2025020`
- **Password**: `parent123`
- **Role**: PARENT — access to Parent Portal (child's grades, attendance, fees, etc.)
- Each parent is linked to a student (stm2025001–stm2025020)

### Student Accounts (10 accounts)
- **Usernames**: `stm2025011` through `stm2025020` (admission numbers)
- **Password**: `student123`
- **Role**: STUDENT — access to Student Portal (grades, attendance, library, e-learning, etc.)

### Teacher Accounts (12 accounts)
- **Usernames**: `samuel.otieno`, `grace.wanjiku`, `david.mwangi`, `faith.njoroge`, `peter.kamau`, `mary.achieng`, `john.mutua`, `susan.wafula`, `james.simiyu`, `esther.kimani`, `george.ndegwa`, `alice.chebet`
- **Password**: `teacher123`
- **Role**: TEACHER — access to Teacher Portal (attendance, gradebook, timetable, resources)

## API Authentication Flow
1. `POST /api/auth/login/` with `X-Tenant-ID: demo_school` header → returns `access` + `refresh` JWT tokens
2. All subsequent requests include `Authorization: Bearer <access>` + `X-Tenant-ID: demo_school`
3. `POST /api/auth/logout/` with refresh token body → blacklists refresh token
4. `GET /api/auth/me/` → returns current user info + role

## Environment Variables
- `DATABASE_URL` — PostgreSQL connection string (managed by Replit)
- `SESSION_SECRET` — Django secret key
- `DJANGO_DEBUG` — Set to `true` in development
- `DJANGO_ALLOWED_HOSTS` — Comma-separated allowed hosts
- `BOOTSTRAP_DEMO_DATA` — Set to `true` to seed demo tenant on startup
- `DEMO_SCHEMA_NAME` — Demo tenant schema name (default: `demo_school`)
- `DEMO_SCHOOL_NAME` — Demo school display name
- `DEMO_TENANT_DOMAIN` — Demo tenant domain (default: `demo.localhost`)
- `DEMO_ADMIN_USER` / `DEMO_ADMIN_PASS` / `DEMO_ADMIN_EMAIL` — Demo admin credentials
- `PYTHONPATH` — Set to `/home/runner/workspace/sms-backend`

## Key Files
- `sms-backend/start.sh` — Startup script for migrations + server
- `sms-backend/config/settings.py` — Django settings
- `sms-backend/config/urls.py` — Tenant URL configuration
- `sms-backend/config/public_urls.py` — Public schema URL configuration
- `sms-backend/school/urls.py` — School API routes (auth, modules, etc.)
- `sms-backend/school/views.py` — Core views incl. LogoutView, SmartCampusTokenObtainPairView
- `sms-backend/school/management/commands/seed_kenya_school.py` — Full seed command
- `sms-backend/school/management/commands/reset_demo.py` — Demo data reset command
- `sms-backend/manage.py` — Django management entry point
- `sms-backend/requirements.txt` — Python dependencies
- `sms-backend/frontend_build/` — Pre-built React SPA assets

## Modules (28+ integrated)
academics, admissions, alumni, assets, cafeteria, clients (multi-tenant), clockin, communication, curriculum, elearning, examinations, hostel, HR, library, maintenance, parent portal, PTM, reporting, school (core), sessions, sports, staff management, timetable, token management, transport, visitor management

## Known Fixes Applied
- Patched `rest_framework_simplejwt/__init__.py` to use `importlib.metadata` fallback instead of deprecated `pkg_resources`
- Python 3.11 installed via nix package manager
- Fixed `reset_demo.py` FK ordering (elearning/PTM/cafeteria/hostel/transport/timetable/curriculum deleted BEFORE Term)
- Parent users (`parent.stm2025001–020`) created with PARENT role via UserProfile in seed
- Student login accounts (`stm2025011–020`) created with STUDENT role; cleaned up on reset
- `LogoutView` added to `school/views.py` — blacklists JWT refresh token at `POST /api/auth/logout/`
- `reset_demo.py` cleans up both `parent.*` and `stm*` prefixed users on reset
