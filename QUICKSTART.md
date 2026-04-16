# RynatySchool SmartCampus — Quick Start Guide

## Overview

RynatySchool SmartCampus is a Django 4.2 multi-tenant school management system with a pre-built React/Vite frontend. It supports 28+ modules across 7 user portals for Grade 7–10 CBE curriculum.

**Production domain:** `rynatyschool.app`  
**Demo tenant:** `demo_school` (schema: `demo_school`)  
**Stack:** Python 3.11, Django 4.2, PostgreSQL 15, DRF 3.15, JWT auth, django-tenants

---

## Prerequisites

- Python 3.11+
- PostgreSQL 15+ (with `demo_school` tenant schema already seeded)
- Node.js 18+ (frontend is pre-built; only needed for rebuilds)
- `pip`, `pnpm`

---

## Local Setup

```bash
# 1. Clone and enter the backend
cd sms-backend

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Set environment variables
export DATABASE_URL="postgresql://user:password@localhost:5432/smartcampus"
export SESSION_SECRET="your-secret-key"

# 4. Start the API server
bash start.sh
```

The `start.sh` script runs Django on `PORT` (default 8000) with `--noreload` and serves the pre-built React frontend from `sms-backend/frontend_build/`.

---

## Demo Credentials

All users belong to the `demo_school` tenant. Authenticate via:
```
POST /api/auth/token/
{"username": "<user>", "password": "<pass>"}
```

| Role | Username | Password | Portal |
|------|----------|----------|--------|
| Tenant Super Admin | `Riqs#.` | `Ointment.54.#` | Admin (`/`) |
| Principal | `principal` | `principal123` | Admin (`/`) |
| Accountant | `accountant` | `accountant123` | Admin (`/`) |
| Bursar | `bursar` | `bursar123` | Admin (`/`) |
| Teacher | _(see seed data)_ | `teacher123` | Teacher Portal |
| Student | `stm2025001` | `student123` | Student Portal |
| Parent | `parent.stm2025001` | `parent123` | Parent Portal (`portal_type: "parent"`) |

### Token Usage
```bash
TOKEN=$(curl -s -X POST /api/auth/token/ -d '{"username":"principal","password":"principal123"}' | jq -r .access)
curl -H "Authorization: Bearer $TOKEN" /api/finance/invoices/
```

---

## User Portals

| Portal | Base URL | Login Role |
|--------|----------|-----------|
| Admin/Staff Dashboard | `/` (SPA) | ADMIN, PRINCIPAL, BURSAR, ACCOUNTANT, HOD, REGISTRAR |
| Parent Portal | `/api/parent-portal/` | Role `PARENT` |
| Student Portal | `/api/student-portal/` | Role `STUDENT` |
| Teacher Portal | `/api/teacher-portal/` | Role `TEACHER`, HOD |

---

## Key API Endpoints

### Authentication
```
POST   /api/auth/token/                    JWT login
POST   /api/auth/token/refresh/            Token refresh
GET    /api/auth/me/                       Current user info
```

### Finance Module
```
GET    /api/finance/invoices/              Invoice list (paginated)
GET    /api/finance/invoices/<id>/         Invoice detail
GET    /api/finance/payments/              Payment list
POST   /api/finance/payments/             Record payment
GET    /api/finance/fee-structures/        Fee structures
GET    /api/finance/write-offs/            Write-off requests
POST   /api/finance/write-offs/           Request write-off
PATCH  /api/finance/write-offs/<id>/approve/  Approve (Principal only)
GET    /api/finance/reversals/             Reversal requests
POST   /api/finance/reversals/            Request reversal
GET    /api/finance/adjustments/           Adjustments
POST   /api/finance/adjustments/          Create adjustment
GET    /api/finance/dashboard/             Finance KPIs
GET    /api/finance/reports/statement/     Fee statement PDF
```

### M-Pesa Payments
```
POST   /api/finance/mpesa/push/            Initiate STK Push (admin)
GET    /api/finance/mpesa/status/          Poll transaction status
POST   /api/finance/mpesa/callback/        Safaricom callback (public, no auth)
```

### Parent Portal
```
GET    /api/parent-portal/dashboard/        Dashboard KPIs
GET    /api/parent-portal/finance/summary/  Fee summary
GET    /api/parent-portal/finance/invoices/ Invoices list
GET    /api/parent-portal/finance/payments/ Payment history
POST   /api/parent-portal/finance/pay/     Initiate M-Pesa or record payment
GET    /api/parent-portal/finance/mpesa-status/  Poll M-Pesa status
GET    /api/parent-portal/academics/grades/ Child's grades
GET    /api/parent-portal/attendance/summary/ Attendance summary
GET    /api/parent-portal/profile/          Profile (GET/PATCH)
POST   /api/parent-portal/profile/change-password/ Change password
```

