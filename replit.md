# RynatySchool SmartCampus — Django Backend

## Overview
RynatySchool SmartCampus is a multi-tenant Django school management system designed for Kenyan secondary schools implementing the Competency-Based Education (CBE) curriculum for Grades 7-10. The project's vision is to provide a comprehensive, digital solution for school administration, academic management, and digital learning, accessible via the custom domain `rynatyschool.app`. It aims to streamline operations, enhance educational delivery, and support the CBE framework through integrated modules covering academics, admissions, library, finance, and more.

## User Preferences
I want iterative development.
I prefer detailed explanations.
Ask before making major changes.
Do not make changes to the `artifacts/mockup-sandbox/` folder.
Do not make changes to the `sms-backend/frontend_build/` folder.
Do not make changes to the `sms-backend/media/school_logos/rynaty-logo.png` file.

## System Architecture

### Core Architecture
The system employs a multi-tenancy architecture using `django-tenants`, where a public schema manages tenant information, and each school operates on its isolated schema for data privacy and scalability. The backend is built with Django 4.2 and Django REST Framework, utilizing PostgreSQL as the database and JWT (SimpleJWT) for authentication. A pre-built React/Vite SPA serves as the frontend, delivered by Django.

### CBE Configuration
The system is tailored for Kenyan CBE Grades 7-10, supporting specific grading schemes (Exceeding, Meeting, Approaching, Below Expectations) and managing 19 defined CBE subjects.

### Modules
The system is composed of 28 distinct modules, including: academics, admissions, alumni, assets, cafeteria, clockin, communication, curriculum, elearning, examinations, hostel, hr, library, maintenance, parent_portal, ptm, reporting, school, sports, staff_mgmt, timetable, token_blacklist, transport, visitor_mgmt, and client/auth modules.

### Authentication and Security
Security features include:
- Non-superuser school administrators.
- JWT cross-schema guard preventing platform admin tokens from being used on school subdomains.
- A dedicated platform admin login endpoint (`/platform/auth/login/`) operating on the public schema.
- `IsGlobalSuperAdmin` guard for all platform API routes.

### Library Enhancements
The library module supports bulk operations for adding books and copies, unique accession number generation, physical circulation desk lookup, and features for reporting lost/damaged books, managing repairs, and sending bulk overdue reminders.

### Super Admin Platform Layer
A comprehensive platform layer for super administrators includes:
- Standardized error response format across all APIs.
- Structured invoice number generation (`SC-YYYY-NNNN`).
- Platform email notification service for provisioning, trial warnings, expiry, suspension, reactivation, invoice issuance, payment receipts, and password resets.
- Automated trial expiry management, including suspension and email notifications, protected by a concurrency lock.

### Enterprise M-Pesa / Finance Infrastructure
A robust finance system incorporates:
- **New Models**: `Wallet`, `LedgerEntry`, `LedgerReconciliation`, `FraudAlert`, `RiskScoreLog`, `FraudWhitelist`, `FinanceAuditLog` (with tamper-proof SHA-256 hash chain), and `RevenueLog` (for cross-tenant platform revenue).
- **Service Engines**: `FraudDetectionEngine` (velocity checks, large amounts, new-user watch, duplicate receipt prevention), `ComplianceEngine` (KYC, frozen wallet, large transaction reporting), and `BillingEngine` (calculates transaction fees and logs revenue).
- **API Endpoints**: Dedicated finance APIs for tenant-level wallet management, ledger access, fraud alerts, and audit logs. Platform-level APIs for cross-tenant revenue, fraud overview, and audit/wallet summaries.
- **Management Commands**: `reconcile_transactions`, `check_pending_payments`, `run_compliance_checks`, `run_fraud_monitor` for automated financial operations.
- **M-Pesa Integration**: Endpoint (`/api/finance/mpesa/test-connection/`) to test Daraja OAuth handshake using provided credentials or saved `TenantSettings`.

## External Dependencies
- **Django**: Web framework
- **Django REST Framework**: For building APIs
- **django-tenants**: For multi-tenancy management
- **PostgreSQL**: Database system
- **SimpleJWT**: For JSON Web Token authentication
- **React**: Frontend library (for mockup sandbox)
- **Vite**: Frontend build tool (for mockup sandbox)
- **requests**: Python HTTP library (for M-Pesa integration)
- **Resend**: Email service (fallback to Django email backend)