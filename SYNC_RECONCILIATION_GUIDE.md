# Payment Systems Synchronization & Reconciliation Guide

**Version:** 1.0  
**Date:** April 17, 2026  
**Audience:** Technical Architects, Backend Developers, Finance Manager  
**Purpose:** Detailed documentation of missing sync mechanisms and reconciliation architecture  

---

## TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Missing Synchronization Mechanisms](#missing-synchronization-mechanisms)
4. [Reconciliation Architecture](#reconciliation-architecture)
5. [Data Flow Maps](#data-flow-maps)
6. [Error Scenarios & Recovery](#error-scenarios--recovery)
7. [Testing Strategy](#testing-strategy)
8. [Rollout Sequence](#rollout-sequence)

---

## Executive Summary

### Problem Statement

Your payment system has **three payment channels (M-Pesa, Stripe, Bank)** but they operate **independently without synchronization**:

- M-Pesa: Webhook events logged but not processed into payment records
- Stripe: Configuration only, no API integration
- Bank: Manual statement import and matching

### Impact

| Area | Impact | Severity |
|------|--------|----------|
| **Revenue Recognition** | Payments received but not recorded as income | CRITICAL |
| **Student Invoices** | Unpaid status not updated after payment | CRITICAL |
| **Accounting GL** | Payment transactions not posted to ledger | CRITICAL |
| **Cash Position** | Bank balance unknown, reconciliation manual | HIGH |
| **Audit Trail** | No clear payment-to-receipt linkage | HIGH |
| **Finance Reports** | Data inconsistency across reports | HIGH |
| **User Experience** | Students don't see payment confirmations | MEDIUM |

### Solution Architecture

Build a **Payment Synchronization Hub** that:
1. **Centralizes** all payment channel inputs (M-Pesa, Stripe, Bank)
2. **Processes** webhook events → Payment records → Invoice updates
3. **Reconciles** payments across channels in real-time
4. **Posts** to general ledger automatically
5. **Notifies** stakeholders (students, parents, finance staff)

---

## Current State Analysis

### M-Pesa Flow (Partially Working)

```
Safaricom Sends Webhook
    ↓
MpesaStkCallbackView receives payload
    ↓
Signature verified ✓
    ↓
PaymentGatewayWebhookEvent logged (raw_payload stored)
    ↓
STOPS HERE ❌
    ↓
No automatic:
✗ Payment record creation
✗ Invoice status update
✗ Wallet credit
✗ Receipt generation
✗ GL posting
✗ Notification
```

### Data Models Currently Exist

**PaymentGatewayTransaction** - Tracks M-Pesa request
- ✓ Reference number
- ✓ Phone number
- ✓ Amount
- ✓ CheckoutRequestID
- ✓ Status
- ✗ Missing: Idempotency key, retry count

**Payment** - Records actual payment
- ✓ Student, amount, method, reference
- ✗ Missing: gateway_name, gateway_transaction_id, webhook_event_id, reconciliation_status

**PaymentGatewayWebhookEvent** - Raw events
- ✓ event_type, raw_payload, created_at
- ✗ Missing: Processing status, error tracking, retry logic

**Invoice** - Student fee invoice
- ✓ Student, amount, status
- ✗ Missing: Payment method preference, late fee waiver flag

---

## Missing Synchronization Mechanisms

### Gap #1: Webhook Event Processing Pipeline

**What's Missing:**
A background job that processes unprocessed webhook events

**Current:**
```python
# Line in MpesaStkCallbackView
PaymentGatewayWebhookEvent.objects.create(
    event_type='mpesa_stk_callback',
    raw_payload=request.data,
    processed=False  # ← ALWAYS FALSE
)
```

**Should Be:**
```
Webhook in → Queue event → Background worker picks up → 
Validates → Extracts data → Creates Payment → 
Updates Invoice → Posts GL → Sends notification
```

**Required Components:**
1. **Event Queue/Broker** (Redis, RabbitMQ, or Celery)
2. **Worker Process** (Celery task)
3. **Event Handler Classes** (for M-Pesa, Stripe, Bank)
4. **Error Handling** (retry, dead-letter queue)
5. **Monitoring** (metrics, alerts)

---

### Gap #2: Multi-Gateway Payment Matching

**What's Missing:**
Logic to find payment records across all gateways

**Current:**
```
PaymentGatewayTransaction created → Webhook received →
Reference extracted → ??? FIND WHICH STUDENT ???
```

**Matching Algorithm Needed:**
```
Given: { amount: 50000, phone: "254712345678", 
         reference: "LHR519D60OP", date: "2026-04-17" }

Find matching Payment by:
  1. Phone number → Student → Invoices
  2. Reference number → Direct Payment lookup
  3. Amount + Date fuzzy match (exact or within 1%)
  4. Student admission number embedded in reference
```

---

### Gap #3: Invoice-to-Payment Allocation Sync

**What's Missing:**
Automatic allocation of payments to correct invoices

**Scenario:** Student has 3 invoices:
- INV-001: 50,000 (Term 1)
- INV-002: 40,000 (Exam fees)
- INV-003: 10,000 (Activity)

Payment received: 50,000 via M-Pesa

**Current:** Nothing happens, payment orphaned  
**Should:** Auto-allocate to oldest/highest priority invoice

**Missing Logic:**
- Priority-based allocation (oldest first, or by vote head)
- Partial payment handling
- Overpayment credit note generation
- Split payments across multiple invoices

---

### Gap #4: Payment Status Sync to Invoice

**What's Missing:**
Invoice status not updated when payment received

**Invoice Status Lifecycle:**
```
Invoice Created (UNPAID)
    ↓
Student makes payment
    ↓
Payment received (but Invoice still UNPAID) ← BUG
    ↓
Bursar manually updates Invoice status
    ↓
OR payment stays orphaned forever
```

**Should Be:**
```
Payment webhook processed
    ↓
Amount allocated to Invoice
    ↓
Invoice.paid_amount += payment.amount
    ↓
IF paid_amount >= total_amount → Invoice.status = PAID
ELSE IF paid_amount > 0 → Invoice.status = PARTIAL_PAID
ELSE → Invoice.status = UNPAID
```

---

### Gap #5: Accounting GL Posting Sync

**What's Missing:**
Payment transactions not automatically posted to ledger

**Current:**
- Invoices created → GL posting works
- Payments received → No GL posting
- Bank deposits → Manual GL entry
- M-Pesa received → No GL entry

**Should Be:**
```
Payment webhook received
    ↓
JournalEntry created automatically:
    DEBIT: M-Pesa Receivable Account (or Bank Account)
    CREDIT: Accounts Receivable (Student Invoice)
    Amount: payment amount
    Description: "Payment from student for Invoice INV-001"
    Reconciliation status: PENDING
```

**Missing Chart of Accounts:**
- 1010 M-Pesa Receivable (Asset)
- 1020 Stripe Receivable (Asset)
- 1030 Bank Account (Asset)
- 1040 Suspense Account (Asset - for unmatched payments)
- 2010 Accounts Receivable (Liability)

---

### Gap #6: Bank Statement Auto-Sync

**What's Missing:**
No automated bank statement import or reconciliation

**Current Workflow:**
```
1. Bursar logs into bank portal
2. Downloads CSV statement manually
3. Uploads CSV to system
4. Manually matches each line to Payment
5. Period-end: marks as reconciled
```

**Should Be:**
```
1. Scheduled job (daily at 9 AM)
2. Connects to bank API (Open Banking, SWIFT, or CSV dump)
3. Fetches latest statement
4. Parses transactions
5. Auto-matches to Payments (fuzzy matching)
6. Creates BankStatementLine records
7. Alerts on unmatched transactions
8. Posts GL entries for reconciliation
```

---

### Gap #7: Stripe Integration (Missing Entirely)

**What's Missing:**
Everything - API calls, webhook processing, refund handling

**Required Components:**
1. **Payment Intent Creation** → Stripe API call
2. **Webhook Handler** → Process charge.succeeded event
3. **Payment Record Creation** → From Stripe webhook
4. **Refund Logic** → Refund intent + webhook processing
5. **3D Secure/SCA** → Handle authentication requirements
6. **Error Handling** → Retry failed payments
7. **PCI Compliance** → Token storage, validation

---

### Gap #8: Duplicate Payment Prevention

**What's Missing:**
No checks to prevent recording same payment twice

**Scenario:**
1. Student initiates M-Pesa STK Push
2. Phone prompt appears, payment processes
3. Student internet drops, thinks payment failed
4. Student initiates STK Push again
5. Both payments go through
6. System records TWO payments for same invoice

**Missing Safeguards:**
- Idempotency key in webhook events
- Check PaymentGatewayTransaction before creating Payment
- Validate invoice not already fully paid
- Duplicate detection by amount + student + date

---

### Gap #9: Refund & Reversal Sync

**What's Missing:**
Payment reversals don't sync back to invoices or payments

**Current Scenario:**
```
1. Bursar approves reversal → Payment.reversed_at set
2. ✗ PaymentAllocation NOT deleted
3. ✗ Invoice.paid_amount unchanged
4. ✗ Invoice status NOT updated
5. ✗ JournalEntry REVERSAL NOT posted
6. ✗ Refund NOT initiated (no B2C payout)
7. ✗ Student NOT notified
```

**Should Be:**
```
1. Reversal approved
2. PaymentAllocation deleted
3. Invoice.paid_amount -= reversed_amount
4. Invoice status recalculated
5. JournalEntry REVERSAL posted (debit AR, credit gateway account)
6. Refund initiated (B2C M-Pesa or bank transfer)
7. RefundRequest created with tracking
8. Student notified via SMS/email
```

---

## Reconciliation Architecture

### Reconciliation Workflow

```
┌─────────────────────────────────────────────────┐
│          PAYMENT RECONCILIATION FLOW             │
└─────────────────────────────────────────────────┘

[1] DATA INGESTION
    ├─ M-Pesa webhooks (real-time)
    ├─ Stripe webhooks (real-time)
    ├─ Bank statement import (scheduled, daily)
    └─ Manual cash entries (bursar input)

[2] NORMALIZATION
    ├─ Extract common fields (amount, date, reference, party)
    ├─ Validate data integrity
    ├─ Convert to standard format
    └─ Detect duplicates

[3] MATCHING
    ├─ Find PaymentGatewayTransaction by reference
    ├─ Find Payment record by amount/date/student
    ├─ Find Invoice by student/due date/amount
    └─ Create PaymentReconciliation record

[4] ALLOCATION
    ├─ Allocate Payment to Invoice (or multiple)
    ├─ Handle partial payments
    ├─ Track overpayments as credits
    └─ Manage payment plan schedules

[5] ACCOUNTING
    ├─ Post JournalEntry (debit asset, credit AR)
    ├─ Update GL account balances
    ├─ Generate trial balance
    └─ Mark reconciliation complete

[6] NOTIFICATION
    ├─ Send receipt to student (email/SMS)
    ├─ Alert bursar if unmatched
    ├─ Update student portal
    └─ Trigger any workflows (e.g., auto-advance to next term)

[7] MONITORING
    ├─ Track reconciliation status
    ├─ Alert on exceptions
    ├─ Generate reports
    └─ Audit trail
```

### Reconciliation Statuses

**Payment Record State Machine:**

```
PENDING_WEBHOOK
    ↓ (webhook event received)
PENDING_PROCESSING
    ↓ (extracted, validated)
PENDING_ALLOCATION
    ↓ (matched to invoice, amount confirmed)
MATCHED
    ↓ (allocated, GL posted)
RECONCILED
    ↓ (reviewed and approved by bursar)
FINAL

Alternative paths:
PENDING_WEBHOOK → FAILED → RETRY → PENDING_WEBHOOK
PENDING_WEBHOOK → UNMATCHED → EXCEPTION → (manual review)
```

---

## Data Flow Maps

### Current M-Pesa Flow (INCOMPLETE)

```
┌──────────────────────────────────────────────────┐
│                 SAFARICOM API                     │
│  (STK Push → Customer enters PIN → sends result) │
└─────────────────────────┬──────────────────────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │  Webhook Event  │
                 │  (JSON POST)    │
                 └────────┬────────┘
                          │
                          ▼
              ┌──────────────────────────┐
              │MpesaStkCallbackView      │
              │- Verify signature        │
              │- Log to DB (processed=F) │
              └──────────────────────────┘
                          │
              ┌───────────┴──────────────┐
              │                          │
     STOPS HERE ❌              Should continue ↓
                     
                ┌──────────────────────────┐
                │WebhookProcessor Worker   │
                │(Background Job - MISSING)│
                ├──────────────────────────┤
                │1. Find PaymentGateway    │
                │   Transaction            │
                │2. Extract M-Pesa details │
                │3. Create Payment record  │
                │4. Create PaymentAlloc    │
                │5. Update Invoice status  │
                │6. Post JournalEntry      │
                │7. Generate receipt       │
                │8. Send notification      │
                │9. Mark processed=true    │
                └──────────────────────────┘
                          │
                          ▼
                ┌──────────────────────────┐
                │ Database Updated         │
                ├──────────────────────────┤
                │Payment: COMPLETED        │
                │Invoice: PAID             │
                │JournalEntry: POSTED      │
                │Notification: SENT        │
                └──────────────────────────┘
                          │
                          ▼
                ┌──────────────────────────┐
                │ Student Portal Updated   │
                │ Receipt available        │
                │ Invoice shown as paid    │
                └──────────────────────────┘
```

### Proposed Stripe Flow (TODO)

```
┌──────────────────────────────────────────────────┐
│                 STRIPE API                        │
│  (Create Payment Intent → Checkout → Payment)   │
└─────────────────────────┬──────────────────────────┘
                          │
                          ▼
         [Student redirected to Stripe]
                          │
                ┌─────────┴──────────┐
                │                    │
         Success              Failed/Cancel
                │                    │
                ↓                    ↓
        Webhook Event: charge.succeeded   (none)
                │
                ▼
     ┌──────────────────────────┐
     │StripeWebhookHandler      │
     │- Verify Stripe signature │
     │- Extract payment details │
     └──────────────┬───────────┘
                    │
                    ▼
          [Similar to M-Pesa flow]
          - Create Payment record
          - Allocate to Invoice
          - Post GL
          - Send receipt
          - Update portal
```

### Bank Statement Flow (TODO)

```
┌──────────────────────────────────────────────────┐
│              BANK API/CSV IMPORT                  │
│        (Daily scheduled job at 9 AM)             │
└─────────────────────────┬──────────────────────────┘
                          │
                          ▼
         ┌────────────────────────────┐
         │BankStatementImportJob      │
         │- Connect to bank API       │
         │- Fetch transactions        │
         │- Parse CSV (if file-based) │
         └────────────┬───────────────┘
                      │
                      ▼
         ┌────────────────────────────┐
         │For each transaction:       │
         │- Validate/normalize        │
         │- Check for duplicates      │
         │- Create BankStatementLine  │
         └────────────┬───────────────┘
                      │
                      ▼
       ┌──────────────────────────────────┐
       │AutoReconciliationJob             │
       │- For each BankStatementLine:     │
       │  1. Extract amount, date, ref    │
       │  2. Fuzzy match to Payments      │
       │  3. If match confidence > 90% →  │
       │     Auto-match                   │
       │  4. Else → Flag for manual match │
       └──────────────┬───────────────────┘
                      │
                      ▼
       ┌──────────────────────────────────┐
       │Update PaymentReconciliation      │
       ├──────────────────────────────────┤
       │- Matched lines: status=MATCHED   │
       │- Unmatched: status=EXCEPTION     │
       │- Post GL entries                 │
       │- Send alerts to bursar           │
       └──────────────────────────────────┘
                      │
                      ▼
       ┌──────────────────────────────────┐
       │Bursar Review Dashboard           │
       │- View unmatched transactions     │
       │- Manually match if needed        │
       │- Approve reconciliation          │
       │- Archive period                  │
       └──────────────────────────────────┘
```

---

## Error Scenarios & Recovery

### Scenario 1: M-Pesa Payment Webhook Not Received

**Problem:** Student pays, webhook doesn't arrive (network issue)

**Current State:** ❌
- Payment received by Safaricom
- Invoice still marked UNPAID
- Payment not recorded in system
- Student sees nothing

**Solution:**
1. **Polling Fallback** - Student portal has "check status" button
2. **Reconciliation Job** - Hourly job queries M-Pesa for pending transactions
3. **Payment Matching** - If found but not in system, create Payment record

**Implementation:**
```
HourlyM-PesaReconciliationJob:
    For each PaymentGatewayTransaction with status=PENDING:
        Query Safaricom API for CheckoutRequestID status
        If status = "PAID" in M-Pesa:
            Create Payment record (mark as webhook_missing=true)
            Update Invoice
            Post GL
            Alert bursar (manual review)
```

---

### Scenario 2: Duplicate Webhook Events

**Problem:** Safaricom sends same webhook twice (network retry)

**Current State:** ❌
- First webhook creates Payment A
- Second webhook creates Payment B (duplicate)
- Invoice marked as overpaid
- Chaos

**Solution:**
Use **Idempotency Key**:
```
Webhook has: { 
    event_id: "evt_xxxxx",  // Unique from Safaricom
    timestamp: "2026-04-17T14:30:00Z"
}

Before processing:
    If PaymentGatewayWebhookEvent with event_id exists:
        Already processed → Return success (idempotent)
    Else:
        Process normally
```

---

### Scenario 3: Payment Matched to Wrong Invoice

**Problem:** Fuzzy matching gives 89% confidence (high but not certain)

**Current State:** ❌
- Auto-allocate with no review
- Payment misallocated
- Wrong invoice marked paid
- Correct invoice still overdue

**Solution:**
Create **Reconciliation Queue**:
```
Confidence >= 95% → Auto-match
Confidence 80-94% → Flag for bursar review
Confidence < 80%  → Unmatched, awaiting manual entry

Bursar dashboard shows:
- Auto-matched: 95 (green)
- Pending review: 3 (yellow)
- Unmatched: 1 (red)
```

---

### Scenario 4: Bank Statement Shows Different Amount

**Problem:** Amount variance between invoice and bank statement

**Example:**
- Invoice: 50,000 KES
- Bank statement: 49,500 KES (service fee deducted)

**Solution:**
```
Auto-match algorithm:
    exact_match = (amount == 50000)
    fuzzy_match = abs(amount - 50000) / 50000 < 0.02  // 2% tolerance
    
    If exact_match:
        Match with confidence 100%
    Elif fuzzy_match:
        Match with confidence 95%
        Flag variance for review
    Else:
        No match, manual review
```

---

### Scenario 5: Stripe Payment Succeeds But Webhook Lost

**Problem:** charge.succeeded event doesn't reach webhook endpoint

**Solution:**
```
Periodic Reconciliation Job (runs every 4 hours):
    For each SubscriptionPayment with status=PENDING:
        Query Stripe API: retrieve(payment_intent_id)
        If Stripe status = "succeeded":
            Create Payment record
            Update invoice
            Post GL
            Send notification
```

---

### Scenario 6: Multiple Payments Received for Same Invoice

**Problem:** Student + Parent both pay for same invoice

**Current:** ❌ Overpayment becomes chaos  
**Solution:**
```
On payment allocation:
    if amount_allocated > invoice.balance:
        excess = amount_allocated - invoice.balance
        Mark invoice as PAID
        Create CreditNote for excess
        Apply to next term or offer refund
```

---

## Testing Strategy

### Unit Tests Required

**Webhook Processing:**
- Test M-Pesa webhook with valid signature ✓ creates Payment
- Test M-Pesa webhook with invalid signature ✗ rejected
- Test Stripe webhook with valid signature (TODO)
- Test duplicate webhooks (idempotency key)
- Test webhook with missing student ✗ exception

**Payment Matching:**
- Test exact amount match
- Test fuzzy matching (within tolerance)
- Test multiple possible invoices (pick oldest)
- Test overpayment scenario
- Test partial payment scenario

**Invoice Sync:**
- Payment created → Invoice.paid_amount incremented
- Invoice.status updated correctly (UNPAID → PARTIAL_PAID → PAID)
- Payment reversed → Invoice.paid_amount decremented
- Late fees calculated after due date

**GL Posting:**
- Payment webhook → JournalEntry created
- Entry has correct debit/credit accounts
- Amount matches payment amount
- Entry marked PENDING_RECONCILIATION

### Integration Tests Required

**M-Pesa Flow:**
1. Create invoice for student
2. Student initiates STK Push
3. Mock Safaricom webhook response
4. Verify Payment created
5. Verify Invoice updated
6. Verify GL posted
7. Verify receipt generated

**Bank Import Flow:**
1. Upload CSV bank statement
2. System auto-matches 95% of lines
3. Bursar reviews 5% unmatched
4. Bursar manually matches remaining
5. Verify GL posted for all
6. Verify trial balance balanced

**Stripe Flow (when implemented):**
1. Create invoice for student
2. Student initiates Stripe checkout
3. Mock Stripe payment success
4. Verify Payment created
5. Verify Invoice marked paid
6. Verify refund processing works

---

## Rollout Sequence

### Phase 1: Foundation (Weeks 1-2)

**Objective:** Build infrastructure for webhook processing

**Tasks:**
1. Add missing database models:
   - PaymentReconciliation
   - WebhookEventProcessing
   - PaymentGatewayCredentials (encrypted)

2. Add missing fields to existing models:
   - Payment.gateway_name
   - Payment.gateway_transaction_id
   - Payment.webhook_event_id
   - Payment.reconciliation_status
   - Invoice.payment_method_preference

3. Setup job queue:
   - Choose Celery/RQ/APScheduler
   - Setup Redis/RabbitMQ
   - Create base Job class

4. Create WebhookEventProcessor base class:
   - Validate signature
   - Extract common fields
   - Error handling

**Testing:** Unit tests for models, signature validation

---

### Phase 2: M-Pesa Webhook Processing (Weeks 3-4)

**Objective:** Convert M-Pesa webhook events to Payment records

**Tasks:**
1. Implement M-PesaWebhookEventProcessor:
   - Parse M-Pesa callback JSON
   - Extract amount, phone, receipt number
   - Find PaymentGatewayTransaction
   - Validate idempotency key

2. Implement PaymentCreationJob:
   - Create Payment record with correct student
   - Create PaymentAllocation to matching invoice
   - Handle overpayments

3. Implement InvoiceUpdateJob:
   - Update Invoice.paid_amount
   - Calculate new status (UNPAID/PARTIAL_PAID/PAID)
   - Calculate remaining balance

4. Implement GLPostingJob:
   - Create JournalEntry for payment
   - Post to M-Pesa Receivable account
   - Post to Accounts Receivable

5. Implement ReceiptGenerationJob:
   - Generate PDF receipt
   - Create receipt file
   - Store receipt_number in Payment

6. Implement NotificationJob:
   - Send SMS to student (payment received)
   - Send email with receipt
   - Update parent portal

**Testing:** 
- End-to-end M-Pesa flow
- Error scenarios (missing student, wrong amount)
- Receipt generation
- GL reconciliation

**Deployment:**
- Webhook processing initially disabled
- Test with 10% of live webhooks
- Gradually increase to 100%
- Monitor for errors

---

### Phase 3: Stripe Integration (Weeks 5-6)

**Objective:** Implement Stripe payment processing

**Tasks:**
1. Create StripePaymentGateway class:
   - Create Payment Intent
   - Handle 3D Secure
   - Process refunds

2. Create StripeWebhookEventProcessor:
   - Handle charge.succeeded
   - Handle charge.failed
   - Handle charge.refunded

3. Implement StripePaymentJob:
   - Similar to M-Pesa flow
   - Create Payment record
   - Update Invoice
   - Post GL

4. Implement StripeRefundJob:
   - Process refund requests
   - Update Payment status
   - Reverse GL entries

5. Frontend Stripe Checkout Component:
   - Integrate Stripe.js
   - Handle success/error
   - Redirect flow

**Testing:**
- Stripe test mode transactions
- Webhook delivery tests
- 3D Secure handling
- Refund processing

**Deployment:**
- Start in test mode
- Manual testing with sample transactions
- Go live with limited schools
- Monitor for issues

---

### Phase 4: Bank Integration (Weeks 7-8)

**Objective:** Automate bank statement import and reconciliation

**Tasks:**
1. Create BankStatementImportJob:
   - Connect to bank API or CSV import
   - Parse transactions
   - Create BankStatementLine records
   - Detect duplicates

2. Implement AutoReconciliationJob:
   - Fuzzy match bank lines to Payments
   - Create PaymentReconciliation records
   - Alert on unmatched transactions

3. Implement ManualReconciliationUI:
   - Bursar dashboard for unmatched items
   - Fuzzy match suggestions
   - One-click match confirmation

4. Implement GLReconciliationPosting:
   - Post GL entries for matched bank transactions
   - Create bank reconciliation reports

**Testing:**
- Bank statement parsing
- Fuzzy matching accuracy
- Manual reconciliation workflow
- GL posting verification

**Deployment:**
- Start with one bank
- Manual review of all matches before posting GL
- Gradually automate as confidence increases

---

### Phase 5: User Interface (Weeks 9-10)

**Objective:** Complete payment UI components

**Tasks:**
1. Build PaymentMethodSelector component:
   - Show M-Pesa, Stripe, Bank options
   - Based on school configuration
   - Icons and descriptions

2. Build StripeCheckoutForm component:
   - Card element
   - Billing address
   - Error handling

3. Build PaymentHistoryChart component:
   - Timeline visualization
   - Filter by method
   - Export CSV/PDF

4. Build ReceiptDownloadComponent:
   - Display receipt details
   - Download as PDF
   - Email option

5. Build BursarReconciliationUI:
   - Unmatched payments list
   - Fuzzy match suggestions
   - Bulk match confirmation
   - Exception handling

6. Update BursarDashboard:
   - Add payment method breakdown
   - Gateway success/failure rates
   - Reconciliation status widget

**Testing:**
- UI/UX testing with students
- UI/UX testing with bursars
- Responsive design testing
- Accessibility testing

**Deployment:**
- Gradual rollout to schools
- Gather user feedback
- Iterate on design

---

### Phase 6: Monitoring & Optimization (Weeks 11-12)

**Objective:** Ensure reliability and performance

**Tasks:**
1. Setup monitoring:
   - Webhook delivery rate
   - Processing latency (goal: < 5 minutes)
   - Match success rate (goal: > 95%)
   - Error rate (goal: < 1%)

2. Create alerts:
   - Webhook failures
   - Processing errors
   - Unmatched transactions
   - GL posting failures

3. Documentation:
   - How to handle exceptions
   - Troubleshooting guide
   - Finance staff training
   - Audit trail guidelines

4. Optimization:
   - Index optimization for large payment tables
   - Query optimization for reports
   - Cache frequently accessed data

**Deployment:**
- Continuous monitoring
- Regular optimization reviews

---

## Summary Matrix

| Component | M-Pesa | Stripe | Bank | Status |
|-----------|--------|--------|------|--------|
| Webhook Processing | ❌ | ❌ | N/A | PHASE 2 |
| Auto-Matching | ❌ | ❌ | ❌ | PHASE 2-4 |
| Invoice Sync | ❌ | ❌ | ❌ | PHASE 2 |
| GL Posting | ❌ | ❌ | ❌ | PHASE 2 |
| Receipts | ❌ | ❌ | N/A | PHASE 2 |
| Refund Processing | ⚠️ | ❌ | N/A | PHASE 3 |
| User Endpoints | ✅ | ❌ | ❌ | PHASE 5 |
| Frontend UI | ⚠️ | ❌ | ❌ | PHASE 5 |
| Monitoring | ❌ | ❌ | ❌ | PHASE 6 |

**Total Timeline:** 12 weeks (3 months)  
**Effort:** 2-3 full-time developers  
**Risk:** Medium (well-documented architecture, proven patterns)

---

**Document Version:** 1.0  
**Last Updated:** April 17, 2026  
**Next Review:** May 17, 2026

