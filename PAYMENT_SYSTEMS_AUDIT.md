# Comprehensive Payment Systems Audit Report
## RynatySchool SmartCampus - Finance & Payment Integration

**Date:** April 17, 2026  
**Scope:** M-Pesa, Stripe, Bank Payments, Payment Reconciliation, User Endpoints  
**Status:** AUDIT ONLY - NO CODE IMPLEMENTATION  

---

## EXECUTIVE SUMMARY

### Current State Assessment

| System | Status | Implementation | Risk Level |
|--------|--------|-----------------|------------|
| **M-Pesa STK Push** | ✅ ACTIVE | Full production | LOW |
| **Stripe Integration** | ⚠️ PLACEHOLDER | Configuration only | HIGH |
| **Bank Payments** | ⚠️ MINIMAL | Manual reconciliation | HIGH |
| **Payment Sync** | ❌ MISSING | Not implemented | CRITICAL |
| **Webhook Processing** | ⚠️ LOGGING ONLY | Raw event storage | HIGH |
| **User Endpoints** | ⚠️ INCOMPLETE | M-Pesa only | HIGH |
| **Reconciliation Engine** | ❌ MISSING | No automated matching | CRITICAL |
| **Frontend UI** | ❌ MINIMAL | Limited components | HIGH |

### Key Findings

1. **M-Pesa is fully operational** - Safaricom Daraja 2.0 API, STK Push working, webhook logging active
2. **Stripe infrastructure exists but unused** - Models support it, no implementation code
3. **Bank integration is manual** - Statement lines exist, no API integration or automation
4. **Payment data is NOT in sync** - Webhooks logged but not processed into transaction records
5. **Missing reconciliation** - Payments received vs invoices paid have no automated matching
6. **User endpoints incomplete** - Only M-Pesa payment endpoint, missing Stripe & bank options

---

## SECTION 1: CURRENT PAYMENT SYSTEMS DETAILED ANALYSIS

### 1.1 M-Pesa Integration (ACTIVE ✅)

#### Architecture
- **Location:** `sms-backend/school/mpesa.py`, `school/views.py`
- **API:** Safaricom Daraja 2.0
- **Auth:** Per-tenant credentials stored in `TenantSettings` model
- **Environment:** Supports sandbox & production via settings

#### Implementation Details

**Endpoint:** `POST /api/finance/mpesa/push/`
- **View:** `MpesaStkPushView` 
- **Method:** REST API
- **Input:**
  ```
  {
    "student_id": "UUID",
    "phone_number": "+254712345678",
    "amount": 50000
  }
  ```
- **Output:**
  ```
  {
    "CheckoutRequestID": "ws_CO_120320231107115",
    "CustomerMessage": "Enter your M-Pesa PIN",
    "ResponseCode": "0",
    "MerchantRequestID": "123456789"
  }
  ```

**Transaction Flow:**
```
1. Student initiates payment → POST /api/finance/mpesa/push/
2. View creates PaymentGatewayTransaction (status=PENDING)
3. Calls mpesa.stk_push() → Safaricom API
4. Returns CheckoutRequestID to client
5. Customer enters PIN on phone
6. Safaricom POST to webhook URL
7. MpesaStkCallbackView receives callback
8. Raw payload logged to PaymentGatewayWebhookEvent
```

#### Data Models

**PaymentGatewayTransaction:**
- `reference` - Unique ID (UUID)
- `phone` - Customer phone number
- `amount` - Transaction amount (KES)
- `checkout_request_id` - Safaricom's request ID
- `status` - PENDING, COMPLETED, CANCELLED, TIMEOUT
- `mpesa_receipt_number` - M-Pesa confirmation code (from callback)
- `created_at`, `updated_at`

**PaymentGatewayWebhookEvent:**
- `event_type` - mpesa_stk_callback, mpesa_c2b_validation, mpesa_c2b_confirmation
- `raw_payload` - Full JSON from Safaricom (STORED BUT NOT PROCESSED)
- `processed` - Boolean flag (currently all false)
- `created_at`

**Payment Model (school/models.py):**
- `student` - FK to Student
- `payment_date` - Auto-added timestamp
- `amount` - Decimal
- `payment_method` - "Cash" | "Bank Transfer" | "MPesa"
- `reference_number` - Unique reference
- `receipt_number` - Receipt ID (auto-generated)
- `reversed_at` - For reversals

#### Webhook Processing (MISSING IMPLEMENTATION)

**Current State:**
- ✅ Webhook URL configured: `/api/mpesa/stk-callback/`
- ✅ Payloads logged to `PaymentGatewayWebhookEvent`
- ❌ **Payloads NOT processed**
- ❌ Payment records NOT created from callbacks
- ❌ Invoice status NOT updated
- ❌ Reconciliation NOT performed

**Callback Payload (from Safaricom):**
```json
{
  "Body": {
    "stkCallback": {
      "MerchantRequestID": "123456789",
      "CheckoutRequestID": "ws_CO_120320231107115",
      "ResultCode": 0,
      "ResultDesc": "The service request has been processed successfully",
      "CallbackMetadata": {
        "Item": [
          { "Name": "Amount", "Value": 50000 },
          { "Name": "MpesaReceiptNumber", "Value": "LHR519D60OP" },
          { "Name": "PhoneNumber", "Value": "254712345678" }
        ]
      }
    }
  }
}
```

---

### 1.2 Stripe Integration (PLACEHOLDER ⚠️)

#### Current State
- **Status:** Configuration file entries only
- **Code:** Zero implementation
- **Models:** Infrastructure exists to support it

