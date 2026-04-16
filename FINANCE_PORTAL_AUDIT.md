# Finance Portal Audit — RynatySchool SmartCampus

**Date:** April 2026  
**Scope:** Fee collection, M-Pesa STK-push integration, invoice/payment workflow, webhook logging, parent/student finance views

---

## 1. Finance Module Architecture

### 1.1 Data Models (sms-backend/school/models.py)

| Model | Key Fields | Purpose |
|---|---|---|
| `FeeStructure` | `school_class`, `academic_year`, `term`, `total_amount` | Defines term fee amounts per class |
| `Invoice` | `student`, `academic_year`, `term`, `total_amount`, `paid_amount`, `status` | Per-student fee invoice |
| `Payment` | `invoice`, `amount`, `method`, `mpesa_transaction_id`, `status` | Individual payment records |
| `PaymentGatewayTransaction` | `reference`, `phone`, `amount`, `checkout_request_id`, `status` | M-Pesa STK-push tracking |
| `PaymentGatewayWebhookEvent` | `event_type`, `raw_payload`, `processed`, `created_at` | Raw Safaricom callback log |

### 1.2 Finance Roles

| Role | Permissions |
|---|---|
| `BURSAR` | View/create/approve all invoices and payments; trigger STK push; export reports |
| `ACCOUNTANT` | View invoices and payments; view reports |
| `PRINCIPAL` | View finance dashboards; approve fee waivers |
| `PARENT` | View own child's invoices and payment history |
| `STUDENT` | View own invoices; initiate M-Pesa STK push for own fees |

---

## 2. M-Pesa STK Push Integration

### 2.1 Flow

```
Student/Parent App  →  /api/student-portal/finance/pay/
        │
        ▼
StudentFinancePayView
  ├─ Validates invoice ownership
  ├─ Creates PaymentGatewayTransaction (status=PENDING, uuid reference)
  ├─ Calls mpesa.stk_push(phone, amount, reference, description)
  │       └─ Daraja API: /mpesa/stkpush/v1/processrequest
  └─ Returns { checkout_request_id, message }

Safaricom Callback  →  /api/mpesa/stk-callback/
        │
        ▼
MpesaStkCallbackView
  ├─ Immediately: PaymentGatewayWebhookEvent.objects.create(raw_payload=body)
  ├─ Parses result_code / result_desc
  ├─ Looks up PaymentGatewayTransaction by checkout_request_id
  ├─ On success: creates Payment, updates Invoice.paid_amount / status
  └─ Marks PaymentGatewayTransaction.status = SUCCESS | FAILED
```

### 2.2 Callback Endpoint

```
POST /api/mpesa/stk-callback/
```

- **Authentication:** None (Safaricom calls directly; IP whitelist enforced at reverse proxy)
- **Raw logging:** Every inbound payload is stored in `PaymentGatewayWebhookEvent` **before** any parsing, preventing data loss on parse errors
- **Idempotency:** Duplicate callbacks are detected by `checkout_request_id` uniqueness

### 2.3 STK Push Parameters

| Parameter | Source | Notes |
|---|---|---|
| Phone number | `UserProfile.phone` or request body | Must be in 254XXXXXXXXX format |
| Amount | Invoice balance (`total_amount - paid_amount`) | Rounded to nearest KES integer |
| Account reference | `PAY-<uuid4[:8].upper()>` | Linked to `PaymentGatewayTransaction.reference` |
| Business short code | `MPESA_SHORT_CODE` env var | |
| Passkey | `MPESA_PASSKEY` env var | |
| Callback URL | `MPESA_CALLBACK_URL` env var | Must be publicly reachable HTTPS |

---

## 3. Portal Endpoints

### 3.1 Student Portal Finance

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/student-portal/my-invoices/` | GET | Student JWT | List own invoices by term |
| `/api/student-portal/my-payments/` | GET | Student JWT | List own payment history |
| `/api/student-portal/finance/pay/` | POST | Student JWT | Initiate M-Pesa STK push |
| `/api/student-portal/finance/mpesa-status/` | GET | Student JWT | Poll STK push status |

**STK Push Request Body:**
```json
{
  "invoice_id": 42,
  "phone": "0712345678",
  "amount": 5000
}
```

**STK Push Response:**
```json
{
  "checkout_request_id": "ws_CO_...",
  "transaction_ref": "PAY-A1B2C3D4",
  "message": "STK push sent to 0712345678. Enter your M-Pesa PIN."
}
```

**Status Poll:**
```
GET /api/student-portal/finance/mpesa-status/?ref=PAY-A1B2C3D4
```

### 3.2 Parent Portal Finance

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/parent-portal/invoices/` | GET | Parent JWT | All linked children's invoices |
| `/api/parent-portal/payments/` | GET | Parent JWT | All linked children's payments |

