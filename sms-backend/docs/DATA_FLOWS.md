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

## 2  Tenant-Configured Messaging Flows

These channels now perform real outbound delivery when a tenant has configured the required credentials in the encrypted tenant secret store. If credentials are missing, the send paths fail honestly and no outbound call is made.

### 2.1  SMS Provider (Africa's Talking / Twilio / other)

| Attribute | Detail |
|-----------|--------|
| **Purpose** | SMS notifications to parents and staff |
| **Current status** | **Active when configured.** `send_sms_placeholder()` is a legacy-named helper that now performs real tenant-scoped HTTP dispatch for Africa's Talking, Twilio, Infobip, and Vonage. |
| **Data sent** | Recipient phone number, message body, sender ID / originator, provider account identifier |
| **Credential source** | `SchoolProfile.sms_provider`, `SchoolProfile.sms_username`, `SchoolProfile.sms_sender_id`, and encrypted tenant secret `school_profile:sms_api_key` |
| **Pre-activation requirements** | (a) Execute a DPA with the chosen SMS provider; (b) Update the school's Privacy Notice to disclose SMS messaging to parents/guardians; (c) Validate the provider-specific sender/originator values in staging before live use. |
| **Code location** | `communication/services.py` — `send_sms_placeholder()` |
| **Failure mode** | Missing/unsupported tenant configuration returns a local `Failed` dispatch result and no outbound HTTP call is attempted. |

### 2.2  WhatsApp Provider

| Attribute | Detail |
|-----------|--------|
| **Purpose** | WhatsApp notifications to parents and staff |
| **Current status** | **Active when configured.** Tenant-scoped dispatch uses the Meta WhatsApp Cloud API. |
| **Data sent** | Recipient phone number, message body, WhatsApp phone-number ID |
| **Credential source** | `SchoolProfile.whatsapp_phone_id` and encrypted tenant secret `school_profile:whatsapp_api_key` |
| **Pre-activation requirements** | Same governance and privacy requirements as SMS, plus Meta WhatsApp Cloud API approval for the tenant's sender identity. |
| **Code location** | `communication/services.py` — `send_sms_placeholder(channel="WhatsApp")` |
| **Failure mode** | Missing tenant credentials returns a local `Failed` dispatch result and no outbound HTTP call is attempted. |

### 2.3  Push Notification Provider

| Attribute | Detail |
|-----------|--------|
| **Purpose** | In-app push notifications |
| **Current status** | **Active when configured.** Push dispatch uses the tenant-scoped FCM legacy HTTP integration. |
| **Data sent** | Device push token, notification title, notification body |
| **Credential source** | Encrypted tenant secret `tenant_setting:integrations.push:server_key` or `tenant_setting:integrations.fcm:server_key` |
| **Pre-activation requirements** | DPA / terms review for the chosen push provider and privacy notice update for device-token handling. |
| **Code location** | `communication/services.py` — `send_push_placeholder()` |
| **Failure mode** | Missing tenant configuration returns a local `Failed` dispatch result and no outbound HTTP call is attempted. |

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
- [ ] Communication transports must resolve tenant-scoped encrypted credentials first; no new global `COMMUNICATION_*` transport secrets should be introduced.

### Runtime
- [ ] `RESEND_API_KEY` — sign Resend DPA before setting in production.
- [ ] Tenant SMS / WhatsApp / push credentials must be stored through the tenant secret store rather than plain env vars.
- [ ] Each live tenant must validate one end-to-end SMS send, one WhatsApp send if enabled, and one push send if enabled after rotating tenant secret keys.
- [ ] `DEPLOYMENT_TRIGGER_HOOK_URL` / `DEPLOYMENT_ROLLBACK_HOOK_URL` — must point to an endpoint controlled by the same organisation.
- [ ] SmartPSS integration — only enable `SMARTPSS_PASSWORD` on servers that have network access to the school LAN; never expose SmartPSS Lite to the public internet without a VPN.

---

## 5  Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-04-16 | Privacy audit | Initial register created from codebase analysis |
| 2026-04-26 | Platform engineering | Activated tenant-scoped SMS, WhatsApp, and push dispatch flows; removed stub-only status for those channels |