### Student Portal
```
GET    /api/student-portal/dashboard/       Dashboard
GET    /api/student-portal/my-invoices/     Student's invoices
GET    /api/student-portal/my-payments/     Payment history
POST   /api/student-portal/finance/pay/     Initiate M-Pesa STK Push
GET    /api/student-portal/finance/mpesa-status/ Poll M-Pesa status
GET    /api/student-portal/profile/         Profile (GET/PATCH)
GET    /api/student-portal/academics/grades/ Grades
GET    /api/student-portal/attendance/summary/ Attendance
```

### Teacher Portal
```
GET    /api/teacher-portal/dashboard/       Dashboard
GET    /api/teacher-portal/classes/         Assigned classes + rosters
GET    /api/teacher-portal/gradebook/       Gradebook
POST   /api/teacher-portal/gradebook/       Save grades
GET    /api/teacher-portal/attendance/      Attendance view
POST   /api/teacher-portal/attendance/      Save attendance
GET    /api/teacher-portal/resources/       Course materials
POST   /api/teacher-portal/resources/       Upload resource
GET    /api/teacher-portal/timetable/       Timetable
GET    /api/teacher-portal/profile/         Profile (GET/PATCH)
```

---

## Finance Approval Workflow

The finance module has a multi-tier approval system:

```
1. Write-Offs:
   Accountant (creates) → PRINCIPAL / DEPUTY_PRINCIPAL (approves)
   URL: POST /api/finance/write-offs/  → PATCH /api/finance/write-offs/<id>/approve/

2. Payment Reversals:
   Accountant (creates) → PRINCIPAL / DEPUTY_PRINCIPAL (approves)

3. Adjustments:
   Accountant (creates) → PRINCIPAL / DEPUTY_PRINCIPAL (approves)

4. Budget Overrides:
   HOD (creates) → PRINCIPAL (approves)
```

**Who can approve:** PRINCIPAL, DEPUTY_PRINCIPAL only (BURSAR cannot approve)  
**ApprovalsHub:** `/api/finance/approvals/` — shows pending items per role

---

## M-Pesa Integration

### Configuration (per tenant)
Set via `TenantSettings` (key: `integrations.mpesa`):
```json
{
  "enabled": true,
  "consumer_key": "from Daraja portal",
  "consumer_secret": "from Daraja portal",
  "shortcode": "174379",
  "passkey": "from Daraja portal",
  "environment": "sandbox"
}
```

### Sandbox Test Credentials (Safaricom)
```
Consumer Key: bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919
Consumer Secret: aKE0mz9ouUoRGNVEekDvnOlRqCGIBvnSc6ClyxGa1MzsMBDsYIAMEJZ
Shortcode: 174379
Passkey: bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919
Test Phone: 254708374149
```

### STK Push Flow
```
1. POST /api/parent-portal/finance/pay/
   Body: {"amount": 5000, "payment_method": "mpesa", "phone": "0712345678"}

2. Safaricom sends STK prompt to phone
3. User enters M-Pesa PIN
4. Safaricom POSTs to /api/finance/mpesa/callback/
5. System creates Payment + allocates to invoice
6. Poll: GET /api/parent-portal/finance/mpesa-status/?checkout_request_id=<id>
```

---

## Module Reference

| Module | Key | Admin URL |
|--------|-----|-----------|
| Finance | `FINANCE` | `/api/finance/` |
| Students | `STUDENTS` | `/api/students/` |
| Academics | `ACADEMICS` | `/api/academics/` |
| Attendance | `ATTENDANCE` | `/api/attendance/` |
| Timetable | `TIMETABLE` | `/api/timetable/` |
| Cafeteria | `CAFETERIA` | `/api/cafeteria/` |
| Library | `LIBRARY` | `/api/library/` |
| Transport | `TRANSPORT` | `/api/transport/` |
| Health | `HEALTH` | `/api/health/` |
| E-Learning | `ELEARNING` | `/api/elearning/` |
| Communication | `COMMUNICATION` | `/api/communication/` |
| Parent Portal | `PARENT_PORTAL` | `/api/parent-portal/` |
| Student Portal | `STUDENT_PORTAL` | `/api/student-portal/` |
| Teacher Portal | `TEACHER_PORTAL` | `/api/teacher-portal/` |
| Admissions | `ADMISSIONS` | `/api/admissions/` |
| HR | `HR` | `/api/hr/` |
| Budget | `BUDGET` | `/api/budget/` |
| Transfers | `TRANSFERS` | `/api/transfers/` |
| Behaviour | `BEHAVIOUR` | `/api/behaviour/` |
| Exam | `EXAM` | `/api/exams/` |
| Inventory | `INVENTORY` | `/api/inventory/` |
| Procurement | `PROCUREMENT` | `/api/procurement/` |
| Hostel | `HOSTEL` | `/api/hostel/` |

---

## Running Migrations

```bash
cd sms-backend
python manage.py migrate_schemas --shared   # public schema
python manage.py migrate_schemas             # all tenant schemas
```

---

## Reference Material

See `sms-backend/mpesa_saas_reference/` for the enterprise M-Pesa reference implementation.
