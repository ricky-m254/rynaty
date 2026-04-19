# Payment Systems API Endpoint Reference Guide

**Version:** 1.0  
**Date:** April 17, 2026  
**Document Type:** API Reference for Development & Integration  

---

## TABLE OF CONTENTS

1. [Authentication & Headers](#authentication--headers)
2. [Student Payment Endpoints](#student-payment-endpoints)
3. [Parent Payment Endpoints](#parent-payment-endpoints)
4. [Bursar & Finance Endpoints](#bursar--finance-endpoints)
5. [Platform Admin Endpoints](#platform-admin-endpoints)
6. [Webhook Endpoints](#webhook-endpoints)
7. [Error Response Codes](#error-response-codes)
8. [Integration Examples](#integration-examples)

---

## Authentication & Headers

### JWT Token Requirements
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
X-School-ID: <tenant_uuid> (if multi-tenant)
X-Idempotency-Key: <uuid> (for payment endpoints)
```

### Token Scopes Required
```
student:finance.read          - View own payments/invoices
student:finance.write         - Initiate payments
parent:finance.read           - View child's finances
parent:finance.write          - Make payments for child
bursar:finance.read           - View all payments
bursar:finance.write          - Create/reverse payments
bursar:finance.admin          - Full finance access
platform:admin:finance        - Multi-tenant management
```

---

## Student Payment Endpoints

### 1. List Student Invoices

**Endpoint:** `GET /api/student-portal/finance/invoices/`

**Authentication:** Required (student user)

**Query Parameters:**
```
status=UNPAID|PAID|PARTIAL_PAID|CANCELLED    (optional)
academic_year=2025-2026                       (optional)
term=Term1|Term2|Term3                        (optional)
page=1                                        (pagination)
page_size=20
```

**Response (200 OK):**
```json
{
  "count": 5,
  "next": "http://api.example.com/api/student-portal/finance/invoices/?page=2",
  "previous": null,
  "results": [
    {
      "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "invoice_number": "INV-2026-001",
      "student": {
        "id": "student-uuid",
        "full_name": "John Doe",
        "admission_number": "ADM-2024-001"
      },
      "academic_year": "2025-2026",
      "term": "Term 1",
      "academic_class": "Form 4A",
      "issued_date": "2026-01-15T10:30:00Z",
      "due_date": "2026-02-28T23:59:59Z",
      "total_amount": 50000.00,
      "paid_amount": 30000.00,
      "balance": 20000.00,
      "status": "PARTIAL_PAID",
      "is_overdue": true,
      "days_overdue": 48,
      "late_fee_accumulated": 500.00,
      "breakdown": [
        {
          "item": "Tuition",
          "amount": 40000.00
        },
        {
          "item": "Exam Fee",
          "amount": 5000.00
        },
        {
          "item": "Activity",
          "amount": 5000.00
        }
      ]
    }
  ]
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid/expired token
- `403 Forbidden` - User not student or accessing other student's data

---

### 2. Get Invoice Detail

**Endpoint:** `GET /api/student-portal/finance/invoices/{invoice_id}/`

**Authentication:** Required

**Path Parameters:**
```
invoice_id=f47ac10b-58cc-4372-a567-0e02b2c3d479
```

**Response (200 OK):** Same as above, single object (not wrapped in results)

---

### 3. List Payment History

**Endpoint:** `GET /api/student-portal/finance/payments/`

**Authentication:** Required

**Query Parameters:**
```
payment_method=MPesa|Cash|Bank|Stripe    (optional)
status=PENDING|COMPLETED|FAILED|REVERSED (optional)
date_from=2026-01-01                     (optional)
date_to=2026-04-17                       (optional)
page=1
page_size=20
```

**Response (200 OK):**
```json
{
  "count": 10,
  "results": [
    {
      "id": "pay-uuid-1",
      "reference_number": "PAY-001",
      "receipt_number": "RCT-000001",
      "amount": 30000.00,
      "payment_method": "MPesa",
      "payment_date": "2026-01-20T14:30:00Z",
      "status": "COMPLETED",
      "gateway_reference": "LHR519D60OP",
      "gateway_name": "mpesa",
      "notes": "Payment via student portal",
      "allocations": [
        {
          "invoice_id": "inv-uuid",
          "invoice_number": "INV-2026-001",
          "amount_allocated": 30000.00
        }
      ]
    },
    {
      "id": "pay-uuid-2",
      "reference_number": "PAY-002",
      "receipt_number": "RCT-000002",
      "amount": 20000.00,
      "payment_method": "Cash",
      "payment_date": "2026-02-10T09:00:00Z",
      "status": "COMPLETED",
      "gateway_reference": null,
      "gateway_name": "cash",
      "notes": "Deposited at bursar office",
      "allocations": [
        {
          "invoice_id": "inv-uuid",
          "invoice_number": "INV-2026-001",
          "amount_allocated": 20000.00
        }
      ]
    }
  ]
}
```

---

### 4. Get Payment Receipt (MISSING - TODO)

**Endpoint:** `GET /api/student-portal/finance/payments/{payment_id}/receipt/`

**Authentication:** Required

**Query Parameters:**
```
format=pdf|json    (default: pdf)
```

**Expected Response (200 OK):**
```
Content-Type: application/pdf
[Binary PDF data]
```

**OR JSON Response:**
```json
{
  "receipt_number": "RCT-000001",
  "payment_id": "pay-uuid",
  "student_name": "John Doe",
  "amount": 30000.00,
  "payment_method": "MPesa",
  "payment_date": "2026-01-20T14:30:00Z",
  "mpesa_reference": "LHR519D60OP",
  "invoice_numbers": ["INV-2026-001"],
  "qr_code": "https://...",
  "school_name": "Saint Mary's School",
  "school_logo": "https://...",
  "verification_url": "https://school.app/verify/receipt/RCT-000001"
}
```

---

### 5. Initiate M-Pesa STK Push Payment

**Endpoint:** `POST /api/finance/mpesa/push/`

**Authentication:** Required (student user)

**Request Body:**
```json
{
  "student_id": "student-uuid",
  "phone_number": "+254712345678",
  "amount": 20000.00,
  "invoice_id": "inv-uuid",
  "description": "Fee payment for Term 1 2026"
}
```

**Response (201 Created):**
```json
{
  "transaction_id": "txn-uuid",
  "CheckoutRequestID": "ws_CO_120320231107115",
  "MerchantRequestID": "123456789",
  "CustomerMessage": "Enter your M-Pesa PIN",
  "ResponseCode": "0",
  "ResponseDescription": "Success. Request accepted for processing",
  "status": "PENDING",
  "created_at": "2026-04-17T14:30:00Z",
  "polling_url": "/api/finance/mpesa/status/?checkout_request_id=ws_CO_120320231107115"
}
```

**Error Responses:**
- `400 Bad Request` - Invalid phone number format
- `402 Payment Required` - Insufficient funds on M-Pesa account (returned by Safaricom)
- `409 Conflict` - Duplicate payment for same invoice
- `413 Payload Too Large` - Amount exceeds limit

---

### 6. Check M-Pesa Payment Status

**Endpoint:** `GET /api/finance/mpesa/status/`

**Authentication:** Required

**Query Parameters:**
```
checkout_request_id=ws_CO_120320231107115
transaction_id=txn-uuid
```

**Response (200 OK):**
```json
{
  "transaction_id": "txn-uuid",
  "CheckoutRequestID": "ws_CO_120320231107115",
  "status": "COMPLETED",
  "ResultCode": 0,
  "ResultDescription": "The service request has been processed successfully",
  "MpesaReceiptNumber": "LHR519D60OP",
  "Amount": 20000.00,
  "TransactionDate": "20260120143000",
  "phone_number": "254712345678",
  "payment_created": true,
  "payment_id": "pay-uuid",
  "invoice_updated": true
}
```

---

### 7. Stripe Payment Checkout (MISSING - TODO)

**Endpoint:** `POST /api/finance/stripe/checkout/`

**Authentication:** Required

**Request Body:**
```json
{
  "student_id": "student-uuid",
  "amount": 20000.00,
  "invoice_id": "inv-uuid",
  "success_url": "https://portal.school.app/payment/success",
  "cancel_url": "https://portal.school.app/payment/cancel"
}
```

**Expected Response (201 Created):**
```json
{
  "session_id": "cs_test_xxxxx",
  "checkout_url": "https://checkout.stripe.com/pay/cs_test_xxxxx",
  "expires_at": "2026-04-17T15:30:00Z",
  "client_secret": "pi_xxxxx_secret_xxxxx"
}
```

---

### 8. Get Available Payment Plans (MISSING - TODO)

**Endpoint:** `GET /api/student-portal/finance/payment-plans/`

**Authentication:** Required

**Query Parameters:**
```
invoice_id=inv-uuid
```

**Expected Response (200 OK):**
```json
{
  "results": [
    {
      "id": "plan-uuid-1",
      "name": "3-Month Plan",
      "duration_months": 3,
      "monthly_amount": 6666.67,
      "total_amount": 20000.00,
      "down_payment_percent": 0,
      "interest_rate": 0.0,
      "is_available": true,
      "available_until": "2026-04-30"
    },
    {
      "id": "plan-uuid-2",
      "name": "6-Month Plan",
      "duration_months": 6,
      "monthly_amount": 3333.33,
      "total_amount": 20000.00,
      "down_payment_percent": 0,
      "interest_rate": 0.0,
      "is_available": true,
      "available_until": "2026-05-31"
    }
  ]
}
```

---

### 9. Request Payment Plan (MISSING - TODO)

**Endpoint:** `POST /api/student-portal/finance/payment-plans/`

**Authentication:** Required

**Request Body:**
```json
{
  "plan_id": "plan-uuid-1",
  "invoice_id": "inv-uuid",
  "first_payment_date": "2026-04-30",
  "notes": "Hardship - awaiting scholarship"
}
```

**Expected Response (201 Created):**
```json
{
  "id": "installment-uuid",
  "plan_id": "plan-uuid-1",
  "invoice_id": "inv-uuid",
  "status": "PENDING_APPROVAL",
  "monthly_amount": 6666.67,
  "schedule": [
    {
      "installment_number": 1,
      "due_date": "2026-04-30",
      "amount": 6666.67,
      "status": "PENDING"
    },
    {
      "installment_number": 2,
      "due_date": "2026-05-30",
      "amount": 6666.67,
      "status": "PENDING"
    }
  ],
  "requested_at": "2026-04-17T14:30:00Z",
  "approval_status": "PENDING_APPROVAL",
  "approval_deadline": "2026-04-19"
}
```

---

### 10. Get Balance Summary (PARTIAL - EXISTS BUT LIMITED)

**Endpoint:** `GET /api/student-portal/finance/balance/`

**Authentication:** Required

**Response (200 OK):**
```json
{
  "student_id": "student-uuid",
  "total_invoiced": 100000.00,
  "total_paid": 70000.00,
  "total_balance": 30000.00,
  "total_overdue": 20000.00,
  "late_fees_accumulated": 1500.00,
  "has_active_payment_plan": false,
  "next_due_date": "2026-05-31",
  "payment_plan_active_installments": 0,
  "last_payment_date": "2026-02-10T09:00:00Z",
  "currency": "KES"
}
```

---

## Parent Payment Endpoints

### 1. List Children

**Endpoint:** `GET /api/parent-portal/children/`

**Authentication:** Required (parent user)

**Response (200 OK):**
```json
{
  "count": 3,
  "results": [
    {
      "id": "student-uuid-1",
      "full_name": "John Doe",
      "admission_number": "ADM-2024-001",
      "current_class": "Form 4A",
      "total_balance": 20000.00,
      "is_active": true
    },
    {
      "id": "student-uuid-2",
      "full_name": "Jane Doe",
      "admission_number": "ADM-2024-002",
      "current_class": "Form 2B",
      "total_balance": 15000.00,
      "is_active": true
    }
  ]
}
```

---

### 2. Get Child's Invoices

**Endpoint:** `GET /api/parent-portal/children/{child_id}/invoices/`

**Authentication:** Required

**Response:** Same structure as student invoices endpoint

---

### 3. Get Child's Payments

**Endpoint:** `GET /api/parent-portal/children/{child_id}/payments/`

**Authentication:** Required

**Response:** Same structure as student payments endpoint

---

### 4. Get Child's Balance

**Endpoint:** `GET /api/parent-portal/children/{child_id}/balance/`

**Authentication:** Required

**Response:** Same structure as student balance endpoint

---

### 5. Pay Child's Fees via M-Pesa

**Endpoint:** `POST /api/parent-portal/children/{child_id}/pay-mpesa/`

**Authentication:** Required (parent user)

**Request Body:**
```json
{
  "phone_number": "+254712345678",
  "amount": 20000.00,
  "invoice_id": "inv-uuid",
  "description": "Parent payment for John Doe"
}
```

**Response:** Same structure as student M-Pesa endpoint

---

### 6. Get Overdue Fees (MISSING - TODO)

**Endpoint:** `GET /api/parent-portal/children/{child_id}/arrears/`

**Authentication:** Required

**Expected Response (200 OK):**
```json
{
  "child_id": "student-uuid",
  "total_arrears": 20000.00,
  "details": [
    {
      "invoice_id": "inv-uuid",
      "invoice_number": "INV-2026-001",
      "term": "Term 1",
      "original_amount": 50000.00,
      "paid_amount": 30000.00,
      "balance": 20000.00,
      "due_date": "2026-02-28",
      "days_overdue": 48,
      "late_fees": 500.00
    }
  ]
}
```

---

### 7. Setup Recurring Payment (MISSING - TODO)

**Endpoint:** `POST /api/parent-portal/recurring-payments/`

**Authentication:** Required

**Request Body:**
```json
{
  "child_id": "student-uuid",
  "payment_method": "mpesa|stripe",
  "amount": 10000.00,
  "frequency": "monthly|weekly",
  "start_date": "2026-04-30",
  "end_date": "2026-12-31",
  "auto_allocate": true
}
```

**Expected Response (201 Created):**
```json
{
  "id": "recurring-uuid",
  "child_id": "student-uuid",
  "status": "ACTIVE",
  "next_charge_date": "2026-04-30",
  "created_at": "2026-04-17T14:30:00Z"
}
```

---

## Bursar & Finance Endpoints

### 1. List All Payments

**Endpoint:** `GET /api/finance/payments/`

**Authentication:** Required (bursar/accountant)

**Query Parameters:**
```
status=PENDING|COMPLETED|FAILED|REVERSED       (optional)
payment_method=MPesa|Cash|Bank|Stripe         (optional)
student_id=uuid                                (optional)
date_from=2026-01-01                          (optional)
date_to=2026-04-17                            (optional)
gateway=mpesa|stripe|bank|cash                (optional)
page=1
page_size=50
```

**Response (200 OK):**
```json
{
  "count": 250,
  "results": [
    {
      "id": "pay-uuid",
      "reference_number": "PAY-001",
      "receipt_number": "RCT-000001",
      "student": {
        "id": "student-uuid",
        "full_name": "John Doe",
        "admission_number": "ADM-2024-001"
      },
      "amount": 30000.00,
      "payment_method": "MPesa",
      "payment_date": "2026-01-20T14:30:00Z",
      "status": "COMPLETED",
      "gateway_name": "mpesa",
      "gateway_reference": "LHR519D60OP",
      "webhook_event_id": "wh-uuid",
      "reconciliation_status": "MATCHED",
      "allocations": [
        {
          "invoice_id": "inv-uuid",
          "amount": 30000.00
        }
      ],
      "created_at": "2026-01-20T14:30:00Z",
      "created_by": "staff-uuid"
    }
  ]
}
```

---

### 2. Create Manual Payment (Cash Receipt)

**Endpoint:** `POST /api/finance/payments/`

**Authentication:** Required (bursar)

**Request Body:**
```json
{
  "student_id": "student-uuid",
  "amount": 30000.00,
  "payment_method": "Cash",
  "reference_number": "MANUAL-CASH-2026-001",
  "receipt_number": "RCT-000001",
  "payment_date": "2026-04-17T10:00:00Z",
  "notes": "Payment received at bursar office, deposited in bank",
  "allocate_to_invoices": [
    {
      "invoice_id": "inv-uuid",
      "amount": 30000.00
    }
  ]
}
```

**Response (201 Created):**
```json
{
  "id": "pay-uuid",
  "reference_number": "MANUAL-CASH-2026-001",
  "receipt_number": "RCT-000001",
  "student_id": "student-uuid",
  "amount": 30000.00,
  "payment_method": "Cash",
  "status": "COMPLETED",
  "allocations": [
    {
      "invoice_id": "inv-uuid",
      "amount_allocated": 30000.00,
      "invoice_status": "PAID"
    }
  ],
  "created_at": "2026-04-17T10:00:00Z",
  "created_by": "staff-uuid"
}
```

---

### 3. Get Payment Detail

**Endpoint:** `GET /api/finance/payments/{payment_id}/`

**Authentication:** Required

**Response (200 OK):** Single payment object (same structure as list)

---

### 4. Reverse Payment (Refund)

**Endpoint:** `POST /api/finance/payments/{payment_id}/reverse/`

**Authentication:** Required (bursar only)

**Request Body:**
```json
{
  "reversal_reason": "Duplicate payment detected - student paid twice",
  "refund_method": "original_payment|mpesa|bank|cash",
  "refund_notes": "Refunding to student M-Pesa"
}
```

**Response (200 OK):**
```json
{
  "id": "pay-uuid",
  "status": "REVERSED",
  "reversed_at": "2026-04-17T14:30:00Z",
  "reversed_by": "bursar-uuid",
  "reversal_reason": "Duplicate payment detected - student paid twice",
  "refund_method": "mpesa",
  "refund_status": "PROCESSING",
  "refund_reference": "REF-001",
  "allocations_affected": 1,
  "invoice_status_after_reversal": "PARTIAL_PAID"
}
```

---

### 5. Manually Reconcile Payment (MISSING - TODO)

**Endpoint:** `POST /api/finance/payments/{payment_id}/reconcile/`

**Authentication:** Required (bursar)

**Request Body:**
```json
{
  "gateway_reference": "LHR519D60OP",
  "bank_reference": "CHQ-001",
  "bank_statement_line_id": "bsl-uuid",
  "reconciliation_notes": "Matched M-Pesa callback to payment record",
  "reconciliation_date": "2026-04-17"
}
```

**Expected Response (200 OK):**
```json
{
  "id": "pay-uuid",
  "reconciliation_status": "MATCHED",
  "reconciled_at": "2026-04-17T14:30:00Z",
  "reconciled_by": "bursar-uuid",
  "gateway_reference": "LHR519D60OP",
  "bank_reference": "CHQ-001"
}
```

---

### 6. List Invoices

**Endpoint:** `GET /api/finance/invoices/`

**Authentication:** Required

**Query Parameters:**
```
status=UNPAID|PAID|PARTIAL_PAID|CANCELLED    (optional)
academic_year=2025-2026                       (optional)
term=Term1|Term2|Term3                        (optional)
class_id=uuid                                 (optional)
student_id=uuid                               (optional)
page=1
page_size=50
```

**Response (200 OK):** Similar structure to student endpoint but with all students

---

### 7. Create Invoice

**Endpoint:** `POST /api/finance/invoices/`

**Authentication:** Required (bursar)

**Request Body:**
```json
{
  "academic_year_id": "ay-uuid",
  "term_id": "term-uuid",
  "class_id": "class-uuid",
  "students": [
    {
      "student_id": "student-uuid-1",
      "amount": 50000.00,
      "fee_structure_id": "fs-uuid"
    },
    {
      "student_id": "student-uuid-2",
      "amount": 50000.00,
      "fee_structure_id": "fs-uuid"
    }
  ],
  "due_date": "2026-02-28",
  "description": "Term 1 2026 fees"
}
```

**Response (201 Created):** Array of created invoices

---

### 8. Generate Arrears Report

**Endpoint:** `GET /api/finance/reports/arrears/`

**Authentication:** Required

**Query Parameters:**
```
as_of_date=2026-04-17                    (optional, defaults to today)
academic_year=2025-2026                  (optional)
term=Term1|Term2|Term3                   (optional)
class_id=uuid                            (optional)
min_balance=1000                         (optional)
page=1
page_size=100
```

**Response (200 OK):**
```json
{
  "count": 45,
  "total_arrears": 1250000.00,
  "results": [
    {
      "student_id": "student-uuid",
      "full_name": "John Doe",
      "admission_number": "ADM-2024-001",
      "current_class": "Form 4A",
      "total_arrears": 20000.00,
      "days_overdue": 48,
      "late_fees": 500.00,
      "invoices": [
        {
          "invoice_id": "inv-uuid",
          "invoice_number": "INV-2026-001",
          "term": "Term 1",
          "balance": 20000.00,
          "due_date": "2026-02-28"
        }
      ]
    }
  ]
}
```

---

### 9. Finance Dashboard (PARTIAL - TODO)

**Endpoint:** `GET /api/finance/reports/dashboard/`

**Authentication:** Required

**Response (200 OK):**
```json
{
  "period": {
    "from": "2026-04-01",
    "to": "2026-04-17"
  },
  "summary": {
    "total_collected": 500000.00,
    "total_invoiced": 1000000.00,
    "total_outstanding": 500000.00,
    "total_overdue": 300000.00,
    "collection_rate": 50.0
  },
  "by_method": {
    "mpesa": {
      "count": 45,
      "amount": 350000.00,
      "percentage": 70.0
    },
    "cash": {
      "count": 15,
      "amount": 100000.00,
      "percentage": 20.0
    },
    "bank": {
      "count": 5,
      "amount": 50000.00,
      "percentage": 10.0
    },
    "stripe": {
      "count": 0,
      "amount": 0.00,
      "percentage": 0.0
    }
  },
  "by_gateway": {
    "mpesa": {
      "total": 350000.00,
      "success_rate": 98.5,
      "failed_count": 1
    },
    "stripe": {
      "total": 0.00,
      "status": "NOT_CONFIGURED"
    },
    "bank": {
      "total": 50000.00,
      "reconciled": 45000.00,
      "pending_reconciliation": 5000.00
    }
  },
  "top_collectors": [
    {
      "class": "Form 4A",
      "collected": 150000.00,
      "target": 200000.00,
      "percentage": 75.0
    }
  ],
  "pending_reconciliation": {
    "count": 5,
    "amount": 75000.00,
    "oldest_date": "2026-04-10"
  }
}
```

---

### 10. Import Bank Statement (MISSING - TODO)

**Endpoint:** `POST /api/finance/bank/import-statement/`

**Authentication:** Required (bursar)

**Request Body (multipart/form-data):**
```
file: <CSV file>
bank_id: "bank-uuid"
statement_date: "2026-04-17"
account_number: "1234567890"
opening_balance: 500000.00
closing_balance: 750000.00
```

**Expected Response (201 Created):**
```json
{
  "import_id": "import-uuid",
  "status": "PROCESSING",
  "bank_id": "bank-uuid",
  "statement_date": "2026-04-17",
  "rows_parsed": 45,
  "rows_imported": 45,
  "rows_duplicate": 0,
  "rows_error": 0,
  "errors": [],
  "import_started_at": "2026-04-17T14:30:00Z"
}
```

---

### 11. Auto-Reconcile Bank Transactions (MISSING - TODO)

**Endpoint:** `POST /api/finance/bank/match-transactions/`

**Authentication:** Required (bursar)

**Request Body:**
```json
{
  "statement_id": "stmt-uuid",
  "match_algorithm": "fuzzy|exact",
  "fuzzy_tolerance_percent": 5,
  "fuzzy_tolerance_days": 3
}
```

**Expected Response (200 OK):**
```json
{
  "statement_id": "stmt-uuid",
  "total_lines": 45,
  "matched": 40,
  "unmatched": 5,
  "matches": [
    {
      "bank_line_id": "bsl-uuid",
      "payment_id": "pay-uuid",
      "confidence": 0.95,
      "match_reason": "Amount and reference match"
    }
  ],
  "unmatched_lines": [
    {
      "bank_line_id": "bsl-uuid",
      "amount": 75000.00,
      "reference": "INVOICE-789",
      "suggestions": [
        {
          "payment_id": "pay-uuid",
          "amount": 75000.00,
          "confidence": 0.85
        }
      ]
    }
  ]
}
```

---

### 12. View Webhook Events (MISSING - TODO)

**Endpoint:** `GET /api/finance/webhook-events/`

**Authentication:** Required (bursar)

**Query Parameters:**
```
status=unprocessed|processed|failed      (optional)
gateway=mpesa|stripe|bank               (optional)
event_type=charge.succeeded             (optional)
date_from=2026-04-01                    (optional)
date_to=2026-04-17                      (optional)
page=1
page_size=50
```

**Expected Response (200 OK):**
```json
{
  "count": 250,
  "results": [
    {
      "id": "wh-uuid",
      "event_id": "evt_xxxxx",
      "gateway": "mpesa",
      "event_type": "mpesa_stk_callback",
      "status": "unprocessed",
      "raw_payload": { ... },
      "processed": false,
      "processing_attempts": 0,
      "error_message": null,
      "created_at": "2026-04-17T14:30:00Z"
    }
  ]
}
```

---

## Platform Admin Endpoints

### 1. Get School Subscription Status

**Endpoint:** `GET /api/platform/subscriptions/{tenant_id}/`

**Authentication:** Required (platform admin)

**Response (200 OK):**
```json
{
  "id": "sub-uuid",
  "tenant_id": "school-uuid",
  "school_name": "Saint Mary's School",
  "plan": "Professional",
  "status": "ACTIVE",
  "billing_cycle": "MONTHLY",
  "amount": 5000.00,
  "currency": "KES",
  "current_period_start": "2026-04-01",
  "current_period_end": "2026-04-30",
  "next_billing_date": "2026-05-01",
  "payment_status": "PAID",
  "auto_renew": true,
  "features": [
    "student_portal",
    "parent_portal",
    "finance_module",
    "mpesa_integration",
    "analytics"
  ]
}
```

---

### 2. Get Integration Status (MISSING - TODO)

**Endpoint:** `GET /api/platform/integrations/{tenant_id}/`

**Authentication:** Required (platform admin)

**Expected Response (200 OK):**
```json
{
  "tenant_id": "school-uuid",
  "integrations": {
    "mpesa": {
      "enabled": true,
      "status": "ACTIVE",
      "last_transaction": "2026-04-17T14:30:00Z",
      "success_rate": 98.5,
      "test_mode": false,
      "configured_at": "2026-01-15",
      "next_credential_rotation": "2026-07-15"
    },
    "stripe": {
      "enabled": false,
      "status": "NOT_CONFIGURED",
      "test_mode": false,
      "configured_at": null
    },
    "bank": {
      "enabled": false,
      "status": "NOT_CONFIGURED",
      "configured_at": null
    }
  }
}
```

---

### 3. Setup Stripe Connect (MISSING - TODO)

**Endpoint:** `POST /api/platform/integrations/{tenant_id}/stripe/connect/`

**Authentication:** Required (platform admin)

**Request Body:**
```json
{
  "stripe_account_id": "acct_xxxxx",
  "stripe_api_key": "sk_live_xxxxx",
  "webhook_secret": "whsec_xxxxx",
  "test_mode": false
}
```

**Expected Response (201 Created):**
```json
{
  "integration_id": "int-uuid",
  "gateway": "stripe",
  "status": "PENDING_VERIFICATION",
  "test_result": "PENDING",
  "verified_at": null,
  "created_at": "2026-04-17T14:30:00Z"
}
```

---

## Webhook Endpoints

### M-Pesa STK Push Callback

**Endpoint:** `POST /api/mpesa/stk-callback/`

**Authentication:** None (Safaricom validates with shared secret)

**Headers Expected:**
```
Content-Type: application/json
```

**Payload (from Safaricom):**
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
          { "Name": "PhoneNumber", "Value": "254712345678" },
          { "Name": "TransactionDate", "Value": "20260120143000" }
        ]
      }
    }
  }
}
```

**Expected Response (200 OK):**
```json
{
  "processed": true,
  "message": "Webhook processed successfully"
}
```

**What SHOULD Happen (Currently Logged But Not Processed):**
1. Payload verified with Safaricom shared secret
2. PaymentGatewayTransaction located by CheckoutRequestID
3. Payment record created
4. Invoice updated
5. JournalEntry posted
6. Receipt generated
7. Notification sent

---

### Stripe Webhook (MISSING - TODO)

**Endpoint:** `POST /api/stripe/webhook/`

**Authentication:** None (Stripe validates with webhook signature)

**Headers Expected:**
```
Stripe-Signature: t=<timestamp>,v1=<signature>
```

**Expected Event Types:**
- `payment_intent.succeeded` → Create Payment record
- `payment_intent.payment_failed` → Mark as failed
- `charge.refunded` → Process refund

---

## Error Response Codes

### Standard HTTP Errors

| Code | Meaning | Example |
|------|---------|---------|
| `400` | Bad Request | Invalid JSON, missing required fields |
| `401` | Unauthorized | Missing/invalid JWT token |
| `403` | Forbidden | User role lacks permission |
| `404` | Not Found | Invoice/payment ID doesn't exist |
| `409` | Conflict | Duplicate payment, student not found |
| `413` | Payload Too Large | Amount exceeds limit |
| `429` | Too Many Requests | Rate limit exceeded |
| `500` | Server Error | Database error, external API failure |

### Payment-Specific Error Responses

**Failed M-Pesa STK Push (400):**
```json
{
  "error_code": "MPESA_INVALID_PHONE",
  "error_message": "Invalid M-Pesa phone number format",
  "details": {
    "phone_number": "+254712345678",
    "validation_rules": "Must start with +254 and be 13 digits"
  }
}
```

**Duplicate Payment (409):**
```json
{
  "error_code": "DUPLICATE_PAYMENT",
  "error_message": "Payment already exists for this invoice",
  "details": {
    "invoice_id": "inv-uuid",
    "existing_payment_id": "pay-uuid",
    "amount": 30000.00,
    "status": "PENDING"
  }
}
```

**Insufficient Balance (402):**
```json
{
  "error_code": "INSUFFICIENT_FUNDS",
  "error_message": "Student account has insufficient balance for this payment",
  "details": {
    "requested_amount": 50000.00,
    "available_balance": 30000.00,
    "shortfall": 20000.00
  }
}
```

**Access Denied (403):**
```json
{
  "error_code": "PERMISSION_DENIED",
  "error_message": "User does not have permission to access this resource",
  "details": {
    "required_role": "bursar",
    "user_role": "parent"
  }
}
```

---

## Integration Examples

### Example 1: Student Paying via M-Pesa

**Step 1: Get invoices**
```bash
curl -X GET "https://api.school.app/api/student-portal/finance/invoices/" \
  -H "Authorization: Bearer <jwt_token>"
```

**Step 2: Initiate STK Push**
```bash
curl -X POST "https://api.school.app/api/finance/mpesa/push/" \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6" \
  -d '{
    "student_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "phone_number": "+254712345678",
    "amount": 20000.00,
    "invoice_id": "inv-uuid"
  }'
```

**Response:**
```json
{
  "transaction_id": "txn-uuid",
  "CheckoutRequestID": "ws_CO_120320231107115",
  "CustomerMessage": "Enter your M-Pesa PIN",
  "ResponseCode": "0"
}
```

**Step 3: Poll for status** (every 5 seconds)
```bash
curl -X GET "https://api.school.app/api/finance/mpesa/status/?checkout_request_id=ws_CO_120320231107115" \
  -H "Authorization: Bearer <jwt_token>"
```

---

### Example 2: Parent Making Payment for Child

```bash
# Get children
curl -X GET "https://api.school.app/api/parent-portal/children/" \
  -H "Authorization: Bearer <jwt_token>"

# Get child's balance
curl -X GET "https://api.school.app/api/parent-portal/children/child-uuid/balance/" \
  -H "Authorization: Bearer <jwt_token>"

# Pay for child
curl -X POST "https://api.school.app/api/parent-portal/children/child-uuid/pay-mpesa/" \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+254712345678",
    "amount": 20000.00,
    "invoice_id": "inv-uuid"
  }'
```

---

### Example 3: Bursar Registering Cash Payment

```bash
curl -X POST "https://api.school.app/api/finance/payments/" \
  -H "Authorization: Bearer <bursar_jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "student-uuid",
    "amount": 50000.00,
    "payment_method": "Cash",
    "reference_number": "CASH-RECEIPT-001",
    "payment_date": "2026-04-17T10:00:00Z",
    "notes": "Cash received from parent",
    "allocate_to_invoices": [
      {
        "invoice_id": "inv-uuid",
        "amount": 50000.00
      }
    ]
  }'
```

---

### Example 4: Bursar Reversing Duplicate Payment

```bash
curl -X POST "https://api.school.app/api/finance/payments/pay-uuid/reverse/" \
  -H "Authorization: Bearer <bursar_jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "reversal_reason": "Duplicate payment - student paid twice",
    "refund_method": "mpesa",
    "refund_notes": "Refunding to student M-Pesa account"
  }'
```

---

## Additional Notes

### Rate Limiting
- 60 requests per minute per authenticated user
- 10 payment initiation requests per minute per user (anti-spam)
- Stripe webhook: Unlimited (signature verified)

### Idempotency
- All POST payment endpoints should include `X-Idempotency-Key` header
- Prevents duplicate payments if request is retried
- Idempotency key valid for 24 hours

### Pagination
- Default page size: 20
- Max page size: 100
- Use `next` URL from response for pagination

### Sorting
- Add `?ordering=-created_at` to sort by creation date (newest first)
- Add `?ordering=student__full_name` to sort by student name

### Filtering
All query parameters are optional and can be combined:
```
/api/finance/payments/?status=COMPLETED&payment_method=MPesa&date_from=2026-01-01
```

---

**Document Version:** 1.0  
**Last Updated:** April 17, 2026  
**Next Review:** May 17, 2026