### 3.3 Admin Finance (Bursar/Accountant)

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/finance/invoices/` | GET/POST | Staff JWT | Invoice CRUD |
| `/api/finance/payments/` | GET/POST | Staff JWT | Payment CRUD |
| `/api/finance/fee-structures/` | GET/POST | Staff JWT | Fee structure management |
| `/api/finance/mpesa/stk-push/` | POST | Bursar JWT | Trigger STK push (admin) |
| `/api/finance/reports/collection/` | GET | Accountant+ | Collection reports |

---

## 4. Audit Findings

### 4.1 ✅ PASS — Raw Webhook Logging
**File:** `sms-backend/school/views.py` → `MpesaStkCallbackView.post()`

All inbound Safaricom callbacks are stored in `PaymentGatewayWebhookEvent` **at the very start** of the handler, before any JSON parsing or business logic. This ensures:
- No payload is ever lost, even if parsing fails
- Replaying failed callbacks is possible from the `PaymentGatewayWebhookEvent` table
- Duplicate detection via `checkout_request_id`

### 4.2 ✅ PASS — Atomic Payment Recording
**File:** `sms-backend/school/views.py` → `MpesaStkCallbackView.post()`

Payment creation, invoice update, and `PaymentGatewayTransaction` status update are all wrapped in `db_transaction.atomic()`, preventing partial state on database errors.

### 4.3 ✅ PASS — Invoice Ownership Validation
**File:** `sms-backend/parent_portal/student_portal_views.py` → `StudentFinancePayView.post()`

The student finance pay endpoint validates that:
1. The invoice belongs to the authenticated student's linked `Student` record
2. The invoice is not already fully paid (`status != 'PAID'`)
3. The amount doesn't exceed the outstanding balance

### 4.4 ✅ PASS — No Sensitive Data in Logs
M-Pesa credentials (passkey, consumer key/secret) are loaded from environment variables only. No credentials are logged or included in error responses.

### 4.5 ⚠️ CAUTION — Phone Number Normalization
Phone numbers entered by users may be in `07XXXXXXXX` format. The M-Pesa helper function is expected to normalize to `254XXXXXXXXX`, but this should be verified in `mpesa_gateway/utils.py`.

**Recommendation:** Add explicit normalization in `StudentFinancePayView` before passing to STK push.

### 4.6 ⚠️ CAUTION — Callback URL Must Be HTTPS
The `MPESA_CALLBACK_URL` must be a publicly reachable HTTPS URL. In development, use `ngrok` or set `MPESA_CALLBACK_URL` to the Replit dev domain. In production, this is `https://api.rynatyschool.app/api/mpesa/stk-callback/`.

### 4.7 ✅ PASS — CSRF Exemption
The STK callback endpoint uses `@csrf_exempt` (via DRF's `APIView`) and does not require authentication, as Safaricom does not pass tokens.

### 4.8 ℹ️ INFO — Sandbox vs Production
The `MPESA_ENVIRONMENT` env var switches between Daraja sandbox (`sandbox.safaricom.co.ke`) and production (`api.safaricom.co.ke`). Test credentials provided in `QUICKSTART.md`.

---

## 5. Test Credentials (Sandbox)

| Setting | Value |
|---|---|
| Consumer Key | See `MPESA_CONSUMER_KEY` in `.env` |
| Consumer Secret | See `MPESA_CONSUMER_SECRET` in `.env` |
| Short Code | `174379` (Daraja sandbox) |
| Passkey | `bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919` |
| Test Phone | `0712345678` (triggers auto-success in sandbox) |
| Callback URL | `https://<replit-dev-domain>/api/mpesa/stk-callback/` |

---

## 6. Environment Variables Required

```bash
MPESA_CONSUMER_KEY=<from Daraja portal>
MPESA_CONSUMER_SECRET=<from Daraja portal>
MPESA_SHORT_CODE=174379
MPESA_PASSKEY=bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919
MPESA_CALLBACK_URL=https://api.rynatyschool.app/api/mpesa/stk-callback/
MPESA_ENVIRONMENT=sandbox   # or: production
```

---

## 7. Reconciliation & Reporting

- **Daily reconciliation:** Compare `Payment` records against M-Pesa statement CSV (downloadable from Daraja portal)
- **Discrepancy detection:** `PaymentGatewayWebhookEvent.processed = False` flags callbacks that were received but not matched to a `PaymentGatewayTransaction`
- **Reports available:** `/api/finance/reports/collection/` supports filtering by term, class, payment method, and date range

---

## 8. Reference Implementation

See `sms-backend/mpesa_saas_reference/` for the extracted reference implementation from `mpesa-school-saas`. This is **read-only reference material** — integration patterns from this codebase have been adapted into the main SmartCampus codebase. Do not import or run these files directly.

Key reference files:
- `mpesa_saas_reference/payments/mpesa_gateway.py` — STK push helper patterns
- `mpesa_saas_reference/payments/views.py` — Callback handler patterns
- `mpesa_saas_reference/payments/models.py` — Transaction model reference