#### Infrastructure Ready
**Settings (config/settings.py - Lines 506-507):**
```python
FINANCE_PAYMENT_GATEWAY_PROVIDER = os.getenv("FINANCE_PAYMENT_GATEWAY_PROVIDER", "placeholder")
FINANCE_PAYMENT_GATEWAY_API_KEY = os.getenv("FINANCE_PAYMENT_GATEWAY_API_KEY", "")
FINANCE_WEBHOOK_TOKEN = os.getenv("FINANCE_WEBHOOK_TOKEN", "")
FINANCE_WEBHOOK_SHARED_SECRET = os.getenv("FINANCE_WEBHOOK_SHARED_SECRET", "")
FINANCE_WEBHOOK_STRICT_MODE = os.getenv("FINANCE_WEBHOOK_STRICT_MODE", "false" if DEBUG else "true")
```

**Models Supporting Stripe:**
- `SubscriptionPayment` model (clients/models.py) has `method = "stripe"` support
- `PaymentGatewayTransaction` can track Stripe transaction IDs
- Status lifecycle: PENDING → PAID/FAILED/REFUNDED

#### Missing Components

| Component | Status | Impact |
|-----------|--------|--------|
| API Integration Layer | ❌ MISSING | No Stripe API calls |
| Payment Intent Processing | ❌ MISSING | Can't create charges |
| Webhook Handler | ❌ MISSING | No payment confirmations |
| Refund Logic | ❌ MISSING | No refund processing |
| 3D Secure/SCA | ❌ MISSING | High-value transactions at risk |
| PCI Compliance | ⚠️ PARTIAL | Token storage exists but untested |
| Error Handling | ❌ MISSING | No retry logic |
| Webhook Verification | ❌ MISSING | Signature validation not implemented |

#### Proposed Integration Points

**User Journey (Planned):**
```
1. Student selects Stripe payment option
2. Redirected to /api/finance/stripe/checkout/
3. Stripe Session created with invoice details
4. Redirect to Stripe hosted checkout
5. Customer pays (credit/debit card)
6. Stripe redirects to /api/finance/stripe/success/
7. Webhook: charge.succeeded → /api/finance/stripe/webhook/
8. Payment record created, invoice updated, receipt generated
```

---

### 1.3 Bank Payment Integration (MINIMAL ⚠️)

#### Current State
- **Status:** Database schema exists, no automation
- **Reconciliation:** Manual entry & matching only
- **API:** No bank API integration

#### Data Models

**BankStatementLine (school/models.py):**
- `statement_date` - When transaction occurred
- `reference_number` - Bank reference
- `amount` - Transaction amount
- `status` - UNMATCHED → MATCHED → RECONCILED
- `matched_to_payment` - FK to Payment (manual assignment)
- `matching_notes` - Why manual match was needed

**Payment Model Support:**
- `payment_method = "Bank Transfer"`
- `reference_number` - Bank confirmation number
- `receipt_number` - Internal receipt

#### Current Workflow (Manual)
```
1. Bank statement exported from bank
2. Finance staff manually uploads CSV
3. Each line imported as BankStatementLine
4. Staff manually matches lines to Payments
5. Status updated to MATCHED
6. Period end: Bursar reconciles (status=RECONCILED)
```

#### Missing Components

| Component | Status | Impact |
|-----------|--------|--------|
| Bank API Integration | ❌ MISSING | Manual download required |
| Automated Statement Import | ❌ MISSING | No scheduled imports |
| Automatic Transaction Matching | ❌ MISSING | Manual matching required |
| OCR for Cheques | ❌ MISSING | Can't process cheque scans |
| Multi-Currency Support | ⚠️ PARTIAL | Single currency only |
| Account Reconciliation | ⚠️ PARTIAL | Manual period-end reconciliation |
| Exception Handling | ⚠️ PARTIAL | No duplicate detection |
| Approval Workflow | ❌ MISSING | No authorization steps |

#### Supported Bank Scenarios

**Currently Supported:**
- ✅ Bank transfer receipts (manual)
- ✅ Cheque deposits (manual entry)
- ✅ Direct deposits (manual entry)

**NOT Supported:**
- ❌ Direct API integration (e.g., SWIFT, Open Banking)
- ❌ Real-time statement sync
- ❌ Automated clearing reconciliation
- ❌ Recurring/standing orders
- ❌ International payments

---

### 1.4 Reference Implementations (NOT Used)

#### M-Pesa B2C Payouts (sms-backend/mpesa_saas_reference/)
**Purpose:** School staff salary disbursement  
**Status:** Reference code exists but not integrated  
**Features:**
- B2C API for sending money to staff phones
- Transaction tracking
- Retry logic on failed disbursements

#### Fraud Detection Engine (sms-backend/mpesa_saas_reference/)
**Purpose:** Identify suspicious payment patterns  
**Status:** Reference code exists but not integrated  
**Features:**
- Duplicate payment detection
- Unusual amount/frequency alerts
- Geographic/device anomalies

---

## SECTION 2: USER ENDPOINTS DOCUMENTATION

### 2.1 Student User Endpoints (Fee Payer)

#### Active Endpoints ✅

