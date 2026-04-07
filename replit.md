# RynatySchool SmartCampus

## Overview
A comprehensive School Management System built with Django 4.2 backend serving a pre-built React/Vite frontend. Supports multi-tenant schools via `django-tenants`, JWT authentication, PostgreSQL, and 28+ integrated modules.

## Architecture
- **Backend**: Django 4.2.7 (Python 3.11) in `/home/runner/workspace/sms-backend/`
- **Frontend**: Pre-built React/Vite SPA in `sms-backend/frontend_build/`, served by WhiteNoise
- **Database**: PostgreSQL with django-tenants for multi-tenancy
- **Port**: 8080 (`$PORT` env var)
- **Routing**: All requests go to Django at `/`. The Django URL conf separates public vs tenant routes.

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
- **Admin Username**: `admin`
- **Admin Password**: `admin123`
- **Admin Email**: `admin@demo.school`

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
- `sms-backend/config/urls.py` — Root URL configuration
- `sms-backend/manage.py` — Django management entry point
- `sms-backend/requirements.txt` — Python dependencies
- `sms-backend/frontend_build/` — Pre-built React SPA assets

## Modules (28+ integrated)
academics, admissions, alumni, assets, cafeteria, clients (multi-tenant), clockin, communication, curriculum, elearning, examinations, hostel, HR, library, maintenance, parent portal, PTM, reporting, school (core), sessions, sports, staff management, timetable, token management, transport, visitor management

## Known Fixes Applied
- Patched `rest_framework_simplejwt/__init__.py` to use `importlib.metadata` fallback instead of deprecated `pkg_resources`
- Python 3.11 installed via nix package manager
