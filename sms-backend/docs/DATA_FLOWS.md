# RynatySchool SmartCampus — Permitted External Data Flows

**Owner:** Platform Engineering  
**Last reviewed:** 2026-04-16  
**Status:** Active register — update this file whenever a new external integration is added or removed.

---

## Purpose

This document is the authoritative register of all data that leaves the SmartCampus backend and reaches an external system (cloud API, on-premises hardware, or operator-configured webhook).  It exists to:

- Verify that every outbound flow is necessary for a stated processing purpose.
- Confirm that each flow is contractually governed (Terms of Service, Data Processing Agreement, or equivalent).
- Give developers and auditors a single source of truth before enabling a new integration.

Every new external integration **must** be registered here and reviewed against the school's Privacy Notice before it is enabled in production.

---

## 1  Active Outbound Flows

### 1.1  M-Pesa / Safaricom Daraja 2.0

| Attribute | Detail |
|-----------|--------|
| **Purpose** | Mobile-money fee collection (STK Push) |
| **Trigger** | School admin or parent initiates a fee payment |
| **Endpoint** | `https://api.safaricom.co.ke` (production) · `https://sandbox.safaricom.co.ke` (sandbox) |
| **Data sent** | Normalised phone number (E.164, e.g. `2547xxxxxxxx`), amount (KES integer), account reference (max 20 chars — fee invoice reference), transaction description (max 13 chars), business shortcode |
| **Data received** | `CheckoutRequestID`, `MerchantRequestID`, response description, customer message |
| **Callback received** | M-Pesa receipt number, phone, amount, transaction date (via the school's own callback URL — Safaricom calls back inbound) |
| **Data NOT sent** | Student name, national ID, date of birth, grades, health records |
| **Governing contract** | Safaricom Daraja Developer Terms of Service; per-tenant credentials stored in `TenantSettings.integrations.mpesa` |
| **Code location** | `school/mpesa.py` — `initiate_stk_push()`, `parse_stk_callback()` |
| **Enforcement** | Credentials loaded from `TenantSettings` (never from env or code); production mode requires `enabled: true` flag explicitly set |

---

### 1.2  SmartPSS Lite (Dahua — on-premises hardware)

| Attribute | Detail |
|-----------|--------|
| **Purpose** | Biometric/RFID attendance capture for staff and students |
| **Trigger** | Scheduled sync or manual admin trigger |
| **Endpoint** | `http://<local-ip>:8443/evo-apigw` — **on-premises LAN only**, not an internet endpoint |
| **Data sent** | Date/time range query (start, end, page size); admin username + password for session auth |
| **Data received** | `personId`, `personName`, `cardNo` (RFID), `attendStatus` (IN/OUT), `deviceName`, timestamp |
| **Data NOT sent** | No student records, health data, or financial information leave the system to this device |
| **Governing contract** | Dahua hardware EULA; school owns and operates the device; data is processed solely on school premises |
| **Code location** | `clockin/infrastructure/smartpss/client.py` |
| **Special notice** | RFID card numbers and biometric-adjacent attendance records are sensitive. Schools **must** include attendance monitoring in their staff/student privacy notice and obtain appropriate consent before enabling this integration. |
| **Enforcement** | Password required — never falls back to a hardcoded default (`ValueError` raised if absent). Connection is to a local IP; no data leaves school premises unless the school explicitly port-forwards. |

---

### 1.3  Resend (Transactional Email)

| Attribute | Detail |
|-----------|--------|
| **Purpose** | Platform-level transactional emails to school administrators (welcome, trial warnings, suspension notices, invoices, password resets) |
| **Trigger** | Platform lifecycle events (tenant provisioned, invoice issued, etc.) |
| **Endpoint** | Resend API (`resend` Python SDK — https://resend.com) |
| **Data sent** | Tenant admin email address, tenant/school name, subscription status, invoice amounts, password-reset URL |
| **Data NOT sent** | Student records, parent contact details, health data, grades |
| **Governing contract** | Resend Terms of Service + Data Processing Agreement (DPA) — operators **must** sign Resend's DPA before enabling `RESEND_API_KEY` in production |
| **Code location** | `clients/platform_email.py` — `_send()` |
| **Fallback** | If `RESEND_API_KEY` is not set, Django's built-in email backend is used (configured via standard `EMAIL_HOST` / `EMAIL_PORT` env vars) |
| **Enforcement** | Resend SDK imported lazily only when the key is present; if absent, Django email backend is used and no data reaches Resend |

---

### 1.4  Deployment / CI-CD Webhooks

| Attribute | Detail |
|-----------|--------|
| **Purpose** | Trigger or roll back CI/CD pipelines from the platform admin panel |
| **Trigger** | Operator action (Deploy → Trigger Pipeline or Roll Back) |
| **Endpoint** | Operator-configured URL via `DEPLOYMENT_TRIGGER_HOOK_URL` / `DEPLOYMENT_ROLLBACK_HOOK_URL` |
| **Data sent** | `release_id` (integer), `event` (trigger/rolled_back), `version` (string), `environment` (string), `requested_by` (admin username) |
| **Data NOT sent** | No school data, student records, or financial information |
| **Governing contract** | Operator's own CI/CD service (e.g. GitHub Actions, Render). The `requested_by` field contains an admin username — ensure the receiving endpoint is operated by the same organisation. |
| **Code location** | `clients/platform_views.py` — `_execute_deployment_hook()` |
| **Enforcement** | Hook only fires if the URL env var is set and non-empty; protected by `DEPLOYMENT_CALLBACK_TOKEN` bearer token; production mode asserts token is not blank/placeholder |

---

## 2  Placeholder / Stub Flows (not yet dispatching PII)

These integrations are registered in the platform catalog but their dispatch functions are **stubs** that do not make real HTTP calls. No personal data currently leaves the system via these channels. A real SDK must be wired in before any data flows.

### 2.1  SMS Provider (Africa's Talking / Twilio / other)

| Attribute | Detail |
|-----------|--------|
| **Purpose** | SMS notifications to parents and staff |
| **Current status** | **Stub only.** `send_sms_placeholder()` returns a simulated success response without making any outbound HTTP call, even when `COMMUNICATION_SMS_API_KEY` is set. |
| **Data that WILL flow when activated** | Recipient phone number, message body (may contain student name, fee balance, attendance status, or other personal data) |
| **Pre-activation requirements** | (a) Execute a DPA with the chosen SMS provider; (b) Update the school's Privacy Notice to disclose SMS messaging to parents/guardians; (c) Replace the stub with the real SDK; (d) Register the activated flow in this document. |
| **Code location** | `communication/services.py` — `send_sms_placeholder()` |
| **Config key** | `COMMUNICATION_SMS_API_KEY` |

### 2.2  WhatsApp Provider

Same requirements as SMS (§ 2.1). Controlled by `COMMUNICATION_WHATSAPP_API_KEY`.

### 2.3  Push Notification Provider

| Attribute | Detail |
|-----------|--------|
| **Purpose** | In-app push notifications |
| **Current status** | **Stub only.** `send_push_placeholder()` does not make outbound HTTP calls. |
| **Data that WILL flow when activated** | Device push token, notification title, notification body |
| **Pre-activation requirements** | DPA with the push provider (e.g. Firebase Cloud Messaging, APNs); privacy notice update; stub replacement. |
| **Code location** | `communication/services.py` — `send_push_placeholder()` |
| **Config key** | `COMMUNICATION_PUSH_SERVER_KEY` |

### 2.4  Google Workspace

Listed in the integrations catalog. No HTTP client code exists. Do not activate without completing a DPA review and registering the flow here.

### 2.5  Zoom

Listed in the integrations catalog. No HTTP client code exists. Do not activate without completing a DPA review and registering the flow here.

---

## 3  Confirmed Absent Flows

The following categories of external data sharing were audited and **confirmed not present** as of the last review date:

| Category | Status |
|----------|--------|
| AI / LLM APIs (OpenAI, Anthropic, Gemini, etc.) | Not present |
| Web analytics / tracking (Google Analytics, Segment, Mixpanel, Amplitude, etc.) | Not present |
| Error monitoring with PII (Sentry, Datadog, etc.) | Not present |
| Data warehouse export (Snowflake, BigQuery, etc.) | Not present |
| Ad networks or marketing pixels | Not present |
| Identity brokers beyond the platform itself | Not present |

---

## 4  Enforcement Checklist (Development & Runtime)

### Development
- [ ] Any new `requests.post / requests.get / httpx.*` call in a non-test file must be reviewed and registered here before merging.
- [ ] Any new entry in the integrations catalog (`AVAILABLE_INTEGRATIONS` in `clients/platform_views.py`) must have a corresponding section in this document.
- [ ] Stub dispatch functions (`send_sms_placeholder`, etc.) must log a `WARNING` when a provider key is present but real dispatch is not implemented.

### Runtime
- [ ] `RESEND_API_KEY` — sign Resend DPA before setting in production.
- [ ] `COMMUNICATION_SMS_API_KEY` — do not set until the SMS stub is replaced with a real SDK **and** this document is updated.
- [ ] `COMMUNICATION_WHATSAPP_API_KEY` — same as above.
- [ ] `COMMUNICATION_PUSH_SERVER_KEY` — same as above.
- [ ] `DEPLOYMENT_TRIGGER_HOOK_URL` / `DEPLOYMENT_ROLLBACK_HOOK_URL` — must point to an endpoint controlled by the same organisation.
- [ ] SmartPSS integration — only enable `SMARTPSS_PASSWORD` on servers that have network access to the school LAN; never expose SmartPSS Lite to the public internet without a VPN.

---

## 5  Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-04-16 | Privacy audit | Initial register created from codebase analysis |