**1. GET /api/student-portal/finance/invoices/**
- **Purpose:** View my fee invoices
- **Authentication:** JWT token (student user)
- **Response:**
  ```json
  {
    "count": 5,
    "results": [
      {
        "id": "uuid",
        "invoice_number": "INV-2026-001",
        "academic_year": "2025-2026",
        "term": "Term 1",
        "total_amount": 50000,
        "paid_amount": 30000,
        "balance": 20000,
        "status": "PARTIAL_PAID",
        "due_date": "2026-02-28",
        "created_at": "2026-01-15"
      }
    ]
  }
  ```
- **Permissions:** Student can only view own invoices
- **Status:** ✅ WORKING

**2. GET /api/student-portal/finance/payments/**
- **Purpose:** View my payment history
- **Authentication:** JWT token
- **Response:**
  ```json
  {
    "count": 10,
    "results": [
      {
        "id": "uuid",
        "reference_number": "PAY-001",
        "receipt_number": "RCT-000001",
        "amount": 30000,
        "payment_method": "MPesa",
        "payment_date": "2026-01-20",
        "status": "COMPLETED",
        "mpesa_reference": "LHR519D60OP"
      }
    ]
  }
  ```
- **Status:** ✅ WORKING

**3. POST /api/finance/mpesa/push/**
- **Purpose:** Initiate M-Pesa STK Push payment
- **Authentication:** JWT token
- **Request:**
  ```json
  {
    "student_id": "uuid",
    "phone_number": "+254712345678",
    "amount": 20000,
    "invoice_id": "uuid" (optional)
  }
  ```
- **Response:**
  ```json
  {
    "CheckoutRequestID": "ws_CO_120320231107115",
    "CustomerMessage": "Enter your M-Pesa PIN",
    "ResponseCode": "0"
  }
  ```
- **Status:** ✅ WORKING
- **Notes:** Only works for M-Pesa, no Stripe or bank options

**4. POST /api/finance/mpesa/status/**
- **Purpose:** Check payment status
- **Authentication:** JWT token
- **Request:**
  ```json
  {
    "CheckoutRequestID": "ws_CO_120320231107115"
  }
  ```
- **Response:** Payment status from M-Pesa
- **Status:** ✅ WORKING

#### Missing Endpoints ❌

**1. POST /api/finance/stripe/checkout/** (MISSING)
- **Purpose:** Initiate Stripe payment
- **Should Return:** Stripe session ID and checkout URL
- **Not Implemented**

**2. POST /api/finance/stripe/webhook/** (MISSING)
- **Purpose:** Handle Stripe payment confirmations
- **Should Handle:** charge.succeeded, charge.failed events
- **Not Implemented**

**3. POST /api/finance/bank/payment/** (MISSING)
- **Purpose:** Register bank payment intent
- **Should Return:** Bank details and reference number
- **Not Implemented**

**4. GET /api/finance/receipt/{payment_id}/** (MISSING)
- **Purpose:** Download payment receipt (PDF)
- **Should Return:** PDF receipt with QR code
- **Status:** Partially implemented for accounting but not exposed to students

---

### 2.2 Parent User Endpoints (Guardian)

#### Active Endpoints ✅

**1. GET /api/parent-portal/children/{child_id}/invoices/**
- **Purpose:** View child's invoices
- **Authentication:** JWT token (parent user)
- **Scope:** Parents can only view children they're linked to
- **Response:** Same structure as student endpoint
- **Status:** ✅ WORKING

**2. GET /api/parent-portal/children/{child_id}/payments/**
- **Purpose:** View child's payment history
- **Authentication:** JWT token
- **Status:** ✅ WORKING

**3. POST /api/parent-portal/children/{child_id}/pay-mpesa/**
- **Purpose:** Parent initiates M-Pesa payment for child
- **Authentication:** JWT token
- **Request:**
  ```json
  {
    "phone_number": "+254712345678",
    "amount": 20000,
    "invoice_id": "uuid"
  }
  ```
- **Status:** ✅ WORKING (M-Pesa only)

#### Missing Endpoints ❌

**1. GET /api/parent-portal/children/{child_id}/arrears/** (MISSING)
- **Purpose:** View overdue fees and payment schedules
- **Not Implemented**

**2. POST /api/parent-portal/payment-plans/** (MISSING)
- **Purpose:** Request installment payment plan
- **Should Support:** 3-month, 6-month payment schedules
- **Not Implemented**

**3. GET /api/parent-portal/payment-methods/** (MISSING)
- **Purpose:** View registered payment methods
- **Should List:** M-Pesa, Stripe, Bank details
- **Not Implemented**

**4. POST /api/parent-portal/recurring-payment/** (MISSING)
- **Purpose:** Setup recurring payment schedule
- **Not Implemented**

---

### 2.3 Bursar/Accountant Endpoints (Backend Users)

#### Active Endpoints ✅

**1. GET /api/finance/payments/**
- **Purpose:** View all school payments
- **Authentication:** JWT token (bursar/accountant role)
- **Query Params:** `?status=PENDING&student_id=uuid&date_from=2026-01-01`
- **Status:** ✅ WORKING

**2. POST /api/finance/payments/**
- **Purpose:** Manually create payment record (cash receipt)
- **Authentication:** JWT token
- **Request:**
  ```json
  {
    "student_id": "uuid",
    "amount": 50000,
    "payment_method": "Cash",
    "reference_number": "CASH-001",
    "notes": "Payment received from parent"
  }
  ```
- **Status:** ✅ WORKING

**3. GET /api/finance/invoices/**
- **Purpose:** View all invoices with filtering
- **Query Params:** `?status=UNPAID&class_id=uuid&academic_year=2025-2026`
- **Status:** ✅ WORKING

**4. POST /api/finance/payments/{id}/reverse/**
- **Purpose:** Reverse/refund a payment
- **Authentication:** JWT token (bursar only)
- **Request:**
  ```json
  {
    "reversal_reason": "Duplicate payment detected"
  }
  ```
- **Status:** ✅ WORKING

**5. GET /api/finance/reports/arrears/**
- **Purpose:** Generate overdue fees report
- **Query Params:** `?as_of_date=2026-04-17`
- **Response:** Students with outstanding balances
- **Status:** ✅ WORKING

**6. GET /api/finance/reports/receipt-cash-book/**
- **Purpose:** Receipt and cash book reports
- **Status:** ✅ WORKING

#### Missing Endpoints ❌

**1. GET /api/finance/payments/reconciliation/** (MISSING)
- **Purpose:** View unreconciled payments
- **Should Show:** Webhook events without matching Payment records
- **Not Implemented**

**2. POST /api/finance/payments/{id}/reconcile/** (MISSING)
- **Purpose:** Manually reconcile a payment with bank/gateway
- **Request:**
  ```json
  {
    "gateway_reference": "LHR519D60OP",
    "bank_reference": "CHQ-001",
    "notes": "Matched to M-Pesa callback"
  }
  ```
- **Not Implemented**

**3. POST /api/finance/bank/import-statement/** (MISSING)
- **Purpose:** Upload bank statement CSV
- **Should Handle:** Parsing and BankStatementLine creation
- **Not Implemented**

**4. POST /api/finance/bank/match-transactions/** (MISSING)
- **Purpose:** Automatically match bank transactions to payments
- **Algorithm:** Fuzzy matching by amount/date/reference
- **Not Implemented**

**5. GET /api/finance/webhook-events/** (MISSING)
- **Purpose:** View raw webhook events for audit
- **Should Show:** PaymentGatewayWebhookEvent logs
- **Query Params:** `?status=unprocessed&gateway=mpesa`
- **Not Implemented**

**6. POST /api/finance/webhook-events/{id}/reprocess/** (MISSING)
- **Purpose:** Manually reprocess failed webhook
- **Not Implemented**

**7. GET /api/finance/dashboard/** (MISSING)
- **Purpose:** Finance summary dashboard
- **Should Show:** Total collected, pending, arrears, cash position
- **Partially Implemented** - exists but not complete

---

### 2.4 Platform Admin Endpoints (Multi-Tenant)

#### Active Endpoints ✅

**1. GET /api/platform/subscriptions/{tenant_id}/**
- **Purpose:** View school's subscription status
- **Authentication:** Platform admin JWT
- **Response:**
  ```json
  {
    "id": "uuid",
    "tenant_id": "school-uuid",
    "plan": "Professional",
    "status": "ACTIVE",
    "billing_cycle": "MONTHLY",
    "next_billing_date": "2026-05-17",
    "amount": 5000
  }
  ```
- **Status:** ✅ WORKING

**2. GET /api/platform/invoices/{tenant_id}/**
- **Purpose:** View school's subscription invoices
- **Status:** ✅ WORKING

**3. GET /api/platform/payments/subscription/**
- **Purpose:** View subscription payments
- **Status:** ✅ WORKING

#### Missing Endpoints ❌

**1. GET /api/platform/integrations/{tenant_id}/** (MISSING)
- **Purpose:** View school's enabled payment integrations
- **Should Return:** 
  ```json
  {
    "mpesa": { "enabled": true, "status": "ACTIVE", "test_mode": false },
    "stripe": { "enabled": false, "status": "NOT_CONFIGURED", "test_mode": true },
    "bank": { "enabled": false, "status": "NOT_CONFIGURED" }
  }
  ```
- **Not Implemented**

**2. POST /api/platform/integrations/{tenant_id}/stripe/connect/** (MISSING)
- **Purpose:** Setup school's Stripe account
- **Should Support:** OAuth Stripe Connect flow
- **Not Implemented**

**3. POST /api/platform/integrations/{tenant_id}/bank/setup/** (MISSING)
- **Purpose:** Configure bank account details
- **Not Implemented**

---

## SECTION 3: SYNC & RECONCILIATION GAPS

### 3.1 Payment Data Sync Issues

#### Problem: Webhook Events NOT Converted to Payments

**Current Flow (BROKEN):**
```
Safaricom sends webhook → MpesaStkCallbackView receives → 
PaymentGatewayWebhookEvent logged (raw_payload stored) → 
PROCESS ENDS HERE ❌

No automatic:
- Payment record creation
- Invoice status update
- Wallet credit
- Receipt generation
```

**Missing Processing Step:**
```json
{
  "Body": {
    "stkCallback": {
      "CheckoutRequestID": "ws_CO_120320231107115",
      "ResultCode": 0,  // 0 = success
      "CallbackMetadata": {
        "Item": [
          { "Name": "Amount", "Value": 50000 },
          { "Name": "MpesaReceiptNumber", "Value": "LHR519D60OP" },
          { "Name": "PhoneNumber", "Value": "254712345678" }
        ]
      }
    }
  }
}
  ↓
SHOULD CREATE:
  1. Payment record
  2. PaymentAllocation record(s)
  3. Update Invoice.paid_amount & status
  4. Create JournalEntry (accounting)
  5. Send receipt to student
  6. Update PaymentGatewayWebhookEvent.processed = true
```

#### Problem: Bank Statements NOT Auto-Synced

**Current Workflow:**
```
1. Finance staff downloads CSV from bank portal
2. Manually uploads to system
3. Manually matches each line to a Payment
4. Period-end manual reconciliation
```

**Missing Automation:**
- No scheduled bank API calls
- No automatic CSV import
- No fuzzy matching algorithm
- No exception alerts

#### Problem: Stripe NOT Integrated

**Missing Entire Workflow:**
- No Stripe account connection
- No payment form
- No webhook processing
- No refund reconciliation

### 3.2 Invoice-to-Payment Sync Issues

#### Problem: Multiple Payment Records for Same Invoice

**Risk:**
- Student pays 30,000 via M-Pesa
- Webhook not processed for 2 hours
- Student pays another 20,000 via cash (staff entry)
- Both payments exist: Payment A (30k, PENDING), Payment B (20k, PAID)
- Invoice only allocated to Payment B
- 30k payment becomes orphaned

**Missing Safeguard:**
- Check PaymentGatewayTransaction for pending matches
- Validate invoice not already fully paid
- Deduplication logic

#### Problem: Reversal Doesn't Sync to Invoice

**Current:**
```
1. Bursar approves reversal → Payment.reversed_at set
2. PaymentAllocation NOT deleted
3. Invoice.paid_amount unchanged
4. Invoice status NOT updated
```

**Should Happen:**
```
1. Reversal approved
2. PaymentAllocation deleted
3. Invoice.paid_amount decremented
4. JournalEntry REVERSAL posted
5. Refund initiated (M-Pesa B2C or bank transfer)
6. Student notified
```

### 3.3 Accounting Sync Issues

#### Problem: Webhook Events NOT Posted to General Ledger

**Current:**
- M-Pesa payment webhooks logged but not accounting entries created
- Bank deposits entered manually, no GL posting
- Stripe (when implemented) won't post entries

**Missing:**
- Automatic JournalEntry creation on payment webhook
- Chart of Accounts missing for gateways (Stripe receivable, M-Pesa payable, etc.)
- Bank reconciliation posting

---

## SECTION 4: MISSING FEATURES & FUNCTIONALITY

### 4.1 User Interface (Frontend)

| Component | Status | Users Affected |
|-----------|--------|-----------------|
| Payment Methods Selector | ❌ MISSING | Students/Parents |
| Stripe Checkout Form | ❌ MISSING | Students/Parents |
| Bank Transfer Instructions | ❌ MISSING | Students/Parents |
| Payment Status Dashboard | ⚠️ PARTIAL | Students/Parents |
| Receipt PDF Download | ⚠️ PARTIAL | Students/Parents |
| Payment History Chart | ❌ MISSING | Students/Parents |
| Installment Plan Selector | ❌ MISSING | Students/Parents |
| Payment Plan Simulator | ❌ MISSING | Students/Parents |
| Arrears Notification | ⚠️ PARTIAL | Students/Parents |
| Finance Dashboard (Bursar) | ⚠️ PARTIAL | Finance Staff |
| Reconciliation UI | ❌ MISSING | Finance Staff |
| Bank Statement Uploader | ❌ MISSING | Finance Staff |
| Webhook Event Viewer | ❌ MISSING | Finance Staff |
| Payment Reversal Form | ⚠️ PARTIAL | Finance Staff |

### 4.2 Backend Business Logic

| Feature | Status | Impact |
|---------|--------|--------|
| Webhook Processing Engine | ❌ MISSING | CRITICAL |
| Auto-Reconciliation Logic | ❌ MISSING | CRITICAL |
| Bank Statement Import | ❌ MISSING | HIGH |
| Stripe Integration | ❌ MISSING | HIGH |
| Multi-Currency Support | ❌ MISSING | MEDIUM |
| Payment Plan Auto-Deduct | ❌ MISSING | MEDIUM |
| Late Fee Auto-Calculation | ⚠️ PARTIAL | MEDIUM |
| Refund Processing | ⚠️ PARTIAL | HIGH |
| Duplicate Detection | ❌ MISSING | HIGH |
| Fraud Detection | ❌ MISSING | MEDIUM |
| Recurring Payments | ❌ MISSING | MEDIUM |
| Payment Retries (Failed) | ❌ MISSING | MEDIUM |
| Audit Trail Encryption | ❌ MISSING | LOW |

### 4.3 Reporting & Analytics

| Report | Status | Users |
|--------|--------|-------|
| Daily Collection Summary | ⚠️ PARTIAL | Bursar |
| Payment Method Breakdown | ❌ MISSING | Bursar |
| Gateway Performance (Stripe vs M-Pesa) | ❌ MISSING | Platform Admin |
| Failed Payment Analysis | ❌ MISSING | Bursar |
| Reconciliation Exception Report | ❌ MISSING | Accountant |
| Arrears Aging Report | ✅ EXISTS | Bursar |
| Student Payment History | ✅ EXISTS | Parent/Student |

---

## SECTION 5: DATA MODEL GAPS

### 5.1 Missing Models

#### Model: PaymentMethodConfiguration
**Purpose:** Store school-specific payment method settings  
**Should Include:**
```
- school_id (FK)
- payment_method (mpesa | stripe | bank | cash)
- is_enabled (boolean)
- configuration (JSON):
    - For M-Pesa: business_shortcode, passkey
    - For Stripe: publishable_key, webhook_secret
    - For Bank: account_number, routing_number, bank_name
- test_mode (boolean)
- test_credentials (JSON, encrypted)
- production_credentials (JSON, encrypted)
- created_at, updated_at
```

#### Model: PaymentReconciliation
**Purpose:** Track matched transactions  
**Should Include:**
```
- payment_id (FK) - Gateway payment record
- bank_statement_line_id (FK, nullable) - Bank match
- invoice_id (FK, nullable) - Accounting match
- status (UNMATCHED | MATCHED | RECONCILED | EXCEPTION)
- match_confidence (float 0-1)
- match_notes (text)
- matched_by (FK to User)
- matched_at (datetime)
- reconciled_at (datetime)
```

#### Model: WebhookEventProcessing
**Purpose:** Track webhook processing state  
**Should Include:**
```
- webhook_event_id (FK)
- processing_status (PENDING | PROCESSING | COMPLETED | FAILED | RETRY)
- error_message (text, nullable)
- attempted_at (datetime)
- retry_count (int)
- next_retry_at (datetime, nullable)
- completed_at (datetime, nullable)
```

#### Model: PaymentGatewayCredentials
**Purpose:** Encrypted credential storage (replaces current TenantSettings JSON)  
**Should Include:**
```
- school_id (FK)
- gateway_name (mpesa | stripe | bank)
- environment (test | production)
- api_key (encrypted)
- api_secret (encrypted)
- webhook_secret (encrypted)
- additional_config (JSON, encrypted)
- is_active (boolean)
- last_tested_at (datetime)
- test_result (success | failure)
```

#### Model: RefundRequest
**Purpose:** Track refund processing  
**Should Include:**
```
- payment_id (FK)
- amount (decimal)
- reason (text)
- requested_by (FK User)
- requested_at (datetime)
- status (PENDING | APPROVED | PROCESSING | COMPLETED | REJECTED)
- refund_method (original_payment | bank | cash)
- gateway_refund_id (text, nullable)
- completed_at (datetime, nullable)
- rejection_reason (text, nullable)
```

### 5.2 Missing Fields

#### Payment Model Should Add:
```
- gateway_name (CharField: mpesa | stripe | bank | cash)
- gateway_transaction_id (CharField, nullable)
- gateway_reference (CharField, nullable)
- webhook_event_id (FK, nullable)
- idempotency_key (CharField, unique, for duplicate prevention)
- reconciliation_status (PENDING | MATCHED | EXCEPTION)
```

#### Invoice Model Should Add:
```
- payment_method_preference (CharField: mpesa | stripe | bank | any)
- is_payment_plan_eligible (boolean)
- late_fee_waived_reason (text, nullable)
- custom_due_date (DateField, nullable - overrides calculated date)
```

---

## SECTION 6: INTEGRATION ARCHITECTURE RECOMMENDATIONS

### 6.1 Payment Gateway Hub Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  PAYMENT SYSTEMS SYNC                        │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         PAYMENT GATEWAY ABSTRACTION LAYER            │  │
│  │  (Interface for M-Pesa, Stripe, Bank, Cash)         │  │
│  └──────────────────────────────────────────────────────┘  │
│         ↑          ↑           ↑           ↑                │
│         │          │           │           │                │
│      M-Pesa     Stripe      Bank API    Cash/Manual         │
│      (Active)   (TODO)      (TODO)      (WORKING)           │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │     WEBHOOK PROCESSING & RECONCILIATION ENGINE       │  │
│  │  (Convert raw events → Payments → Invoices → GL)    │  │
│  └──────────────────────────────────────────────────────┘  │
│         ↑          ↑           ↑           ↑                │
│         │          │           │           │                │
│    Event Queue  Matcher    GL Poster    Notifier           │
│    (TODO)       (TODO)     (PARTIAL)    (PARTIAL)          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │          ACCOUNTING & RECONCILIATION                 │  │
│  │  (JournalEntry posting, trial balance, audit)        │  │
│  └──────────────────────────────────────────────────────┘  │
│         ↑          ↑           ↑                            │
│         │          │           │                            │
│   AR Account   Bank Acct   Gateway Accts                    │
│  (WORKING)    (PARTIAL)    (MISSING)                        │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │            USER-FACING ENDPOINTS & UI                │  │
│  │  (Student/Parent/Bursar portals)                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Webhook Processing Flow (TODO)

```
Webhook In (M-Pesa/Stripe/Bank)
    ↓
[1] Verify Signature/Token
    ↓ (if valid)
[2] Log to PaymentGatewayWebhookEvent
    ↓
[3] Extract payment details
    ├─ Gateway transaction ID
    ├─ Amount
    ├─ Reference number
    ├─ Timestamp
    └─ Status (success/failure)
    ↓
[4] Find matching PaymentGatewayTransaction
    ├─ By CheckoutRequestID (M-Pesa)
    ├─ By PaymentIntentID (Stripe)
    └─ By Transaction ID (Bank)
    ↓
[5] Find matching Invoice (by phone/student/ref number)
    ↓
[6] Create Payment Record (if new)
    ├─ Student ID
    ├─ Amount
    ├─ Payment method
    ├─ Gateway reference
    └─ Status
    ↓
[7] Create PaymentAllocation (link Payment → Invoice)
    ├─ If exact amount match: allocate fully
    ├─ If partial: allocate available
    └─ If overpayment: create credit note
    ↓
[8] Update Invoice Status
    ├─ Fully paid → status = PAID
    ├─ Partial → status = PARTIAL_PAID
    └─ Overpaid → notify bursar
    ↓
[9] Post JournalEntry (Accounting)
    ├─ Debit: M-Pesa Receivable / Bank Account
    └─ Credit: Accounts Receivable (Student Invoice)
    ↓
[10] Mark PaymentGatewayWebhookEvent.processed = true
    ↓
[11] Generate & Send Receipt
    ├─ Email to student
    ├─ Email to parent
    └─ PDF to portal
    ↓
[12] Send Notification (if configured)
    ├─ SMS balance update
    └─ Email confirmation
    ↓
Payment Sync Complete ✅
```

---

## SECTION 7: CONFIGURATION & SECURITY AUDIT

### 7.1 Environment Variables (INCOMPLETE)

#### Currently Defined:
```
FINANCE_PAYMENT_GATEWAY_PROVIDER = "placeholder"
FINANCE_PAYMENT_GATEWAY_API_KEY = ""
FINANCE_WEBHOOK_TOKEN = ""
FINANCE_WEBHOOK_SHARED_SECRET = ""
FINANCE_WEBHOOK_STRICT_MODE = false (dev) | true (prod)
```

#### Missing (Should Be Added):

**M-Pesa Configuration:**
```
MPESA_DARAJA_API_URL = https://api.sandbox.safaricom.co.ke
MPESA_CONSUMER_KEY = <your-key>
MPESA_CONSUMER_SECRET = <your-secret>
MPESA_SHORTCODE = 123456
MPESA_PASSKEY = <your-passkey>
MPESA_WEBHOOK_URL = https://school.com/api/mpesa/stk-callback/
MPESA_TIMEOUT_URL = https://school.com/api/mpesa/timeout/
```

**Stripe Configuration:**
```
STRIPE_PUBLIC_KEY = pk_test_xxxxx
STRIPE_SECRET_KEY = sk_test_xxxxx
STRIPE_WEBHOOK_SECRET = whsec_xxxxx
STRIPE_ACCOUNT_ID = acct_xxxxx (for connect)
STRIPE_API_VERSION = 2024-04-10
STRIPE_WEBHOOK_URL = https://school.com/api/stripe/webhook/
```

**Bank Configuration:**
```
BANK_STATEMENT_IMPORT_PATH = /mnt/bank-imports/
BANK_STATEMENT_FILENAME_PATTERN = *.csv
BANK_RECONCILIATION_TOLERANCE = 0 (exact match required)
BANK_IMPORT_SCHEDULE = daily
```

### 7.2 Security Gaps

| Gap | Severity | Recommendation |
|-----|----------|-----------------|
| Webhook credentials in environment | HIGH | Use vault (AWS Secrets Manager) |
| No webhook signature verification | CRITICAL | Implement HMAC-SHA256 validation |
| Bank credentials in plain text | CRITICAL | Encrypt all gateway credentials |
| No rate limiting on payment endpoints | HIGH | Add throttling (10 req/min per user) |
| No idempotency keys | HIGH | Prevent duplicate payment processing |
| Webhook events not encrypted | MEDIUM | Add encryption for sensitive data |
| No audit trail for credential rotation | MEDIUM | Log all credential changes |
| M-Pesa callback IP not whitelisted | MEDIUM | Validate Safaricom IP ranges |
| No PCI DSS compliance tracking | CRITICAL | Add compliance checklist |
| Refund logic not validated | HIGH | Require dual approval for large refunds |

---

## SECTION 8: COMPREHENSIVE USER ENDPOINT INVENTORY

### All Endpoints by Role

#### STUDENT ENDPOINTS

| Endpoint | Method | Status | Purpose |
|----------|--------|--------|---------|
| `/api/student-portal/finance/invoices/` | GET | ✅ | List my invoices |
| `/api/student-portal/finance/invoices/{id}/` | GET | ✅ | View invoice detail |
| `/api/student-portal/finance/payments/` | GET | ✅ | List my payments |
| `/api/student-portal/finance/payments/{id}/receipt/` | GET | ❌ | Download receipt PDF |
| `/api/finance/mpesa/push/` | POST | ✅ | Initiate M-Pesa STK |
| `/api/finance/mpesa/status/` | GET | ✅ | Check STK status |
| `/api/finance/stripe/checkout/` | POST | ❌ | Start Stripe payment |
| `/api/finance/stripe/success/` | GET | ❌ | Stripe redirect (success) |
| `/api/finance/bank/instructions/` | GET | ❌ | Get bank transfer details |
| `/api/student-portal/finance/payment-plans/` | GET | ❌ | View available plans |
| `/api/student-portal/finance/payment-plans/` | POST | ❌ | Request plan |
| `/api/student-portal/finance/balance/` | GET | ⚠️ | Get balance summary |

#### PARENT ENDPOINTS

| Endpoint | Method | Status | Purpose |
|----------|--------|--------|---------|
| `/api/parent-portal/children/` | GET | ✅ | List my children |
| `/api/parent-portal/children/{id}/invoices/` | GET | ✅ | Child's invoices |
| `/api/parent-portal/children/{id}/payments/` | GET | ✅ | Child's payments |
| `/api/parent-portal/children/{id}/balance/` | GET | ⚠️ | Child's balance |
| `/api/parent-portal/children/{id}/pay-mpesa/` | POST | ✅ | Pay M-Pesa (child) |
| `/api/parent-portal/children/{id}/pay-stripe/` | POST | ❌ | Pay Stripe (child) |
| `/api/parent-portal/children/{id}/arrears/` | GET | ❌ | Child's overdue fees |
| `/api/parent-portal/payment-methods/` | GET | ❌ | Saved payment methods |
| `/api/parent-portal/payment-methods/` | POST | ❌ | Add payment method |
| `/api/parent-portal/recurring-payments/` | GET | ❌ | My subscriptions |
| `/api/parent-portal/recurring-payments/` | POST | ❌ | Create subscription |

#### BURSAR/ACCOUNTANT ENDPOINTS

| Endpoint | Method | Status | Purpose |
|----------|--------|--------|---------|
| `/api/finance/payments/` | GET | ✅ | List all payments |
| `/api/finance/payments/` | POST | ✅ | Create payment (manual) |
| `/api/finance/payments/{id}/` | GET | ✅ | Payment detail |
| `/api/finance/payments/{id}/reverse/` | POST | ✅ | Reverse payment |
| `/api/finance/payments/{id}/reconcile/` | POST | ❌ | Manual reconciliation |
| `/api/finance/invoices/` | GET | ✅ | List invoices |
| `/api/finance/invoices/` | POST | ✅ | Create invoice |
| `/api/finance/invoices/{id}/` | PATCH | ✅ | Update invoice |
| `/api/finance/invoices/{id}/write-off/` | POST | ⚠️ | Write off balance |
| `/api/finance/reports/arrears/` | GET | ✅ | Arrears report |
| `/api/finance/reports/dashboard/` | GET | ⚠️ | Finance dashboard |
| `/api/finance/reports/cash-book/` | GET | ✅ | Cash book report |
| `/api/finance/reports/payment-methods/` | GET | ❌ | Payments by method |
| `/api/finance/reports/gateway-performance/` | GET | ❌ | Gateway stats |
| `/api/finance/bank/import-statement/` | POST | ❌ | Upload bank CSV |
| `/api/finance/bank/statements/` | GET | ❌ | View bank statements |
| `/api/finance/bank/match-transactions/` | POST | ❌ | Auto-match |
| `/api/finance/webhook-events/` | GET | ❌ | View raw webhooks |
| `/api/finance/webhook-events/{id}/reprocess/` | POST | ❌ | Retry webhook |
| `/api/finance/reconciliation/` | GET | ❌ | Reconciliation status |

#### PLATFORM ADMIN ENDPOINTS

| Endpoint | Method | Status | Purpose |
|----------|--------|--------|---------|
| `/api/platform/subscriptions/{tenant}/` | GET | ✅ | School subscription |
| `/api/platform/subscriptions/{tenant}/` | PATCH | ✅ | Update subscription |
| `/api/platform/invoices/{tenant}/` | GET | ✅ | School's invoices |
| `/api/platform/payments/` | GET | ✅ | Platform payments |
| `/api/platform/integrations/{tenant}/` | GET | ❌ | Integration status |
| `/api/platform/integrations/{tenant}/stripe/connect/` | POST | ❌ | Stripe setup |
| `/api/platform/integrations/{tenant}/stripe/disconnect/` | POST | ❌ | Stripe removal |
| `/api/platform/integrations/{tenant}/bank/setup/` | POST | ❌ | Bank config |
| `/api/platform/integrations/{tenant}/test/` | POST | ❌ | Test gateway |

---

## SECTION 9: MISSING UI COMPONENTS CHECKLIST

### Frontend (artifacts/rynaty-space/src/)

#### Payment Selection Component ❌
- Component name: `PaymentMethodSelector.tsx`
- Should display: M-Pesa, Stripe, Bank, Cash options
- Based on school configuration (enabled methods)
- Icon and description for each
- Feature flags per school

#### Stripe Checkout Component ❌
- Component: `StripeCheckoutForm.tsx`
- Integration with @stripe/react-stripe-js
- Card element with validation
- Error handling & retry
- Loading state during processing
- Receipt generation on success

#### Bank Transfer Instructions ❌
- Component: `BankTransferInfo.tsx`
- Display bank account details
- Reference number to include
- Due date reminder
- Transaction status checker

#### Payment History Chart ❌
- Component: `PaymentHistoryChart.tsx`
- Timeline visualization
- Filter by payment method
- Export CSV/PDF
- Trend analysis

#### Receipt/Voucher Component ❌
- Component: `PaymentReceipt.tsx`
- Display payment details
- QR code with transaction ref
- Download as PDF
- Email send option
- Print option

#### Installment Plan UI ❌
- Component: `InstallmentPlanSelector.tsx`
- Show available plans (3mo, 6mo, etc.)
- Calculate monthly amount
- Due date calculator
- Approval status
- Request plan button

#### Finance Dashboard (Bursar) ❌
- Component: `BursarDashboard.tsx`
- Key metrics: daily collection, pending, arrears
- Collection by method (M-Pesa vs Bank vs Cash)
- Gateway success/failure rates
- Outstanding invoices list
- Recent payments widget
- Arrears trend chart

#### Reconciliation UI ❌
- Component: `PaymentReconciliation.tsx`
- Unmatched payments list
- Bank statement line matcher
- Fuzzy matching results
- Accept/reject matches
- Manual payment lookup
- Bulk reconciliation

#### Webhook Event Viewer ❌
- Component: `WebhookEventLog.tsx`
- Event list with filtering
- Raw JSON payload viewer
- Processing status
- Error messages
- Manual reprocess button
- Timestamp and source

---

## SECTION 10: DEPLOYMENT & ROLLOUT STRATEGY

### Phase 1: Foundation (Weeks 1-2)
- [ ] Setup payment gateway credentials management
- [ ] Implement webhook processing framework
- [ ] Add missing data models
- [ ] Create Stripe API integration layer
- [ ] Setup bank import scheduler

### Phase 2: Stripe Integration (Weeks 3-4)
- [ ] Stripe Payment Intent API implementation
- [ ] Webhook handler for Stripe events
- [ ] Frontend checkout component
- [ ] Refund processing
- [ ] Error handling & retries

### Phase 3: Bank Integration (Weeks 5-6)
- [ ] Bank statement import from API/CSV
- [ ] Automatic transaction matching
- [ ] Reconciliation exception alerts
- [ ] Bank endpoint dashboard

### Phase 4: Payment Sync (Weeks 7-8)
- [ ] Webhook processing engine (M-Pesa/Stripe/Bank)
- [ ] Invoice-to-payment auto-matching
- [ ] GL posting for all payment types
- [ ] Audit trail for all transactions

### Phase 5: User Interface (Weeks 9-10)
- [ ] Payment method selector
- [ ] Payment history & receipts
- [ ] Bursar reconciliation UI
- [ ] Finance dashboard updates

### Phase 6: Testing & Documentation (Weeks 11-12)
- [ ] End-to-end payment scenarios
- [ ] Security & compliance testing
- [ ] User documentation
- [ ] Staff training

---

## SECTION 11: SUMMARY OF CRITICAL GAPS

### Immediate Action Required (CRITICAL)

1. **Webhook Processing Engine**
   - Safaricom callbacks logged but not converted to Payments
   - Risk: Revenue not recorded, invoices not marked paid
   - Impact: Financial data integrity compromised

2. **Stripe Implementation**
   - Zero code, only configuration
   - Risk: No card payment option for users
   - Impact: Revenue loss, single payment method dependency

3. **Bank Reconciliation**
   - Manual entry & matching only
   - Risk: Days/weeks delay in cash recognition
   - Impact: Cash position unknown, fraud risk

4. **Payment Data Sync**
   - Multiple systems (M-Pesa, Stripe, Bank) not synchronized
   - Risk: Duplicate payments, orphaned transactions
   - Impact: Financial chaos, accounting errors

### High Priority (Next 4 Weeks)

5. **User Endpoints for All Payment Methods**
   - Only M-Pesa exposed to students
   - Missing Stripe & bank options
   - Impact: Functionality gaps, poor UX

6. **Frontend UI Components**
   - Minimal payment UI components
   - Missing receipt, history, reconciliation screens
   - Impact: Poor user experience

7. **Accounting Integration**
   - Webhooks not posting to GL
   - No Stripe/Bank account chart setup
   - Impact: Trial balance incomplete

### Medium Priority (Next 8 Weeks)

8. **Security Hardening**
   - Webhook signature verification
   - Credential encryption
   - Rate limiting
   - PCI compliance gaps

---

## CONCLUSION

The system has a **solid M-Pesa foundation** but requires substantial development to:

1. ✅ Activate webhook processing for M-Pesa (convert raw events to payments)
2. ✅ Implement Stripe integration (API, webhooks, frontend)
3. ✅ Build bank reconciliation automation
4. ✅ Sync all payment systems (M-Pesa, Stripe, Bank)
5. ✅ Complete user endpoints for all payment methods
6. ✅ Build missing UI components
7. ✅ Harden security (signatures, encryption, compliance)
8. ✅ Document all systems & user workflows

**Estimated Timeline:** 12 weeks for full implementation  
**Team Size:** 2-3 developers  
**Priority Focus:** Webhook processing (Week 1) → Sync engines (Weeks 2-4) → Stripe (Weeks 5-6) → Bank (Weeks 7-8) → UI/Security (Weeks 9-12)

